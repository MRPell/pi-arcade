#!/usr/bin/env bash
# preflight.sh — Runs on your Mac (make preflight). Is the cabinet ready for
# arcade-profiles.enforce to go on? Changes nothing on the cabinet: it compares
# the cabinet's copy with this checkout, then runs the cabinet's own checks
# (python3 -m arcade_profiles.preflight) with this computer's time zone.
# Exits 1 if anything fails.

set -uo pipefail

PI_HOST="${PI_HOST:-pi@retropie.local}"
PI_DIR="${PI_DIR:-/home/pi/pi-arcade}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# This computer's time zone: the one the owner sets play hours in.
OWNER_TZ="${OWNER_TZ:-$(readlink /etc/localtime | sed 's|.*zoneinfo/||')}"

failed=0

if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$PI_HOST" true 2>/dev/null; then
  echo "FAIL  cabinet: cannot reach $PI_HOST over SSH without a password"
  exit 1
fi
echo "ok    cabinet: $PI_HOST"

if differ=$(PI_HOST="$PI_HOST" PI_DIR="$PI_DIR" bash "$SCRIPT_DIR/deploy.sh" --check 2>&1); then
  echo "ok    deployed: $PI_DIR matches this checkout"
else
  echo "FAIL  deployed: $PI_DIR differs from this checkout in $(wc -l <<<"$differ" | tr -d ' ') files; run make deploy"
  echo "info  the cabinet's own checks run once it has this checkout: make deploy-install, then make preflight"
  exit 1
fi

ssh -o BatchMode=yes "$PI_HOST" \
  "PYTHONPATH=$PI_DIR/src python3 -m arcade_profiles.preflight --timezone '$OWNER_TZ'" || failed=1

exit "$failed"
