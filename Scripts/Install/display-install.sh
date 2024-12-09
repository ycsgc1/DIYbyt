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
    local server_url="http://localhost:8000"
    
    while true; do
        read -p "Is this being installed on the same machine as the render server? (y/n): " is_local
        case $is_local in
            [Yy]* )
                server_url="http://localhost:8000"
                break
                ;;
            [Nn]* )
                while true; do
                    read -p "Enter the IP address of the render server: " server_ip
                    if [[ $server_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                        server_url="http://${server_ip}:8000"
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

# Function to configure CPU isolation
configure_cpu_isolation() {
    log "Configuring CPU isolation for better display performance..."
    CMDLINE="/boot/cmdline.txt"
    
    # Check if isolcpus is already configured
    if grep -q "isolcpus=" "$CMDLINE"; then
        warn "CPU isolation already configured in $CMDLINE"
        return 0
    }
    
    # Backup original cmdline.txt
    cp "$CMDLINE" "${CMDLINE}.backup"
    
    # Add isolcpus parameter
    sed -i 's/$/ isolcpus=3/' "$CMDLINE"
    
    log "CPU isolation configured - core 3 will be reserved for display updates"
    return 0
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root"
fi

# Get script and repo paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"

if [ -z "${REPO_ROOT}" ]; then
    error "Could not determine repository root directory"
fi

# Get current user (the one who sudo'ed)
ACTUAL_USER=$(who mom likes | awk '{print $1}')

if [ -z "${ACTUAL_USER}" ]; then
    error "Could not determine actual user"
fi

# Base paths
INSTALL_DIR="/opt/DIYbyt"
LOG_DIR="/var/log/diybyt"
PROGRAMS_DIR="${INSTALL_DIR}/star_programs"
MATRIX_DIR="${REPO_ROOT}/rgb-led-matrix-library"

# Get server configuration
SERVER_URL=$(get_server_config)
log "Using server URL: ${SERVER_URL}"

# Install required packages
log "Installing required packages..."
apt-get update
apt-get install -y python3-pip python3-dev python3-pillow git curl unzip

# Create directories
log "Creating directories..."
mkdir -p "${PROGRAMS_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${MATRIX_DIR}"

# Create log file if it doesn't exist
touch "${LOG_DIR}/display.log"

# Download Adafruit RGB Matrix installer to the new location
log "Downloading RGB Matrix installer..."
curl -L https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/rgb-matrix.sh -o "${MATRIX_DIR}/rgb-matrix.sh"
chmod +x "${MATRIX_DIR}/rgb-matrix.sh"

# Change to the matrix directory before running installer
cd "${MATRIX_DIR}"

# Run the Adafruit installer script
log "Running RGB Matrix installer..."
# This will prompt for user input
QUALITY_MOD=0  # Will be set to 1 if user chooses convenience mode
./rgb-matrix.sh
INSTALL_RESULT=$?

# Return to original directory
cd - > /dev/null

# Configure CPU isolation and set reboot flag if needed
NEEDS_REBOOT=0
if configure_cpu_isolation; then
    NEEDS_REBOOT=1
fi

# Configure audio based on quality selection
if [ $QUALITY_MOD -eq 0 ]; then
    log "Configuring audio for quality RGB matrix output..."
    echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
    sudo update-initramfs -u
    NEEDS_REBOOT=1
fi

# Install Python dependencies
log "Installing Python dependencies..."
pip3 install requests pillow

# Copy display script
log "Installing display service..."
cp "${REPO_ROOT}/DIYbyt-Client/src/components/DIYbyt_Display.py" /usr/local/bin/diybyt-display
chmod 755 /usr/local/bin/diybyt-display

# Copy and configure systemd service
log "Setting up systemd service..."
SERVICE_SOURCE="${REPO_ROOT}/DIYbyt-Client/systemd/diybyt-display.service"

if [ -f "${SERVICE_SOURCE}" ]; then
    log "Using existing service file from repository..."
    cp "${SERVICE_SOURCE}" /etc/systemd/system/diybyt-display.service
    
    # Update server URL in the copied service file
    sed -i "s#DIYBYT_SERVER_URL=.*#DIYBYT_SERVER_URL=${SERVER_URL}#g" /etc/systemd/system/diybyt-display.service
else
    warn "Service file not found in repository, creating default service file..."
    cat > /etc/systemd/system/diybyt-display.service << EOL
[Unit]
Description=DIYbyt Display Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/DIYbyt

# Environment variables
Environment=PYTHONUNBUFFERED=1
Environment=DIYBYT_SERVER_URL=${SERVER_URL}
Environment=DIYBYT_PROGRAMS_PATH=/opt/DIYbyt/star_programs

# Service execution
ExecStart=/usr/local/bin/diybyt-display

# Restart configuration
Restart=on-failure
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=append:/var/log/diybyt/display.log
StandardError=append:/var/log/diybyt/display.log

[Install]
WantedBy=multi-user.target
EOL
fi

chmod 644 /etc/systemd/system/diybyt-display.service

# Set proper permissions
log "Setting permissions..."
chmod 750 "${INSTALL_DIR}"
chmod 2775 "${PROGRAMS_DIR}"
chmod 2775 "${LOG_DIR}"
chmod 666 "${LOG_DIR}/display.log"

# Enable and start service
log "Starting service..."
systemctl daemon-reload
systemctl enable diybyt-display
systemctl restart diybyt-display

# Wait a moment for the service to start
sleep 2

# Check service status
if systemctl is-active --quiet diybyt-display; then
    log "Service installed and running successfully!"
else
    error "Service failed to start. Check logs with: journalctl -u diybyt-display -xe"
fi

# Print final instructions
cat << EOL

${GREEN}Installation Complete!${NC}

Important paths:
- Install directory: ${INSTALL_DIR}
- Programs directory: ${PROGRAMS_DIR}
- Logs: ${LOG_DIR}/display.log
- RGB Matrix Library: ${MATRIX_DIR}

Commands:
- Check service status: systemctl status diybyt-display
- View logs: journalctl -u diybyt-display -f
- View local logs: tail -f ${LOG_DIR}/display.log
- Restart service: systemctl restart diybyt-display
- Stop service: systemctl stop diybyt-display

Thank you for installing DIYbyt Display Service!
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