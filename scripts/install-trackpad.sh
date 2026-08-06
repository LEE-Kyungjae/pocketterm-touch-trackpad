#!/usr/bin/env bash
# =====================================================================
# 터치 -> 트랙패드 브리지를 시스템 서비스로 설치.
# 파이 위에서 root 로 실행.
# =====================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="/opt/pocketterm35"
SERVICE="pocketterm-trackpad.service"

if [[ $EUID -ne 0 ]]; then
  echo "root 권한 필요: sudo $0" >&2
  exit 1
fi

log() { printf '\033[1;32m[trackpad]\033[0m %s\n' "$*"; }

# 1. 의존성
log "python3-evdev 설치 확인"
if ! python3 -c "import evdev" 2>/dev/null; then
  apt-get update -y
  apt-get install -y python3-evdev
fi

# 2. 스크립트 배치
install -d -m 0755 "$DEST"
install -m 0755 "${REPO_DIR}/trackpad/touchpad_bridge.py" "${DEST}/touchpad_bridge.py"
log "브리지 설치: ${DEST}/touchpad_bridge.py"

# 3. systemd 유닛
install -m 0644 "${REPO_DIR}/trackpad/${SERVICE}" "/etc/systemd/system/${SERVICE}"
systemctl daemon-reload
systemctl enable --now "$SERVICE"
log "서비스 활성화 완료: $SERVICE"
log "상태 확인:  systemctl status $SERVICE"
log "로그 확인:  journalctl -u $SERVICE -f"
