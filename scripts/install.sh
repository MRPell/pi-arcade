#!/usr/bin/env bash
# install.sh — Runs on the Raspberry Pi.
# Installs dependencies, configures uinput, deploys and enables the GPIO daemon,
# installs the RetroArch controller profiles, and installs the MAME, Sega
# Genesis, NES and SNES libretro cores via RetroPie-Setup if not already present.
#
# Usage: bash /home/pi/pi-arcade/scripts/install.sh

set -euo pipefail

REPO_DIR="/home/pi/pi-arcade"
MAME_ROMS_DIR="/home/pi/RetroPie/roms/mame-libretro"
MEGADRIVE_ROMS_DIR="/home/pi/RetroPie/roms/megadrive"
NES_ROMS_DIR="/home/pi/RetroPie/roms/nes"
SNES_ROMS_DIR="/home/pi/RetroPie/roms/snes"
SERVICE_NAME="pi-arcade-gpio"
SERVICE_SRC="$REPO_DIR/systemd/pi-arcade-gpio.service"
SERVICE_DST="/etc/systemd/system/pi-arcade-gpio.service"
AUTOCONFIG_SRC="$REPO_DIR/config/retroarch-autoconfig"
AUTOCONFIG_DST="/opt/retropie/configs/all/retroarch/autoconfig"

log() { echo "[install] $*"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
  fi
}

require_root

# ------------------------------------------------------------------ #
# 1. System packages
# ------------------------------------------------------------------ #
log "Updating package list..."
apt-get update -qq

log "Installing system dependencies..."
apt-get install -y --no-install-recommends \
  python3-pip \
  python3-dev \
  python3-rpi.gpio \
  python3-evdev \
  git

# ------------------------------------------------------------------ #
# 2. uinput kernel module
# ------------------------------------------------------------------ #
log "Enabling uinput module..."
modprobe uinput
# Persist across reboots
if ! grep -q '^uinput' /etc/modules; then
  echo 'uinput' >> /etc/modules
fi
# Allow non-root uinput access (daemon runs as root anyway, but just in case)
chmod 660 /dev/uinput || true

# ------------------------------------------------------------------ #
# 3. GPIO daemon systemd service
# ------------------------------------------------------------------ #
log "Installing GPIO daemon systemd service..."
cp "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
log "GPIO daemon started. Status:"
systemctl is-active "$SERVICE_NAME" && log "  active" || log "  FAILED — check: journalctl -u $SERVICE_NAME"

# ------------------------------------------------------------------ #
# 3b. RetroArch controller profile for the 2nd virtual pad
# ------------------------------------------------------------------ #
# The daemon's player2_start chord emits Start on "Pi Arcade Controller P2".
# Without this autoconfig RetroArch does not know that pad's Start button, so
# the chord never reaches MAME as 2-Player Start.
if [[ -d "$AUTOCONFIG_SRC" && -d "$AUTOCONFIG_DST" ]]; then
  log "Installing RetroArch autoconfig profiles..."
  cp "$AUTOCONFIG_SRC"/*.cfg "$AUTOCONFIG_DST"/
  chown pi:pi "$AUTOCONFIG_DST"/*.cfg
fi

# ------------------------------------------------------------------ #
# 4. RetroPie emulator cores
# ------------------------------------------------------------------ #
# retropie_packages.sh is the non-interactive entrypoint. retropie_setup.sh is
# the whiptail GUI wrapper — it always runs post_update/gui_setup first and
# hangs on /dev/tty when invoked over SSH without a controlling terminal.
RETROPIE_PACKAGES="/home/pi/RetroPie-Setup/retropie_packages.sh"
if [[ ! -f "$RETROPIE_PACKAGES" ]]; then
  log "RetroPie-Setup not found. Cloning..."
  git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git /home/pi/RetroPie-Setup
  chown -R pi:pi /home/pi/RetroPie-Setup
fi

EMULATOR_CORES=(lr-mame2003-plus lr-genesis-plus-gx lr-fceumm lr-snes9x2010)

log "Installing emulator cores via RetroPie-Setup (this takes several minutes)..."
for core in "${EMULATOR_CORES[@]}"; do
  log "  Installing $core..."
  __nodialog=1 bash "$RETROPIE_PACKAGES" "$core" depends
  __nodialog=1 bash "$RETROPIE_PACKAGES" "$core" install_bin
  __nodialog=1 bash "$RETROPIE_PACKAGES" "$core" configure
done

# The ROMs use No-Intro names, which lr-fbneo's console subsystems reject
# (they want FBNeo romset names like md_tjam.zip). Picking a "default emulator
# for system" in the runcommand menu rewrites these, so re-pin them here.
declare -A SYSTEM_DEFAULTS=(
  [megadrive]=lr-genesis-plus-gx
  [nes]=lr-fceumm
  [snes]=lr-snes9x2010
)
for system in "${!SYSTEM_DEFAULTS[@]}"; do
  emulators_cfg="/opt/retropie/configs/$system/emulators.cfg"
  if [[ -f "$emulators_cfg" ]]; then
    log "Setting $system default emulator to ${SYSTEM_DEFAULTS[$system]}"
    sed -i "s/^default = .*/default = \"${SYSTEM_DEFAULTS[$system]}\"/" "$emulators_cfg"
  fi
done

# ------------------------------------------------------------------ #
# 5. ROM directories
# ------------------------------------------------------------------ #
for roms_dir in "$MAME_ROMS_DIR" "$MEGADRIVE_ROMS_DIR" "$NES_ROMS_DIR" "$SNES_ROMS_DIR"; do
  if [[ ! -d "$roms_dir" ]]; then
    log "Creating ROM directory: $roms_dir"
    mkdir -p "$roms_dir"
    chown pi:pi "$roms_dir"
  fi
done

# ------------------------------------------------------------------ #
# 6. Keyboard-only ports (EmulationStation "Ports" menu)
# ------------------------------------------------------------------ #
# These games only read the keyboard, so each launch goes through
# src/keybridge.py, which turns the panel's virtual gamepad into keys from
# config/ports/<id>/keymap.json. keybridge runs as pi under runcommand, so the
# input group needs write access to /dev/uinput.
cat > /etc/udev/rules.d/99-pi-arcade-uinput.rules <<'EOF'
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF
udevadm control --reload-rules
udevadm trigger --name-match=uinput

apt-get -o Acquire::Check-Valid-Until=false install -y --no-install-recommends lbreakout2

# Space Cadet Pinball: open-source rebuild of the Full Tilt! Pinball table.
# Built from source (not in apt). The game data (CADET.DAT and its sounds) is
# not redistributable — copy it from your own copy into PINBALL_DATA_DIR.
PINBALL_SRC="/home/pi/SpaceCadetPinball"
PINBALL_REV="cb9b7b8"
PINBALL_BIN="$PINBALL_SRC/bin/SpaceCadetPinball"
PINBALL_DATA_DIR="/home/pi/.local/share/SpaceCadetPinball"
if [[ ! -x "$PINBALL_BIN" ]]; then
  log "Building Space Cadet Pinball (~20 min on a Pi 3B)..."
  apt-get -o Acquire::Check-Valid-Until=false install -y --no-install-recommends \
    cmake libsdl2-dev libsdl2-mixer-dev
  if [[ ! -d "$PINBALL_SRC/.git" ]]; then
    sudo -u pi git clone https://github.com/k4zmu2a/SpaceCadetPinball.git "$PINBALL_SRC"
  fi
  sudo -u pi git -C "$PINBALL_SRC" fetch -q origin
  sudo -u pi git -C "$PINBALL_SRC" checkout -q "$PINBALL_REV"
  sudo -u pi cmake -S "$PINBALL_SRC" -B "$PINBALL_SRC/build" -DCMAKE_BUILD_TYPE=Release
  sudo -u pi make -C "$PINBALL_SRC/build" -j2
fi
install -d -o pi -g pi "$PINBALL_DATA_DIR"
# Fullscreen with no menu bar; seeded once so in-game changes are kept.
if [[ ! -f "$PINBALL_DATA_DIR/imgui_pb.ini" ]]; then
  install -o pi -g pi -m 644 "$REPO_DIR/config/ports/spacecadetpinball/imgui_pb.ini" "$PINBALL_DATA_DIR/"
fi

PORTS_ROMS_DIR="/home/pi/RetroPie/roms/ports"
mkdir -p "$PORTS_ROMS_DIR"
chown pi:pi "$PORTS_ROMS_DIR"

# id|menu title|command
PORTS=(
  "lbreakout2|LBreakout2|/usr/games/lbreakout2"
  "spacecadetpinball|Space Cadet Pinball|$PINBALL_BIN"
)
for entry in "${PORTS[@]}"; do
  IFS='|' read -r port_id port_title port_cmd <<< "$entry"
  log "Registering port $port_title"
  launcher="$PORTS_ROMS_DIR/$port_title.sh"
  cat > "$launcher" <<EOF
#!/bin/bash
"/opt/retropie/supplementary/runcommand/runcommand.sh" 0 _PORT_ "$port_id" ""
EOF
  chmod +x "$launcher"
  chown pi:pi "$launcher"

  port_conf_dir="/opt/retropie/configs/ports/$port_id"
  mkdir -p "$port_conf_dir"
  cat > "$port_conf_dir/emulators.cfg" <<EOF
$port_id = "python3 $REPO_DIR/src/keybridge.py $REPO_DIR/config/ports/$port_id/keymap.json -- $port_cmd"
default = "$port_id"
EOF
  chown -R pi:pi "$port_conf_dir"
done

# LBreakout2 starts windowed by default; seed a fullscreen config only if the
# player has none yet, so later in-game settings are kept.
if [[ ! -f /home/pi/.lgames/lbreakout2.conf ]]; then
  install -d -o pi -g pi /home/pi/.lgames
  install -o pi -g pi -m 644 "$REPO_DIR/config/ports/lbreakout2/lbreakout2.conf" /home/pi/.lgames/lbreakout2.conf
fi

# EmulationStation lists a system only if es_systems.cfg has it. RetroPie adds
# "ports" when it installs one of its own port packages; do the same here.
ES_SYSTEMS="/etc/emulationstation/es_systems.cfg"
if ! xmlstarlet sel -t -c "/systemList/system[name='ports']" "$ES_SYSTEMS" >/dev/null; then
  log "Adding the Ports system to EmulationStation"
  xmlstarlet ed -L \
    -s /systemList -t elem -n system \
    -s '/systemList/system[last()]' -t elem -n name -v ports \
    -s '/systemList/system[last()]' -t elem -n fullname -v Ports \
    -s '/systemList/system[last()]' -t elem -n path -v "$PORTS_ROMS_DIR" \
    -s '/systemList/system[last()]' -t elem -n extension -v '.sh .SH' \
    -s '/systemList/system[last()]' -t elem -n command -v 'bash %ROM%' \
    -s '/systemList/system[last()]' -t elem -n platform -v pc \
    -s '/systemList/system[last()]' -t elem -n theme -v ports \
    "$ES_SYSTEMS"
fi

# ------------------------------------------------------------------ #
# 7. Arcade profiles: sign in with a button combo
# ------------------------------------------------------------------ #
# EmulationStation is started through scripts/arcade-session.sh. With
# arcade-profiles.enforce off in config/cabinet.json (the default) it just
# runs EmulationStation as before; on, players sign in first.
AUTOSTART="/opt/retropie/configs/all/autostart.sh"
if [[ -f "$AUTOSTART" ]] && ! grep -q 'arcade-session.sh' "$AUTOSTART"; then
  if grep -q '^emulationstation #auto$' "$AUTOSTART"; then
    log "Starting EmulationStation through arcade-session.sh"
    cp -n "$AUTOSTART" "$AUTOSTART.pre-profiles"
    sed -i "s|^emulationstation #auto\$|bash $REPO_DIR/scripts/arcade-session.sh #auto|" "$AUTOSTART"
  else
    log "WARNING: $AUTOSTART has no 'emulationstation #auto' line; arcade profiles not hooked in"
  fi
fi

# Hours and time limits: runcommand runs these before and after every game.
# They do nothing unless EmulationStation was started by arcade-session.sh
# with the flag on. Linked, so make deploy updates them.
for hook in runcommand-onstart.sh runcommand-onend.sh; do
  hook_dst="/opt/retropie/configs/all/$hook"
  if [[ -e "$hook_dst" && ! -L "$hook_dst" ]]; then
    log "WARNING: $hook_dst already exists; hours and time limits not hooked in"
  else
    log "Linking $hook for arcade profiles"
    ln -sfn "$REPO_DIR/scripts/$hook" "$hook_dst"
    chown -h pi:pi "$hook_dst"
  fi
done

# ------------------------------------------------------------------ #
# 8. Done
# ------------------------------------------------------------------ #
cat <<'EOF'

----------------------------------------------------------------------
Installation complete.

Next steps:
  1. Wire up the hardware (see docs/hardware-setup.md)
  2. Verify config/gpio_map.json matches your actual GPIO pins
  3. Copy MAME ROMs to: /home/pi/RetroPie/roms/mame-libretro/
     See docs/games.md for the exact ROM filenames.
  4. Copy Sega Genesis ROMs to: /home/pi/RetroPie/roms/megadrive/
     See docs/sega-genesis.md for the game list and controls.
  5. Copy NES ROMs to: /home/pi/RetroPie/roms/nes/
     and SNES ROMs to: /home/pi/RetroPie/roms/snes/
     See docs/nes.md and docs/snes.md for the game lists and controls.
  6. Reboot the Pi: sudo reboot
  7. On first boot into RetroPie, configure the controller when prompted
     (move the joystick and press buttons as shown on screen)

GPIO daemon log:
  journalctl -u pi-arcade-gpio -f
----------------------------------------------------------------------
EOF
