# 02 — 디스플레이 오버레이 (핵심 복구)

Waveshare 3.5" DPI 디스플레이를 살리는 두 요소:

1. **오버레이 바이너리** `waveshare-35dpi-5b.dtbo` 가 부팅 오버레이 디렉터리에 있을 것
2. **`/boot/firmware/config.txt`** 에 `dtoverlay=waveshare-35dpi-5b` 줄이 있을 것

둘 다 있어야 하고, **파일을 새로 넣었으면 재부팅해야** 적용된다.

---

## 오버레이 파일 위치 ✅ (이 이미지의 함정)

이 Ubuntu 이미지는 A/B **tryboot** 레이아웃이라, 흔히 아는 `/boot/firmware/overlays/` 가
**존재하지 않는다**. 대신:

```
/boot/firmware/current/overlays/waveshare-35dpi-5b.dtbo   ← 일반 부팅 (os_prefix=current/)
/boot/firmware/new/overlays/waveshare-35dpi-5b.dtbo       ← tryboot   (os_prefix=new/)
```

`config.txt` 상단 구조:

```ini
[all]
os_prefix=current/

[tryboot]
os_prefix=new/
```

→ 펌웨어는 `os_prefix + overlays/` 에서 오버레이를 찾는다. 그래서 **양쪽 모두**에 넣어야
일반 부팅과 tryboot 둘 다에서 디스플레이가 뜬다.

파일 검증:
```bash
md5sum /boot/firmware/current/overlays/waveshare-35dpi-5b.dtbo
# 기대값: ec0dae463e40becc7e9124b97e7537fb
```

---

## config.txt 에 필요한 줄 ✅

`[all]` 섹션에:

```ini
dtparam=i2c_arm=on            # 터치 컨트롤러(i2c) 버스
dtoverlay=waveshare-35dpi-5b  # 디스플레이 + 터치 오버레이
```

전체 스니펫은 [`config/config.txt.snippet`](../config/config.txt.snippet) 참고.

---

## 자동 복구 (권장)

```bash
sudo ./scripts/provision.sh
sudo reboot
```

`provision.sh` 는:
- `overlays/waveshare-35dpi-5b.dtbo` 를 존재하는 모든 overlays 디렉터리에 복사
- `config.txt` 를 백업(`config.txt.pocketterm.bak.<날짜>`)한 뒤 필요한 줄을 중복 없이 주입

## 수동 복구 (스크립트 없이)

```bash
# 1) 오버레이 복사
sudo cp overlays/waveshare-35dpi-5b.dtbo /boot/firmware/current/overlays/
sudo cp overlays/waveshare-35dpi-5b.dtbo /boot/firmware/new/overlays/

# 2) config.txt 편집 — [all] 섹션에 아래 두 줄 확인/추가
sudo nano /boot/firmware/config.txt
#   dtparam=i2c_arm=on
#   dtoverlay=waveshare-35dpi-5b

# 3) 재부팅
sudo reboot
```

---

## 검증

재부팅 후:

```bash
# 디스플레이 커넥터 (DPI 패널이 잡히는지)
ls /sys/class/drm/
for s in /sys/class/drm/card*/status; do echo "$s $(cat $s)"; done

# 터치 입력장치
cat /proc/bus/input/devices | grep -iE "Name=|Handlers="

# 라이브 디바이스트리에 오버레이(터치 노드)가 적용됐는지
sudo find /proc/device-tree -iname '*ft6236*' -o -iname '*gt911*' -o -iname '*goodix*'
```

## 트러블슈팅

| 증상 | 원인/조치 |
|------|-----------|
| 파일·config 다 있는데 화면/터치 없음 | **파일 넣고 재부팅 안 함.** `sudo reboot` |
| 재부팅해도 오버레이 미적용 | 오버레이가 `current/overlays/` 가 아니라 없는 `overlays/` 에만 있음. 위치 재확인 |
| 화면은 되는데 터치만 안 됨 | `dtparam=i2c_arm=on` 누락, 또는 터치가 USB 모델인데 케이블 미연결 |
| 터치는 되는데 화면만 안 됨 | 터치가 USB 경로일 수 있음. 디스플레이 DPI 배선/오버레이 확인 |
| 오버레이 로드 로그 확인 | 이 펌웨어는 런타임 오버레이 로그를 남기지 않음. DT/입력장치 존재로 판단 |
