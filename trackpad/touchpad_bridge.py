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
    cur_slot = 0

    # 현재 리포트 프레임에서의 primary 손가락 좌표 갱신 추적
    last_primary = None            # (x, y) 직전 프레임 primary 위치
    prev_finger_count = 0

    # 탭/드래그 상태
    touch_down_ms = 0.0
    touch_moved = 0.0              # 눌린 뒤 이동 누적 거리
    last_up_ms = 0.0              # 마지막으로 손 뗀 시각(드래그 판정용)
    max_fingers = 0               # 이번 터치 시퀀스에서 동시에 닿은 최대 손가락 수
    dragging = False
    left_down = False

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

    try:
        for ev in dev.read_loop():
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_MT_SLOT:
                    cur_slot = ev.value
                elif ev.code == ecodes.ABS_MT_TRACKING_ID:
                    s = slot(cur_slot)
                    s.active = ev.value != -1
                elif ev.code == ecodes.ABS_MT_POSITION_X:
                    slot(cur_slot).x = ev.value
                elif ev.code == ecodes.ABS_MT_POSITION_Y:
                    slot(cur_slot).y = ev.value
                # 단일터치(ST) 전용 장치 대비: ABS_X/ABS_Y 를 slot 0 에 매핑
                elif ev.code == ecodes.ABS_X:
                    slot(0).x = ev.value
                elif ev.code == ecodes.ABS_Y:
                    slot(0).y = ev.value

            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                # ST 장치는 slot 0 활성 상태를 BTN_TOUCH 로 알린다.
                if not slots or list(slots.keys()) == [0]:
                    slot(0).active = ev.value == 1

            elif ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT:
                now = time.monotonic() * 1000.0
                count = active_count()

                # primary = 활성 slot 중 가장 작은 번호
                primary = None
                for i in sorted(slots):
                    if slots[i].active:
                        primary = slots[i]
                        break

                if debug:
                    print(f"count={count} primary={(primary.x, primary.y) if primary else None} "
                          f"drag={dragging} left={left_down}")

                # 이번 시퀀스에서 동시에 닿은 최대 손가락 수 갱신(우클릭 판정용)
                if count > max_fingers:
                    max_fingers = count

                # --- 손가락이 처음 닿음 ---
                if count > 0 and prev_finger_count == 0 and primary is not None:
                    touch_down_ms = now
                    touch_moved = 0.0
                    max_fingers = count
                    last_primary = (primary.x, primary.y)
                    # 직전 탭 후 곧바로 다시 눌렀으면 드래그 개시
                    if now - last_up_ms <= DRAG_START_MS:
                        dragging = True
                        left_down = True
                        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
                        ui.syn()

                # --- 이동 처리 ---
                elif count >= 1 and primary is not None and last_primary is not None:
                    dx = primary.x - last_primary[0]
                    dy = primary.y - last_primary[1]
                    last_primary = (primary.x, primary.y)
                    touch_moved += (dx * dx + dy * dy) ** 0.5

                    if count == 1:
                        mx = int(dx * POINTER_SPEED)
                        my = int(dy * POINTER_SPEED)
                        if mx:
                            ui.write(ecodes.EV_REL, ecodes.REL_X, mx)
                        if my:
                            ui.write(ecodes.EV_REL, ecodes.REL_Y, my)
                        if mx or my:
                            ui.syn()
                    elif count >= 2:
                        # 2손가락: 스크롤. 세로 우선.
                        sv = int(-dy * SCROLL_SPEED)
                        sh = int(dx * SCROLL_SPEED)
                        if sv:
                            ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, sv)
                        if sh:
                            ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL, sh)
                        if sv or sh:
                            ui.syn()

                # --- 모든 손가락 뗌 ---
                if count == 0 and prev_finger_count > 0:
                    if dragging or left_down:
                        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
                        ui.syn()
                        dragging = False
                        left_down = False
                    else:
                        # 탭 판정: 짧고 거의 안 움직였으면 클릭
                        #   1손가락 탭 -> 좌클릭,  2손가락 탭 -> 우클릭
                        held = now - touch_down_ms
                        if held <= TAP_MAX_MS and touch_moved <= TAP_SLOP_PX:
                            if max_fingers >= 2:
                                emit_click(ecodes.BTN_RIGHT)
                            else:
                                emit_click(ecodes.BTN_LEFT)
                                last_up_ms = now
                    max_fingers = 0
                    last_primary = None
                    # 뗀 slot 정리
                    for s in slots.values():
                        s.active = False

                prev_finger_count = count

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
