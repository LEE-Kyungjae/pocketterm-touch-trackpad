# 03 — 와이파이 연결

> ℹ️ 이 문서는 Ubuntu-on-Pi 표준 절차다. 실제 기기의 현재 네트워크 설정 파일은
> 복구 시점에 `ls /etc/netplan/` 로 확인하고 아래에 맞춰 편집한다.

Pi 5는 온보드 Wi-Fi가 있다. **폰 핫스팟은 일반 공유기(AP)와 완전히 동일하게 취급**되므로
SSID/비번만 넣으면 붙는다.

---

## 방법 A — 이미 부팅된 상태에서 (netplan)

Ubuntu 서버 이미지는 netplan을 쓴다. `/etc/netplan/` 의 yaml을 편집:

```bash
ls /etc/netplan/
sudo nano /etc/netplan/50-cloud-init.yaml   # 파일명은 환경마다 다름
```

```yaml
network:
  version: 2
  wifis:
    wlan0:
      dhcp4: true
      access-points:
        "<SSID_또는_핫스팟이름>":
          password: "<와이파이_비번>"
```

적용:
```bash
sudo netplan apply
# 확인
ip -br addr show wlan0
```

> 편집 후에도 안 붙으면 `rfkill list` 로 wlan 이 blocked 인지 확인(`sudo rfkill unblock wifi`).

---

## 방법 B — NetworkManager 를 쓰는 이미지라면

```bash
nmcli radio wifi on
nmcli dev wifi list
sudo nmcli dev wifi connect "<SSID>" password "<비번>"
nmcli -t -f DEVICE,TYPE,STATE dev     # 상태 확인
```

---

## 방법 C — 첫 부팅 전, SD/eMMC 를 다른 PC에 꽂아서 (cloud-init)

이 이미지의 `/boot/firmware/` 에는 cloud-init 파일(`user-data`, `meta-data`, 보통 `network-config`)이
있다. 부팅 파티션(FAT)이라 맥/윈도우에서도 보인다.

`network-config` 예시:
```yaml
version: 2
wifis:
  wlan0:
    dhcp4: true
    access-points:
      "<SSID>":
        password: "<비번>"
```

저장 후 파이에 꽂고 부팅하면 첫 부팅 때 적용된다.

---

## 핫스팟 관련 주의

- **대역**: Pi 5 Wi-Fi는 2.4/5GHz 모두 지원. 5GHz 핫스팟이 지역 채널 문제로 안 잡히면
  핫스팟을 **2.4GHz** 로 바꾸면 확실하다.
- **파이를 핫스팟(AP)으로 만들면서 동시에 와이파이로 인터넷 받기**: 무선칩 1개로 STA+AP
  동시는 제약이 크다. 이럴 땐 **유선으로 인터넷 받고 와이파이로 뿌리거나**, USB Wi-Fi 동글을
  하나 추가하는 게 깔끔하다. (일반적인 "핫스팟에 파이 붙이기"는 방법 A/B/C로 충분)
