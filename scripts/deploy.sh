#!/usr/bin/env bash
# deploy.sh — Runs on your Mac.
# Syncs the project to the Pi and optionally triggers the installer.
#   --install  run the installer after syncing
#   --check    change nothing; list the files the Pi's copy lacks or has
#              different, and exit 1 if there are any

set -euo pipefail

PI_HOST="${PI_HOST:-pi@retropie.local}"
PI_DIR="${PI_DIR:-/home/pi/pi-arcade}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { echo "[deploy] $*"; }

EXCLUDES=(
  --exclude '.git'
  --exclude '__pycache__'
  --exclude '*.pyc'
  --exclude '.DS_Store'
  --exclude 'roms'
  --exclude '.sim-*'
)

if [[ "${1:-}" == "--check" ]]; then
  itemized=$(rsync -anc --itemize-changes "${EXCLUDES[@]}" "$REPO_ROOT/" "$PI_HOST:$PI_DIR/")
  differ=$(grep -v '^\.' <<<"$itemized" || true)
  if [[ -n "$differ" ]]; then
    echo "$differ"
    exit 1
  fi
  exit 0
fi

log "Deploying to $PI_HOST:$PI_DIR"

rsync -avz --progress "${EXCLUDES[@]}" \
  "$REPO_ROOT/" \
  "$PI_HOST:$PI_DIR/"

log "Deploy complete."

if [[ "${1:-}" == "--install" ]]; then
  log "Running installer on Pi..."
  ssh "$PI_HOST" "sudo bash $PI_DIR/scripts/install.sh"
fi
