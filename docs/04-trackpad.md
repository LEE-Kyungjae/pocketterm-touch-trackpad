# 04 — 터치 → 트랙패드 변환

터치스크린은 기본적으로 **절대좌표** 장치다(누른 자리가 곧 클릭). 이걸 노트북 트랙패드처럼
**상대 이동**으로 바꾸는 게 [`trackpad/touchpad_bridge.py`](../trackpad/touchpad_bridge.py) 다.

작은 3.5" 화면을 **손밑 조작판**으로 두고 커서를 움직이고 싶을 때(예: HDMI 큰 화면 병행) 유용하다.
3.5" 가 유일한 화면이면 그냥 절대터치가 더 자연스러우니 이 도구는 선택사항이다.

> ⚠️ **검증 상태**: 문법·구조는 로컬 검증 완료. **실제 이 기기 터치 위 동작은 미검증**
> (작성 시점 SSH 접근 제약). 첫 실행은 서비스로 걸기 전에 아래처럼 포그라운드로 확인해라.

---

## 동작(제스처)

| 입력 | 결과 |
|------|------|
| 손가락 1개 이동 | 커서 상대 이동 |
| 짧은 탭(거의 안 움직임) | 왼쪽 클릭 |
| 두 손가락 짧은 탭 | 오른쪽 클릭 |
| 탭 직후 눌러서 이동 | 드래그(왼쪽 버튼 홀드) |
| 두 손가락 이동 | 스크롤(세로/가로 휠) |

## 요구사항

```bash
sudo apt install -y python3-evdev      # 또는  pip install evdev
```
`/dev/uinput` 과 입력장치 접근 때문에 **root**(또는 input/uinput 권한)로 실행한다.

## 먼저 손으로 확인 (권장)

```bash
# 1) 터치 장치가 잡히는지
sudo python3 trackpad/touchpad_bridge.py --list
#   [TOUCH] /dev/input/eventN  <장치이름>  ← 이런 줄이 나와야 한다

# 2) 포그라운드 + 디버그로 실제 만져보며 관찰 (Ctrl-C 종료)
sudo python3 trackpad/touchpad_bridge.py --debug
```

- 커서가 반대로 가거나 너무 빠르면 → 아래 상수 조정
- 장치를 못 찾으면 → `--device /dev/input/eventN` 로 직접 지정

## 서비스로 상시 실행

```bash
sudo ./scripts/install-trackpad.sh
systemctl status pocketterm-trackpad.service
journalctl -u pocketterm-trackpad.service -f
```

`provision.sh --trackpad` 로도 한 번에 설치된다.

## 튜닝 (touchpad_bridge.py 상단 상수)

| 상수 | 의미 | 기본 |
|------|------|------|
| `POINTER_SPEED` | 커서 이동 배율(클수록 빠름) | `1.4` |
| `SCROLL_SPEED` | 2손가락 스크롤 배율 | `0.05` |
| `TAP_MAX_MS` | 이 시간 안에 떼면 탭 후보 | `200` |
| `TAP_SLOP_PX` | 이 픽셀 넘게 움직이면 탭 아님 | `12` |
| `DRAG_START_MS` | 탭 직후 이 시간 안에 다시 누르면 드래그 | `300` |

## 알려진 한계 / 앞으로

- 멀티터치 **Type B**(ABS_MT_SLOT) 와 단일터치(ST, BTN_TOUCH+ABS_X/Y) 를 지원.
  그 외 특이한 프로토콜은 `--debug` 로 이벤트 보고 분기 추가 필요.
- 스크롤 방향(자연/역방향)은 `SCROLL_SPEED` 부호로 조정.
- 우클릭 = **두 손가락 탭**(구현됨). 관성 스크롤은 아직 없음 — 필요하면 추가.

## 권한을 root 대신 좁히려면 (선택)

```bash
sudo usermod -aG input <사용자>
# udev: /dev/uinput 를 input 그룹에 쓰기 허용
echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | \
  sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```
그 뒤 서비스 유닛의 `User=root` 를 해당 사용자로 바꾸고 재시작.
