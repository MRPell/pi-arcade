#!/bin/bash
# runcommand-onstart.sh: RetroPie's runcommand runs this before every game.
# install.sh links it in as /opt/retropie/configs/all/runcommand-onstart.sh.
#
# Only EmulationStation started by arcade-session.sh with arcade-profiles.enforce
# on carries ARCADE_PROFILES_ENFORCED=1; otherwise this does nothing and games
# start as before profiles.
#
# runcommand ignores this script's exit status, so a refused game is stopped by
# ending runcommand ($PPID) before it starts the emulator; EmulationStation then
# carries on. A gate failure also refuses the game, so a crash never lets play
# round the rules.
[[ "$ARCADE_PROFILES_ENFORCED" == 1 ]] || exit 0

REPO_DIR="${PI_ARCADE_DIR:-/home/pi/pi-arcade}"
PYTHONPATH="$REPO_DIR/src" python3 -m arcade_profiles.gate_console start "$PPID" || kill -TERM "$PPID"
