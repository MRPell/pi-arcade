#!/bin/bash
# arcade-session.sh — RetroPie's autostart.sh runs this in place of
# `emulationstation`. install.sh puts it there.
#
# arcade-profiles.enforce off (config/cabinet.json): start EmulationStation
# exactly as before. On: show the sign-in screen, then EmulationStation; when
# EmulationStation quits, the next player signs in. The flag is read again each
# time round, so turning it off takes effect the next time EmulationStation quits.
#
# EmulationStation started here with the flag on gets ARCADE_PROFILES_ENFORCED=1,
# which the runcommand hooks (runcommand-onstart.sh, -onend.sh) see before each
# game: hours and time limits apply only to that EmulationStation.

REPO_DIR="${PI_ARCADE_DIR:-/home/pi/pi-arcade}"
CABINET_CONFIG="${PI_ARCADE_CABINET_CONFIG:-$REPO_DIR/config/cabinet.json}"
CONSOLE_FONT=/usr/share/consolefonts/Lat15-TerminusBold32x16.psf.gz

enforce_on() {
  PYTHONPATH="$REPO_DIR/src" python3 -m arcade_profiles.flag "$CABINET_CONFIG"
}

if ! enforce_on; then
  exec emulationstation "$@"
fi

[[ -f "$CONSOLE_FONT" ]] && setfont "$CONSOLE_FONT" 2>/dev/null

while enforce_on; do
  # Retry rather than fall through to EmulationStation, so a sign-in failure
  # never becomes a way round it. Turning the flag off ends the retries.
  until PYTHONPATH="$REPO_DIR/src" python3 -m arcade_profiles.signin_console; do
    echo "Sign-in failed; retrying. Logs: journalctl or this console." >&2
    sleep 3
    enforce_on || break 2
  done
  ARCADE_PROFILES_ENFORCED=1 emulationstation "$@"
done

exec emulationstation "$@"
