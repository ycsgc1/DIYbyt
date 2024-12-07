#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base paths
INSTALL_DIR="/opt/DIYbyt"
COMPONENTS_DIR="${INSTALL_DIR}/components/ProgramManager"
LOG_DIR="/var/log/diybyt"
SERVICE_NAME="diybyt-renderer"

# Script directory detection
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

# Log function
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

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root (use sudo)"
fi

# Create directory structure
log "Creating directory structure..."
mkdir -p "${COMPONENTS_DIR}"
mkdir -p "${LOG_DIR}"

# Copy renderer script
log "Installing renderer service..."
cp "${REPO_ROOT}/DIYbyt-Server/src/components/ProgramManager/pixlet_renderer.py" "${COMPONENTS_DIR}/"
chmod +x "${COMPONENTS_DIR}/pixlet_renderer.py"

# Copy and configure systemd service
log "Setting up systemd service..."
cp "${REPO_ROOT}/DIYbyt-Server/systemd/diybyt-renderer.service" "/etc/systemd/system/${SERVICE_NAME}.service"

# Set proper permissions
log "Setting permissions..."
chown -R root:root "${INSTALL_DIR}"
chmod -R 755 "${INSTALL_DIR}"
chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"
chmod 644 "${LOG_DIR}/renderer.log"

# Install Python dependencies
log "Installing Python dependencies..."
apt-get update
apt-get install -y python3-fastapi python3-uvicorn python3-aiofiles python3-watchdog

# Reload systemd and enable service
log "Enabling and starting service..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl start ${SERVICE_NAME}

# Check service status
if systemctl is-active --quiet ${SERVICE_NAME}; then
    log "Service installed and running successfully!"
    log "You can check the logs with: journalctl -u ${SERVICE_NAME} -f"
    log "Service status: $(systemctl status ${SERVICE_NAME} | grep Active)"
else
    error "Service failed to start. Check logs with: journalctl -u ${SERVICE_NAME} -xe"
fi

# Print final instructions
cat << EOL

${GREEN}Installation Complete!${NC}

Important paths:
- Install directory: ${INSTALL_DIR}
- Components directory: ${COMPONENTS_DIR}
- Logs: ${LOG_DIR}/renderer.log

Commands:
- Check service status: systemctl status ${SERVICE_NAME}
- View logs: journalctl -u ${SERVICE_NAME} -f
- Restart service: systemctl restart ${SERVICE_NAME}
- Stop service: systemctl stop ${SERVICE_NAME}

Thank you for installing DIYbyt Renderer Service!
EOL