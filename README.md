# PocketTerm 35 — Touchscreen → Trackpad

**포켓텀(PocketTerm 35)의 터치스크린을 노트북 트랙패드처럼 바꿔주는 도구** +
라즈베리파이 5 / Waveshare 3.5" 디스플레이·터치 셋업 복구 매뉴얼.

> **Turn a Raspberry Pi touchscreen into a laptop-style trackpad** (Linux `evdev` → `uinput`):
> relative pointer, tap-to-click, two-finger tap right-click, two-finger scroll with
> inertia/momentum, and tap-drag. Runs as a systemd service.

`raspberry-pi` · `touchscreen` · `trackpad` · `touchpad` · `evdev` · `uinput` · `goodix` · `waveshare`

이 저장소의 목적은 두 가지다:

1. **재난 복구** — 파이가 날아가거나 SD/eMMC를 새로 구웠을 때, 이 문서와 스크립트만 보고
   디스플레이·터치·와이파이를 다시 세팅할 수 있게 한다.
2. **터치 → 트랙패드 변환 도구** 공개 — 터치스크린을 노트북 트랙패드처럼 쓰는 `touchpad_bridge.py`.

> ⚠️ **정직성 노트**
> 이 저장소의 값들은 실제 기기(Raspberry Pi 5 Model B, Ubuntu)에서 확인한 것과,
> 표준 절차로 채운 것이 섞여 있다. 각 문서에 `✅ 확인됨` / `ℹ️ 표준절차(미검증)` 로 표시했다.
> 트랙패드는 실기기(Pi 5 / Goodix 터치)에서 동작 확인 완료 — 아래 4번 참고.

---

## 확인된 대상 환경 ✅

| 항목 | 값 |
|------|-----|
| 보드 | Raspberry Pi 5 Model B Rev 1.0 |
| OS | Ubuntu (aarch64), 커널 `7.0.0-1009-raspi` |
| 부팅 펌웨어 경로 | `/boot/firmware/` (A/B **tryboot** 레이아웃, `os_prefix=current/`) |
| 디스플레이 | Waveshare 3.5" DPI, 오버레이 `waveshare-35dpi-5b` |
| 오버레이 위치 | `/boot/firmware/current/overlays/` 와 `/boot/firmware/new/overlays/` |
| 오버레이 md5 | `ec0dae463e40becc7e9124b97e7537fb` |

> **핵심 함정**: 이 Ubuntu 이미지에는 흔히 아는 `/boot/firmware/overlays/` 가 **없다**.
> 오버레이는 `current/overlays/`(일반 부팅)와 `new/overlays/`(tryboot)에 들어가야 한다.
> `config.txt` 는 `[all] os_prefix=current/`, `[tryboot] os_prefix=new/` 로 되어 있다.

---

## 빠른 복구 (파이가 날아갔을 때)

파이에 SSH로 들어간 뒤:

```bash
git clone <이-저장소-URL> pocketterm-touch-trackpad
cd pocketterm-touch-trackpad

# 디스플레이 오버레이만 복구
sudo ./scripts/provision.sh

# 디스플레이 + 터치 트랙패드 서비스까지
sudo ./scripts/provision.sh --trackpad

sudo reboot
```

`provision.sh` 가 하는 일:
- `overlays/waveshare-35dpi-5b.dtbo` 를 존재하는 모든 부팅 오버레이 디렉터리에 복사
- `/boot/firmware/config.txt` 에 `dtparam=i2c_arm=on`, `dtoverlay=waveshare-35dpi-5b` 를 **중복 없이** 주입 (기존 config.txt는 타임스탬프 백업)
- `--trackpad` 시 트랙패드 브리지를 systemd 서비스로 설치

와이파이는 자동화하지 않는다(자격증명이 필요하므로) → [docs/03-wifi.md](docs/03-wifi.md).

---

## 문서

| 문서 | 내용 |
|------|------|
| [docs/01-hardware.md](docs/01-hardware.md) | 하드웨어 구성, 계정, 확인된 사실 |
| [docs/02-display-overlay.md](docs/02-display-overlay.md) | 디스플레이 오버레이 — 파일 위치, config.txt, 수동 복구, 검증 |
| [docs/03-wifi.md](docs/03-wifi.md) | 와이파이 연결 (폰 핫스팟 포함), netplan / cloud-init |
| [docs/04-trackpad.md](docs/04-trackpad.md) | 터치 → 트랙패드 변환 도구 사용법과 튜닝 |

## 저장소 구조

```
pocketterm-touch-trackpad/
├── README.md
├── overlays/waveshare-35dpi-5b.dtbo     # 실제 오버레이 바이너리 (md5 ec0dae46…)
├── config/config.txt.snippet            # config.txt 에 필요한 줄
├── scripts/
│   ├── provision.sh                     # 디스플레이 오버레이 프로비저닝
│   └── install-trackpad.sh              # 트랙패드 서비스 설치
├── trackpad/
│   ├── touchpad_bridge.py               # 터치 → 트랙패드 브리지 (핵심)
│   ├── pocketterm-trackpad.service      # systemd 유닛
│   └── requirements.txt
└── docs/…
```

## 4. 트랙패드 검증 상태

실기기(Raspberry Pi 5, `Goodix Capacitive TouchScreen` = `/dev/input/event9`)에서 **확인 완료** ✅
- 터치 자동탐지 → grab → 가상 트랙패드 생성
- 1손가락 커서 이동 · 1손가락 탭 좌클릭 · 2손가락 탭 우클릭
- 2손가락 스크롤 + 관성(momentum) · 탭-드래그
- systemd 서비스로 상시 실행(부팅 자동)

동작을 직접 관찰(튜닝용):

```bash
sudo python3 trackpad/touchpad_bridge.py --list      # 터치 장치 확인
sudo python3 trackpad/touchpad_bridge.py --debug     # 손으로 만져보며 이벤트 관찰
```

세기·방향 조정은 [docs/04-trackpad.md](docs/04-trackpad.md) 의 튜닝 상수 참고.

## 라이선스

MIT — [LICENSE](LICENSE)
