#!/bin/bash

# Exit on error
set -e

# Colors for better visibility
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log functions
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Function to get server configuration
get_server_config() {
    local is_local
    local server_url="http://localhost:3001"
    
    while true; do
        read -p "Is this being installed on the same machine as the GUI server? (y/n): " is_local
        case $is_local in
            [Yy]* )
                server_url="http://localhost:3001"
                break
                ;;
            [Nn]* )
                while true; do
                    read -p "Enter the IP address of the GUI server: " server_ip
                    if [[ $server_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                        server_url="http://${server_ip}:3001"
                        break
                    else
                        warn "Invalid IP format. Please try again."
                    fi
                done
                break
                ;;
            * ) echo "Please answer yes (y) or no (n).";;
        esac
    done
    echo "$server_url"
}

# Function to configure audio for RGB matrix
configure_audio() {
    log "Would you like to configure the system for quality RGB matrix output?"
    log "This will disable the default audio device to improve display quality."
    read -p "Configure for quality output? (y/n): " quality_config
    
    if [[ "$quality_config" =~ ^[Yy]$ ]]; then
        log "Configuring system for quality RGB matrix output..."
        echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
        sudo update-initramfs -u
        return 0  # Return true - system needs reboot
    fi
    return 1  # Return false - no reboot needed
}

[Previous installation script content up to the final status check]

# Configure audio if requested
NEEDS_REBOOT=0
if configure_audio; then
    NEEDS_REBOOT=1
fi

# Check service status
if systemctl is-active --quiet diybyt-sync; then
    log "Service installed and running successfully!"
else
    error "Service failed to start. Check logs with: journalctl -u diybyt-sync -xe"
fi

# Print final instructions
cat << EOL

${GREEN}Installation Complete!${NC}

Important paths:
- Install directory: ${INSTALL_DIR}
- Programs directory: ${PROGRAMS_DIR}
- Logs: ${LOG_DIR}/sync.log
- Virtual environment: ${VENV_DIR}

Commands:
- Check service status: systemctl status diybyt-sync
- View logs: journalctl -u diybyt-sync -f
- View local logs: tail -f ${LOG_DIR}/sync.log
- Restart service: systemctl restart diybyt-sync
- Stop service: systemctl stop diybyt-sync

Thank you for installing DIYbyt Sync Service!
EOL

# Handle reboot if needed
if [ $NEEDS_REBOOT -eq 1 ]; then
    echo
    echo "System configuration requires a reboot to take effect."
    read -p "Would you like to reboot now? (y/n): " reboot_now
    if [[ "$reboot_now" =~ ^[Yy]$ ]]; then
        log "Rebooting system..."
        sudo reboot
    else
        log "Please remember to reboot your system for the changes to take effect."
    fi
fi