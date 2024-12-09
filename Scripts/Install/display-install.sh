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
    fi
    
    # Backup original cmdline.txt
    cp "$CMDLINE" "${CMDLINE}.backup"
    
    # Add isolcpus parameter
    sed -i 's/$/ isolcpus=3/' "$CMDLINE"
    
    log "CPU isolation configured - core 3 will be reserved for display updates"
    return 0
}

# Function to install RGB Matrix
install_rgb_matrix() {
    local MATRIX_DIR="$1"
    local GITUSER=https://github.com/hzeller
    local REPO=rpi-rgb-led-matrix
    local COMMIT=a3eea997a9254b83ab2de97ae80d83588f696387

    log "Installing RGB Matrix software..."
    
    # Download and extract the specific commit
    curl -L $GITUSER/$REPO/archive/$COMMIT.zip -o $REPO-$COMMIT.zip
    unzip -q $REPO-$COMMIT.zip
    rm $REPO-$COMMIT.zip
    mv $REPO-$COMMIT "${MATRIX_DIR}"
    
    cd "${MATRIX_DIR}"
    
    # Build for both Python versions if available
    if command -v python3 &> /dev/null; then
        make clean
        make install-python HARDWARE_DESC=adafruit-hat-pwm PYTHON=$(which python3)
    fi

    if command -v python2 &> /dev/null; then
        make clean
        make install-python HARDWARE_DESC=adafruit-hat-pwm PYTHON=$(which python2)
    fi
    
    cd - > /dev/null
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
VENV_DIR="${INSTALL_DIR}/venv"

# Get server configuration
SERVER_URL=$(get_server_config)
log "Using server URL: ${SERVER_URL}"

# Install required system packages
log "Installing required packages..."
apt-get update
apt-get install -y python3-pip python3-dev python3-pillow git curl unzip python3-venv

# Create directories
log "Creating directories..."
mkdir -p "${PROGRAMS_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${MATRIX_DIR}"
mkdir -p "${VENV_DIR}"

# Create log file if it doesn't exist
touch "${LOG_DIR}/display.log"

# Install RGB Matrix
install_rgb_matrix "${MATRIX_DIR}"

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

Note: You may need to reboot your system for all changes to take effect.

Thank you for installing DIYbyt Display Service!
EOL