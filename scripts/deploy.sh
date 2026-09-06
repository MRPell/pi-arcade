#!/usr/bin/env bash
# deploy.sh — Runs on your Mac.
# Syncs the project to the Pi and optionally triggers the installer.

set -euo pipefail

PI_HOST="${PI_HOST:-pi@raspberrypi.local}"
PI_DIR="${PI_DIR:-/home/pi/pi-arcade}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { echo "[deploy] $*"; }

log "Deploying to $PI_HOST:$PI_DIR"

rsync -avz --progress \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'roms' \
  "$REPO_ROOT/" \
  "$PI_HOST:$PI_DIR/"

log "Deploy complete."

if [[ "${1:-}" == "--install" ]]; then
  log "Running installer on Pi..."
  ssh "$PI_HOST" "sudo bash $PI_DIR/scripts/install.sh"
fi
