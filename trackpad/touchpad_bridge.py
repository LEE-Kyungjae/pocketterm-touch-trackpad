#!/usr/bin/env python3
"""
PocketTerm 35 — 터치스크린을 트랙패드로 변환하는 브리지.

터치스크린은 기본적으로 '절대좌표' 장치다(누른 자리가 곧 클릭 위치).
이 스크립트는 터치 이벤트를 grab 해서 원래 절대 포인터로 안 새게 막고,
대신 노트북 트랙패드처럼 '상대 이동'을 하는 가상 마우스를 만들어 준다.

제스처:
  - 손가락 1개 이동            -> 커서 상대 이동
  - 짧게 탭(움직임 거의 없음)   -> 왼쪽 클릭
  - 탭한 뒤 바로 눌러서 이동     -> 드래그(왼쪽 버튼 홀드)
  - 손가락 2개                 -> 스크롤(세로/가로 휠)

장치는 자동 탐지한다(멀티터치/BTN_TOUCH 능력을 가진 첫 장치).
--device /dev/input/eventN 으로 강제 지정도 가능.

의존성: python3-evdev  (apt install python3-evdev  또는  pip install evdev)
루트 또는 input/uinput 접근 권한 필요.

주의: 이 코드는 실제 하드웨어에서 최종 검증되지 않았다(작성 시점에 SSH 접근 제약).
      goodix gt911 / ft6236 계열(멀티터치 Type B + BTN_TOUCH)을 기준으로 작성했다.
      동작이 이상하면 --debug 로 이벤트를 찍어보고 상수(SCROLL_*, TAP_*)를 조정한다.
"""
from __future__ import annotations

import argparse
import sys
import select
import time
from typing import Dict, Optional

try:
    from evdev import InputDevice, UInput, ecodes, list_devices
except ImportError:
    sys.stderr.write(
        "python3-evdev 가 필요하다.\n"
        "  Ubuntu:  sudo apt install -y python3-evdev\n"
        "  pip   :  pip install evdev\n"
    )
    sys.exit(1)


# --- 튜닝 상수 -------------------------------------------------------------
POINTER_SPEED = 1.4      # 커서 이동 배율(클수록 빠름)
SCROLL_SPEED = 0.05      # 2손가락 스크롤 배율(움직인 픽셀 -> 휠 클릭)
TAP_MAX_MS = 200         # 이 시간 안에 떼면 탭 후보
TAP_SLOP_PX = 12         # 이 픽셀 이상 움직이면 탭이 아니라 이동으로 간주
DRAG_START_MS = 300      # 탭 직후 이 시간 안에 다시 누르면 드래그 시작
SCROLL_INERTIA = True    # 2손가락 스크롤 후 관성(놓아도 잠깐 계속 흐름)
SCROLL_FRICTION = 0.92   # 관성 감쇠(16ms당 배율, 작을수록 빨리 멈춤)
SCROLL_INERTIA_MIN = 30  # 이 속도(units/sec) 아래로 떨어지면 관성 정지
INERTIA_TICK = 0.012     # 관성 갱신 주기(초)


def find_touch_device(explicit: Optional[str]) -> InputDevice:
    """터치스크린 evdev 장치를 찾는다."""
    if explicit:
        return InputDevice(explicit)

    candidates = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except (PermissionError, OSError):
            continue
        caps = dev.capabilities()
        abs_caps = caps.get(ecodes.EV_ABS, [])
        abs_codes = {c for c, _ in abs_caps} if abs_caps and isinstance(abs_caps[0], tuple) else set(abs_caps)
        key_caps = set(caps.get(ecodes.EV_KEY, []))
        has_mt = ecodes.ABS_MT_POSITION_X in abs_codes
        has_st = ecodes.ABS_X in abs_codes and ecodes.BTN_TOUCH in key_caps
        # 마우스/태블릿 펜 등은 제외하고 순수 터치스크린만
        is_pointer_mouse = ecodes.REL_X in caps.get(ecodes.EV_REL, [])
        if (has_mt or has_st) and not is_pointer_mouse:
            candidates.append(dev)
        else:
            dev.close()

    if not candidates:
        raise SystemExit(
            "터치스크린 장치를 못 찾았다. `python3 touchpad_bridge.py --list` 로 확인하고 "
            "--device 로 직접 지정해라."
        )
    # 여러 개면 첫 번째. 보통 하나뿐.
    chosen = candidates[0]
    for extra in candidates[1:]:
        extra.close()
    return chosen


def list_all_devices() -> None:
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except (PermissionError, OSError):
            continue
        caps = dev.capabilities(verbose=False)
        abs_caps = caps.get(ecodes.EV_ABS, [])
        abs_codes = {c for c, _ in abs_caps} if abs_caps and isinstance(abs_caps[0], tuple) else set(abs_caps)
        tag = "TOUCH" if ecodes.ABS_MT_POSITION_X in abs_codes or ecodes.ABS_X in abs_codes else "     "
        print(f"[{tag}] {path}  {dev.name}")
        dev.close()


class Slot:
    __slots__ = ("x", "y", "active")

    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.active = False


def run(dev: InputDevice, debug: bool = False) -> None:
    ui = UInput(
        {
            ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
            ecodes.EV_REL: [
                ecodes.REL_X,
                ecodes.REL_Y,
                ecodes.REL_WHEEL,
                ecodes.REL_HWHEEL,
            ],
        },
        name="PocketTerm Virtual Trackpad",
    )

    # 터치 이벤트를 독점해서 절대 포인터로 새지 않게 한다.
    dev.grab()
    print(f"[trackpad] using: {dev.path}  ({dev.name})")
    print("[trackpad] Ctrl-C 로 종료")

    slots: Dict[int, Slot] = {}

    def slot(i: int) -> Slot:
        s = slots.get(i)
        if s is None:
            s = Slot()
            slots[i] = s
        return s

    def active_count() -> int:
        return sum(1 for s in slots.values() if s.active)

    def emit_click(button: int) -> None:
        ui.write(ecodes.EV_KEY, button, 1)
        ui.syn()
        ui.write(ecodes.EV_KEY, button, 0)
        ui.syn()

    # 스크롤 누적기: 소수 휠을 모아 정수 클릭으로 변환(매프레임 반올림 손실 방지)
    scroll_acc = [0.0, 0.0]   # [vertical, horizontal]

    def emit_scroll(dv: float, dh: float) -> None:
        scroll_acc[0] += dv
        scroll_acc[1] += dh
        iv = int(scroll_acc[0])
        ih = int(scroll_acc[1])
        if iv:
            ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, iv)
            scroll_acc[0] -= iv
        if ih:
            ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL, ih)
            scroll_acc[1] -= ih
        if iv or ih:
            ui.syn()

    # 포인터 누적기(서브픽셀 손실 방지)
    ptr_acc = [0.0, 0.0]

    def emit_move(dx: float, dy: float) -> None:
        ptr_acc[0] += dx
        ptr_acc[1] += dy
        ix = int(ptr_acc[0])
        iy = int(ptr_acc[1])
        if ix:
            ui.write(ecodes.EV_REL, ecodes.REL_X, ix)
            ptr_acc[0] -= ix
        if iy:
            ui.write(ecodes.EV_REL, ecodes.REL_Y, iy)
            ptr_acc[1] -= iy
        if ix or iy:
            ui.syn()

    # 제스처 상태
    cur_slot = 0
    last_primary = None
    last_primary_slot = -1
    prev_count = 0
    touch_down_ms = 0.0
    touch_moved = 0.0
    last_up_ms = 0.0
    max_fingers = 0
    dragging = False
    left_down = False

    # 관성 스크롤 상태 (단위: units/sec)
    scroll_vel = [0.0, 0.0]    # 최근 2손가락 이동으로 추정한 속도
    last_scroll_ms = 0.0
    inertia = [0.0, 0.0]       # 진행 중인 관성 속도

    def process_syn(now: float) -> None:
        nonlocal last_primary, last_primary_slot, prev_count, touch_down_ms, touch_moved
        nonlocal last_up_ms, max_fingers, dragging, left_down, last_scroll_ms
        count = active_count()

        primary = None
        primary_slot = -1
        for i in sorted(slots):
            if slots[i].active:
                primary = slots[i]
                primary_slot = i
                break

        if debug:
            pos = (primary.x, primary.y) if primary else None
            print(f"count={count} primary={pos} drag={dragging} "
                  f"inertia={inertia[0]:.1f}")

        if count > max_fingers:
            max_fingers = count

        # 손가락 처음 닿음 -> 관성 취소 + 상태 초기화
        if count > 0 and prev_count == 0 and primary is not None:
            inertia[0] = inertia[1] = 0.0
            scroll_vel[0] = scroll_vel[1] = 0.0
            touch_down_ms = now
            touch_moved = 0.0
            max_fingers = count
            last_primary = (primary.x, primary.y)
            last_primary_slot = primary_slot
            if now - last_up_ms <= DRAG_START_MS:
                dragging = True
                left_down = True
                ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
                ui.syn()

        # 이동 처리
        elif count >= 1 and primary is not None and last_primary is not None:
            # 손가락 개수나 주 손가락(primary)이 바뀐 프레임에는 이동을 내보내지
            # 않는다. 안 그러면 두 손가락 중 하나(특히 기준 손가락)가 먼저 떨어질 때
            # 남은 손가락과의 좌표 차이만큼 커서가 튄다.
            if count != prev_count or primary_slot != last_primary_slot:
                last_primary = (primary.x, primary.y)
                last_primary_slot = primary_slot
            else:
                dx = primary.x - last_primary[0]
                dy = primary.y - last_primary[1]
                last_primary = (primary.x, primary.y)
                touch_moved += (dx * dx + dy * dy) ** 0.5

                if count == 1:
                    emit_move(dx * POINTER_SPEED, dy * POINTER_SPEED)
                elif count >= 2:
                    dv = dy * SCROLL_SPEED   # 세로 스크롤 방향(부호 뒤집어 조정)
                    dh = dx * SCROLL_SPEED
                    emit_scroll(dv, dh)
                    dt = (now - last_scroll_ms) / 1000.0
                    if dt > 0:
                        scroll_vel[0] = 0.6 * scroll_vel[0] + 0.4 * (dv / dt)
                        scroll_vel[1] = 0.6 * scroll_vel[1] + 0.4 * (dh / dt)
            last_scroll_ms = now

        # 모든 손가락 뗌
        if count == 0 and prev_count > 0:
            if dragging or left_down:
                ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
                ui.syn()
                dragging = False
                left_down = False
            else:
                held = now - touch_down_ms
                if held <= TAP_MAX_MS and touch_moved <= TAP_SLOP_PX:
                    # 1손가락 탭 -> 좌클릭, 2손가락 탭 -> 우클릭
                    if max_fingers >= 2:
                        emit_click(ecodes.BTN_RIGHT)
                    else:
                        emit_click(ecodes.BTN_LEFT)
                        last_up_ms = now
                elif max_fingers >= 2 and SCROLL_INERTIA:
                    # 2손가락 스크롤 후 놓음 -> 관성 시작
                    inertia[0] = scroll_vel[0]
                    inertia[1] = scroll_vel[1]
            max_fingers = 0
            last_primary = None
            last_primary_slot = -1
            for s in slots.values():
                s.active = False

        prev_count = count

    def handle_event(ev) -> None:
        nonlocal cur_slot
        if ev.type == ecodes.EV_ABS:
            if ev.code == ecodes.ABS_MT_SLOT:
                cur_slot = ev.value
            elif ev.code == ecodes.ABS_MT_TRACKING_ID:
                slot(cur_slot).active = ev.value != -1
            elif ev.code == ecodes.ABS_MT_POSITION_X:
                slot(cur_slot).x = ev.value
            elif ev.code == ecodes.ABS_MT_POSITION_Y:
                slot(cur_slot).y = ev.value
            elif ev.code == ecodes.ABS_X:
                slot(0).x = ev.value
            elif ev.code == ecodes.ABS_Y:
                slot(0).y = ev.value
        elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
            if not slots or list(slots.keys()) == [0]:
                slot(0).active = ev.value == 1
        elif ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT:
            process_syn(time.monotonic() * 1000.0)

    fd = dev.fileno()
    last_tick = time.monotonic()
    try:
        while True:
            timeout = INERTIA_TICK if (inertia[0] or inertia[1]) else 1.0
            r, _, _ = select.select([fd], [], [], timeout)
            now_s = time.monotonic()
            if r:
                try:
                    for ev in dev.read():
                        handle_event(ev)
                except BlockingIOError:
                    pass
            # 관성 스크롤 (손가락 없을 때만)
            if active_count() == 0 and (inertia[0] or inertia[1]):
                dt = now_s - last_tick
                if dt > 0:
                    emit_scroll(inertia[0] * dt, inertia[1] * dt)
                    decay = SCROLL_FRICTION ** (dt / 0.016)
                    inertia[0] *= decay
                    inertia[1] *= decay
                    if (inertia[0] ** 2 + inertia[1] ** 2) ** 0.5 < SCROLL_INERTIA_MIN:
                        inertia[0] = inertia[1] = 0.0
            last_tick = now_s
    except KeyboardInterrupt:
        pass
    finally:
        try:
            dev.ungrab()
        except OSError:
            pass
        ui.close()
        dev.close()
        print("\n[trackpad] 종료")


def main() -> None:
    ap = argparse.ArgumentParser(description="터치스크린 -> 트랙패드 브리지")
    ap.add_argument("--device", help="터치스크린 evdev 경로 (예: /dev/input/event4)")
    ap.add_argument("--list", action="store_true", help="입력장치 목록만 출력하고 종료")
    ap.add_argument("--debug", action="store_true", help="이벤트 디버그 출력")
    args = ap.parse_args()

    if args.list:
        list_all_devices()
        return

    dev = find_touch_device(args.device)
    run(dev, debug=args.debug)


if __name__ == "__main__":
    main()
