# 01 — 하드웨어 & 환경

## 확인된 사실 ✅ (실제 기기에서 조회)

```
보드   : Raspberry Pi 5 Model B Rev 1.0
OS     : Ubuntu (aarch64)
커널   : Linux 7.0.0-1009-raspi #9-Ubuntu SMP PREEMPT_DYNAMIC (2026-04-13)
호스트 : ze2
계정   : ze2  (sudo 그룹 소속)
펌웨어 : /boot/firmware  (A/B tryboot, os_prefix=current/)
```

디스플레이:
```
Waveshare 3.5" DPI 터치 디스플레이
- 표시(display): DPI (GPIO 병렬 인터페이스)
- 터치(touch)  : 정전식, 컨트롤러 goodix gt911 / ft6236 (i2c, 주소 0x14 / 0x5d)
- 오버레이     : waveshare-35dpi-5b
```

## 접속

기본은 유선/네트워크로 SSH:

```bash
ssh ze2@<PI_IP>
```

- `<PI_IP>` 실제 값과 로그인 비밀번호, 와이파이 자격증명 등 **민감정보는 이 저장소에 넣지 않는다.**
- 개인 메모가 필요하면 저장소 루트에 `SECRETS.local.md` 를 만들어라. `.gitignore` 에 의해
  깃에 올라가지 않는다.

## 터치 입력 경로에 대한 메모 ℹ️

Waveshare 3.5" 계열은 모델에 따라 **터치가 i2c 오버레이로 오는 경우**와
**USB HID로 오는 경우**가 있다. 두 경우의 복구 절차가 다르므로, 복구 시 아래로 판별한다:

```bash
cat /proc/bus/input/devices        # 터치 장치의 이름/버스 확인
# I2c/부트: 위 오버레이(dtoverlay=waveshare-35dpi-5b) 필요
# USB    : 오버레이와 무관하게 꽂으면 인식 (별도 설정 불필요)
```

> 이 저장소의 오버레이 프로비저닝은 **디스플레이(DPI)** 를 위한 것이다.
> 터치가 USB로 들어오는 모델이면 터치는 오버레이 없이도 동작한다.
