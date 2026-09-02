PI_HOST ?= pi@raspberrypi.local
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

.PHONY: deploy install deploy-install ssh logs restart-daemon gpio-test status
