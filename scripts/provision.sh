#!/usr/bin/env bash
# =====================================================================
# PocketTerm 35 provisioning
# 라즈베리파이 5 (Ubuntu) 에서 실행. 디스플레이가 날아갔을 때 이걸로 복구한다.
#
# 하는 일:
#   1) waveshare-35dpi-5b.dtbo 를 부팅 오버레이 디렉터리에 복사
#   2) /boot/firmware/config.txt 에 필요한 dtoverlay/dtparam 줄을 idempotent 하게 주입
#   3) (옵션) 터치 -> 트랙패드 변환 서비스 설치
#
# 사용법 (파이 위에서):
#   sudo ./scripts/provision.sh              # 디스플레이 오버레이만
#   sudo ./scripts/provision.sh --trackpad   # 트랙패드 서비스까지 설치
#
# 이 스크립트는 이 저장소 루트 기준 상대경로를 쓴다. 저장소 어디서 실행해도 된다.
# =====================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FW_DIR="/boot/firmware"
CONFIG_TXT="${FW_DIR}/config.txt"
OVERLAY_SRC="${REPO_DIR}/overlays/waveshare-35dpi-5b.dtbo"
OVERLAY_NAME="waveshare-35dpi-5b.dtbo"
INSTALL_TRACKPAD=0

for arg in "$@"; do
  case "$arg" in
    --trackpad) INSTALL_TRACKPAD=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "root 권한 필요: sudo $0 $*" >&2
  exit 1
fi

log() { printf '\033[1;32m[provision]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------------
# 0. 사전 점검
# ---------------------------------------------------------------------
if [[ ! -f "$OVERLAY_SRC" ]]; then
  echo "오버레이 원본을 못 찾음: $OVERLAY_SRC" >&2
  exit 1
fi
if [[ ! -d "$FW_DIR" ]]; then
  echo "$FW_DIR 없음. 이 스크립트는 라즈베리파이(Ubuntu) 위에서 실행해야 한다." >&2
  exit 1
fi

# ---------------------------------------------------------------------
# 1. 오버레이 파일 배치
#
# 이 Ubuntu 이미지는 A/B tryboot 레이아웃이라 오버레이가
#   /boot/firmware/current/overlays/  (일반 부팅, os_prefix=current/)
#   /boot/firmware/new/overlays/      (tryboot, os_prefix=new/)
# 에 있어야 한다. 그냥 /boot/firmware/overlays/ 는 이 이미지엔 존재하지 않는다.
# 존재하는 overlays 디렉터리 전부에 복사한다(레이아웃이 다른 이미지도 커버).
# ---------------------------------------------------------------------
copied=0
for d in "${FW_DIR}"/overlays "${FW_DIR}"/current/overlays "${FW_DIR}"/new/overlays; do
  if [[ -d "$d" ]]; then
    install -m 0644 "$OVERLAY_SRC" "${d}/${OVERLAY_NAME}"
    log "오버레이 복사: ${d}/${OVERLAY_NAME}"
    copied=1
  fi
done
if [[ $copied -eq 0 ]]; then
  warn "overlays 디렉터리를 못 찾음. ${FW_DIR}/overlays 를 만들어 복사한다."
  install -d -m 0755 "${FW_DIR}/overlays"
  install -m 0644 "$OVERLAY_SRC" "${FW_DIR}/overlays/${OVERLAY_NAME}"
fi

# ---------------------------------------------------------------------
# 2. config.txt 주입 (idempotent)
# ---------------------------------------------------------------------
ensure_line() {
  # ensure_line <파일> <정확히-일치시킬-줄>
  local file="$1" line="$2"
  if grep -qxF "$line" "$file"; then
    log "이미 존재: $line"
  else
    printf '%s\n' "$line" >>"$file"
    log "추가함: $line"
  fi
}

if [[ ! -f "$CONFIG_TXT" ]]; then
  echo "$CONFIG_TXT 없음" >&2; exit 1
fi
cp -a "$CONFIG_TXT" "${CONFIG_TXT}.pocketterm.bak.$(date +%Y%m%d-%H%M%S)"
log "config.txt 백업 생성"

ensure_line "$CONFIG_TXT" "dtparam=i2c_arm=on"
ensure_line "$CONFIG_TXT" "dtoverlay=waveshare-35dpi-5b"

# ---------------------------------------------------------------------
# 3. (옵션) 트랙패드 서비스
# ---------------------------------------------------------------------
if [[ $INSTALL_TRACKPAD -eq 1 ]]; then
  log "트랙패드 서비스 설치 위임 -> scripts/install-trackpad.sh"
  "${REPO_DIR}/scripts/install-trackpad.sh"
fi

echo
log "완료. 변경을 적용하려면 재부팅: sudo reboot"
log "재부팅 후 확인:"
echo "    ls /sys/class/drm/                 # 디스플레이 커넥터"
echo "    cat /proc/bus/input/devices        # 터치 입력장치"
