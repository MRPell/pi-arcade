PI_HOST ?= pi@retropie.local
PI_DIR  ?= /home/pi/pi-arcade

# Push project files to the Pi
deploy:
	PI_HOST=$(PI_HOST) PI_DIR=$(PI_DIR) bash scripts/deploy.sh

# Run the installer on the Pi via SSH (requires deploy first)
install:
	ssh $(PI_HOST) "sudo bash $(PI_DIR)/scripts/install.sh"

# Deploy then install in one step
deploy-install:
	PI_HOST=$(PI_HOST) PI_DIR=$(PI_DIR) bash scripts/deploy.sh --install

# Open an SSH shell on the Pi
ssh:
	ssh $(PI_HOST)

# Tail the GPIO daemon log
logs:
	ssh $(PI_HOST) "journalctl -u pi-arcade-gpio -f"

# Restart the GPIO daemon (useful after editing gpio_map.json)
restart-daemon:
	ssh $(PI_HOST) "sudo systemctl restart pi-arcade-gpio"

# Run the daemon manually in verbose mode for testing
gpio-test:
	ssh $(PI_HOST) "sudo python3 $(PI_DIR)/src/gpio_daemon.py --verbose"

# Check daemon status
status:
	ssh $(PI_HOST) "systemctl status pi-arcade-gpio"

# Run the unit tests (keybridge's need python3-evdev, so run those on the Pi)
test:
	python3 -m unittest discover -s tests -p 'test_[!k]*.py'

# Run every test on the Pi's own Python (3.7) from a throwaway copy in /tmp;
# the cabinet's install is untouched
PI_TEST_DIR ?= /tmp/pi-arcade-test
test-pi:
	rsync -a --delete --exclude .git --exclude roms --exclude '.sim-*' --exclude __pycache__ ./ $(PI_HOST):$(PI_TEST_DIR)/
	ssh $(PI_HOST) "cd $(PI_TEST_DIR) && python3 -m unittest discover -s tests -p 'test_*.py'; s=\$$?; rm -rf $(PI_TEST_DIR); exit \$$s"

# Is the cabinet ready for arcade-profiles.enforce to go on? Read-only.
preflight:
	PI_HOST=$(PI_HOST) PI_DIR=$(PI_DIR) bash scripts/preflight.sh

# Cabinet simulator in the browser, arcade-profiles.enforce on (dev). Its
# cabinet's settings live in SIM_DIR, where make admin-sim changes them.
PORT ?= 21000
SIM_DIR ?= $(CURDIR)/.sim-cabinet
sim:
	python3 -m sim.server --port $(PORT) --cabinet config/cabinet.dev.json --state-dir $(SIM_DIR)

# Same, with the cabinet's shipped config (flag off): boots as before profiles
sim-flag-off:
	python3 -m sim.server --port $(PORT) --cabinet config/cabinet.json --state-dir $(SIM_DIR)

# Arcade profiles admin on this computer: profiles, combos, limits and the
# flag, written to the cabinet over SSH (PI_HOST, PI_DIR)
ADMIN_PORT ?= 21010
admin:
	python3 -m admin.server --port $(ADMIN_PORT) --pi $(PI_HOST) --pi-dir $(PI_DIR)

# The admin pointed at the simulator's cabinet (start make sim first)
admin-sim:
	python3 -m admin.server --port $(ADMIN_PORT) --sim-dir $(SIM_DIR)

.PHONY: test test-pi preflight sim sim-flag-off admin admin-sim deploy install deploy-install ssh logs restart-daemon gpio-test status
