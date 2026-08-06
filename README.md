# PocketTerm 35

라즈베리파이 5 + Waveshare 3.5" DPI 터치 디스플레이로 만든 포켓 터미널(**PocketTerm 35**)의
셋업 매뉴얼과 프로비저닝 도구.

이 저장소의 목적은 두 가지다:

1. **재난 복구** — 파이가 날아가거나 SD/eMMC를 새로 구웠을 때, 이 문서와 스크립트만 보고
   디스플레이·터치·와이파이를 다시 세팅할 수 있게 한다.
2. **터치 → 트랙패드 변환 도구** 공개 — 터치스크린을 노트북 트랙패드처럼 쓰는 `touchpad_bridge.py`.

> ⚠️ **정직성 노트**
> 이 저장소의 값들은 실제 기기(Raspberry Pi 5 Model B, Ubuntu)에서 확인한 것과,
> 표준 절차로 채운 것이 섞여 있다. 각 문서에 `✅ 확인됨` / `ℹ️ 표준절차(미검증)` 로 표시했다.
> 트랙패드 스크립트는 작성 시점에 실제 하드웨어에서 최종 검증되지 않았다(아래 4번 참고).

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
git clone <이-저장소-URL> pocketterm35
cd pocketterm35

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
pocketterm35/
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

## 4. 트랙패드 검증 상태 (읽어라)

`touchpad_bridge.py` 는 goodix gt911 / ft6236 계열(멀티터치 Type B + BTN_TOUCH)을
기준으로 작성했고, 로컬에서 문법·구조는 검증했지만 **실제 이 기기 터치 위에서의 동작은
아직 확인하지 못했다**(작성 시점 SSH 접근 제약). 첫 실행은 서비스로 걸기 전에
포그라운드 + `--debug` 로 확인하는 걸 권장한다:

```bash
sudo python3 trackpad/touchpad_bridge.py --list      # 터치 장치 확인
sudo python3 trackpad/touchpad_bridge.py --debug     # 손으로 만져보며 관찰
```

이상하면 [docs/04-trackpad.md](docs/04-trackpad.md) 의 튜닝 상수 조정.

## 라이선스

MIT — [LICENSE](LICENSE)
