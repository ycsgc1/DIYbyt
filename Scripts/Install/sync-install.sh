#!/bin/bash

# Exit on error
set -e

# Colors for better visibility
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log functions
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
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
PROGRAMS_DIR="${INSTALL_DIR}/star_programs"
LOG_DIR="/var/log/diybyt"

# Install required packages
log "Installing required packages..."
apt-get update
apt-get install -y python3 python3-requests

# Create directories
log "Creating directories..."
mkdir -p "${PROGRAMS_DIR}"
mkdir -p "${LOG_DIR}"

# Create log file if it doesn't exist
touch "${LOG_DIR}/sync.log"

# Set ownership and permissions
log "Setting ownership and permissions..."
chown -R "${ACTUAL_USER}:${ACTUAL_USER}" "${INSTALL_DIR}"
chown -R "${ACTUAL_USER}:${ACTUAL_USER}" "${LOG_DIR}"

# Set directory permissions
chmod 750 "${INSTALL_DIR}"
chmod 2775 "${PROGRAMS_DIR}"
chmod 2775 "${LOG_DIR}"
chmod 666 "${LOG_DIR}/sync.log"

# Copy sync service script
log "Installing sync service..."
cp "${REPO_ROOT}/DIYbyt-Sync/sync_service.py" /usr/local/bin/diybyt-sync
chmod 755 /usr/local/bin/diybyt-sync
chown "${ACTUAL_USER}:${ACTUAL_USER}" /usr/local/bin/diybyt-sync

# Copy and configure systemd service
log "Setting up systemd service..."
cp "${REPO_ROOT}/DIYbyt-Sync/diybyt-sync.service" /etc/systemd/system/diybyt-sync.service
chmod 644 /etc/systemd/system/diybyt-sync.service
sed -i "s/ycsgc/${ACTUAL_USER}/g" /etc/systemd/system/diybyt-sync.service

# Install Python requirements
log "Installing Python requirements..."
if [ -f "${REPO_ROOT}/DIYbyt-Sync/requirements.txt" ]; then
    pip3 install -r "${REPO_ROOT}/DIYbyt-Sync/requirements.txt"
else
    error "Requirements file not found at ${REPO_ROOT}/DIYbyt-Sync/requirements.txt"
fi

# Reload systemd and start service
log "Starting service..."
systemctl daemon-reload
systemctl enable diybyt-sync
systemctl restart diybyt-sync

# Wait a moment for the service to start
sleep 2

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

Commands:
- Check service status: systemctl status diybyt-sync
- View logs: journalctl -u diybyt-sync -f
- View local logs: tail -f ${LOG_DIR}/sync.log
- Restart service: systemctl restart diybyt-sync
- Stop service: systemctl stop diybyt-sync

Thank you for installing DIYbyt Sync Service!
EOL