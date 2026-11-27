#!/bin/bash
# arcade-session.sh — RetroPie's autostart.sh runs this in place of
# `emulationstation`. install.sh puts it there.
#
# arcade-profiles.enforce off (config/cabinet.json, or the owner's setting
# from their computer): start EmulationStation exactly as before, and when it
# quits drop to the console as before. On: show the sign-in screen, then
# EmulationStation; when EmulationStation quits, the next player signs in.
# The flag is read again each time EmulationStation quits, both ways, so the
# owner turning it on or off from their computer takes effect at the next quit
# with no restart of the cabinet.
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

# Off: EmulationStation as before profiles. When it quits, carry on only if
# the flag was turned on meanwhile; otherwise end here with its exit status.
plain_emulationstation() {
  emulationstation "$@"
  local status=$?
  enforce_on || exit "$status"
}

enforce_on || plain_emulationstation "$@"

[[ -f "$CONSOLE_FONT" ]] && setfont "$CONSOLE_FONT" 2>/dev/null

while true; do
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
  plain_emulationstation "$@"
done
