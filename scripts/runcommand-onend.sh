#!/bin/bash
# runcommand-onend.sh: RetroPie's runcommand runs this after every game.
# install.sh links it in as /opt/retropie/configs/all/runcommand-onend.sh.
# Stops counting the game's time; does nothing unless arcade-profiles is
# enforcing (see runcommand-onstart.sh).
[[ "$ARCADE_PROFILES_ENFORCED" == 1 ]] || exit 0

REPO_DIR="${PI_ARCADE_DIR:-/home/pi/pi-arcade}"
PYTHONPATH="$REPO_DIR/src" python3 -m arcade_profiles.gate_console end
