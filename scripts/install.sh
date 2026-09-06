#!/usr/bin/env bash
# install.sh — Runs on the Raspberry Pi.
# Installs dependencies, configures uinput, deploys and enables the GPIO daemon,
# and installs lr-mame2003-plus via RetroPie-Setup if not already present.
#
# Usage: bash /home/pi/pi-arcade/scripts/install.sh

set -euo pipefail

REPO_DIR="/home/pi/pi-arcade"
ROMS_DIR="/home/pi/RetroPie/roms/mame-libretro"
SERVICE_NAME="pi-arcade-gpio"
SERVICE_SRC="$REPO_DIR/systemd/pi-arcade-gpio.service"
SERVICE_DST="/etc/systemd/system/pi-arcade-gpio.service"

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
# 4. RetroPie / MAME
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

log "Installing lr-mame2003-plus via RetroPie-Setup (this takes several minutes)..."
__nodialog=1 bash "$RETROPIE_PACKAGES" lr-mame2003-plus depends
__nodialog=1 bash "$RETROPIE_PACKAGES" lr-mame2003-plus install_bin
__nodialog=1 bash "$RETROPIE_PACKAGES" lr-mame2003-plus configure

# ------------------------------------------------------------------ #
# 5. ROM directory
# ------------------------------------------------------------------ #
if [[ ! -d "$ROMS_DIR" ]]; then
  log "Creating MAME ROM directory: $ROMS_DIR"
  mkdir -p "$ROMS_DIR"
  chown pi:pi "$ROMS_DIR"
fi

# ------------------------------------------------------------------ #
# 6. Done
# ------------------------------------------------------------------ #
cat <<'EOF'

----------------------------------------------------------------------
Installation complete.

Next steps:
  1. Wire up the hardware (see docs/hardware-setup.md)
  2. Verify config/gpio_map.json matches your actual GPIO pins
  3. Copy MAME ROMs to: /home/pi/RetroPie/roms/mame-libretro/
     See docs/games.md for the exact ROM filenames.
  4. Reboot the Pi: sudo reboot
  5. On first boot into RetroPie, configure the controller when prompted
     (move the joystick and press buttons as shown on screen)

GPIO daemon log:
  journalctl -u pi-arcade-gpio -f
----------------------------------------------------------------------
EOF
