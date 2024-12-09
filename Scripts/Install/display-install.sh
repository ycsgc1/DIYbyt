#!/bin/bash

# Exit on error, but allow us to handle it
set +e

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

# Function to select from options
selectN() {
    args=("${@}")
    if [[ ${args[0]} = "0" ]]; then
        OFFSET=0
    else
        OFFSET=1
    fi
    for ((i=0; i<$#; i++)); do
        echo $((i+$OFFSET)). ${args[$i]}
    done
    echo
    REPLY=""
    let LAST=$#+$OFFSET-1
    while :
    do
        echo -n "SELECT $OFFSET-$LAST: "
        read
        if [[ $REPLY -ge $OFFSET ]] && [[ $REPLY -le $LAST ]]; then
            let RESULT=$REPLY-$OFFSET
            return $RESULT
        fi
    done
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root"
fi

# Display welcome message
echo "This script installs the DIYbyt Display Service with"
echo "Adafruit RGB Matrix Bonnet/HAT support for Raspberry Pi."
echo "Steps include:"
echo "- Update package index files"
echo "- Install prerequisite software"
echo "- Install RGB matrix driver software"
echo "- Configure system settings"
echo "- Set up Python environment"
echo "- Install DIYbyt service"
echo
echo "EXISTING INSTALLATION, IF ANY, WILL BE OVERWRITTEN."
echo
echo -n "CONTINUE? [y/n] "
read REPLY
if [[ ! "$REPLY" =~ ^[yY]$ ]]; then
    echo "Canceled."
    exit 0
fi

# Initialize variables
INTERFACE_TYPE=0
INSTALL_RTC=0
QUALITY_MOD=0

# Get interface type
INTERFACES=( \
    "Adafruit RGB Matrix Bonnet" \
    "Adafruit RGB Matrix HAT + RTC" \
)

echo
echo "Select interface board type:"
selectN "${INTERFACES[@]}"
INTERFACE_TYPE=$?

# Verify selection was successful
if [ $? -ne 0 ]; then
    error "Interface selection failed"
fi

# Get RTC preference if using HAT
if [ $INTERFACE_TYPE -eq 1 ]; then
    while true; do
        echo
        echo -n "Install realtime clock support? [y/n] "
        read REPLY
        if [[ "$REPLY" =~ ^[yY]$ ]]; then
            INSTALL_RTC=1
            break
        elif [[ "$REPLY" =~ ^[nN]$ ]]; then
            INSTALL_RTC=0
            break
        else
            echo "Please answer y or n"
        fi
    done
fi

# Get quality/convenience preference
QUALITY_OPTS=( \
    "Quality (disables sound, requires soldering)" \
    "Convenience (sound on, no soldering)" \
)

echo
echo "Now you must choose between QUALITY and CONVENIENCE."
echo
echo "QUALITY: best output from the LED matrix requires"
echo "commandeering hardware normally used for sound, plus"
echo "some soldering.  If you choose this option, there will"
echo "be NO sound from the audio jack or HDMI (USB audio"
echo "adapters will work and sound best anyway), AND you"
echo "must SOLDER a wire between GPIO4 and GPIO18 on the"
echo "Bonnet or HAT board."
echo
echo "CONVENIENCE: sound works normally, no extra soldering."
echo "Images on the LED matrix are not quite as steady, but"
echo "maybe OK for most uses.  If eager to get started, use"
echo "'CONVENIENCE' for now, you can make the change and"
echo "reinstall using this script later!"
echo
echo "What is thy bidding?"
selectN "${QUALITY_OPTS[@]}"
QUALITY_MOD=$?

# Verify selection was successful
if [ $? -ne 0 ]; then
    error "Quality mode selection failed"
fi

# Verify selections before continuing
echo
echo "Interface board type: ${INTERFACES[$INTERFACE_TYPE]}"
if [ $INTERFACE_TYPE -eq 1 ]; then
    echo "Install RTC support: $([ $INSTALL_RTC -eq 1 ] && echo "Yes" || echo "No")"
fi
echo "Optimize: ${QUALITY_OPTS[$QUALITY_MOD]}"
if [ $QUALITY_MOD -eq 0 ]; then
    echo "Reminder: you must SOLDER a wire between GPIO4"
    echo "and GPIO18, and internal sound is DISABLED!"
fi
echo
echo -n "CONTINUE? [y/n] "
read REPLY
if [[ ! "$REPLY" =~ ^[yY]$ ]]; then
    echo "Canceled."
    exit 0
fi

# Get server configuration
SERVER_URL=$(get_server_config)
log "Using server URL: ${SERVER_URL}"

# Install required system packages
log "Installing required packages..."
apt-get update
apt-get install -y python3-pip python3-dev python3-pil git curl unzip python3-venv

# Create directories
log "Creating directories..."
mkdir -p "${PROGRAMS_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${MATRIX_DIR}"
mkdir -p "${VENV_DIR}"

# Create log file if it doesn't exist
touch "${LOG_DIR}/display.log"

# Install RGB Matrix with configuration
install_rgb_matrix "${MATRIX_DIR}" "${INTERFACE_TYPE}" "${QUALITY_MOD}" "${INSTALL_RTC}"

# Configure CPU isolation
configure_cpu_isolation

# Configure virtual environment
log "Setting up Python virtual environment..."
python3 -m venv "${VENV_DIR}"

# Install Python dependencies in virtual environment
log "Installing Python dependencies in virtual environment..."
"${VENV_DIR}/bin/pip" install requests pillow

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
Environment=PATH=${VENV_DIR}/bin:$PATH

# Service execution
ExecStart=${VENV_DIR}/bin/python /usr/local/bin/diybyt-display

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
chown -R $ACTUAL_USER:$(id -g $ACTUAL_USER) "${MATRIX_DIR}"

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
- Virtual Environment: ${VENV_DIR}

Commands:
- Check service status: systemctl status diybyt-display
- View logs: journalctl -u diybyt-display -f
- View local logs: tail -f ${LOG_DIR}/display.log
- Restart service: systemctl restart diybyt-display
- Stop service: systemctl stop diybyt-display

Configuration Summary:
- Interface Type: ${INTERFACES[$INTERFACE_TYPE]}
- RTC Support: $([ $INSTALL_RTC -eq 1 ] && echo "Enabled" || echo "Disabled")
- Display Mode: ${QUALITY_OPTS[$QUALITY_MOD]}

Important Notes:
$(if [ $QUALITY_MOD -eq 0 ]; then
echo "- Quality mode is enabled: Audio is disabled and you must solder a wire between GPIO4 and GPIO18"
else
echo "- Convenience mode is enabled: Audio is enabled, no soldering required"
fi)
$(if [ $INSTALL_RTC -eq 1 ]; then
echo "- RTC has been enabled but time must be set up using 'date' and 'hwclock' commands"
echo "- See: https://learn.adafruit.com/adding-a-real-time-clock-to-raspberry-pi/set-rtc-time"
fi)

Note: A reboot is recommended for all changes to take effect.
Would you like to reboot now? [y/n] 
EOL

read REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    log "Rebooting system..."
    reboot
else
    log "Please remember to reboot your system for all changes to take effect."
fi