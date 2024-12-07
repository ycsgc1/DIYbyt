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
RENDER_DIR="${INSTALL_DIR}/render"
TEMP_DIR="${RENDER_DIR}/temp"
CACHE_DIR="${RENDER_DIR}/star_programs_cache"
GIF_DIR="${RENDER_DIR}/gifs"

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
mkdir -p "${TEMP_DIR}"
mkdir -p "${CACHE_DIR}"
mkdir -p "${GIF_DIR}"

# Copy renderer script
log "Installing renderer service..."
cp "${REPO_ROOT}/DIYbyt-Server/src/components/ProgramManager/pixlet_renderer.py" "${COMPONENTS_DIR}/"

# Copy and configure systemd service
log "Setting up systemd service..."
cp "${REPO_ROOT}/DIYbyt-Server/systemd/diybyt-renderer.service" "/etc/systemd/system/${SERVICE_NAME}.service"

# Create log file if it doesn't exist
touch "${LOG_DIR}/renderer.log"

# Set proper permissions
log "Setting proper permissions..."

# Set ownership recursively
chown -R root:root "${INSTALL_DIR}"
chown -R root:root "${LOG_DIR}"

# Set world-writable permissions for render directories
chmod 777 "${TEMP_DIR}"
chmod 777 "${GIF_DIR}"
chmod 777 "${CACHE_DIR}"

# Make parent directories accessible
chmod 755 "${INSTALL_DIR}"
chmod 755 "${RENDER_DIR}"
chmod 755 "${COMPONENTS_DIR}"

# Set log directory permissions
chmod 777 "${LOG_DIR}"
chmod 666 "${LOG_DIR}/renderer.log"

# Make the renderer script executable
chmod 755 "${COMPONENTS_DIR}/pixlet_renderer.py"

# Set service file permissions
chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"

# Check for pixlet installation
if ! command -v pixlet &> /dev/null; then
    error "Pixlet is not installed or not in PATH. Please install pixlet first."
fi

# Make pixlet executable and ensure it's accessible
chmod 755 $(which pixlet)

# Install Python dependencies
log "Installing Python dependencies..."
apt-get update
apt-get install -y python3-fastapi python3-uvicorn python3-aiofiles python3-watchdog

# Reload systemd and enable service
log "Enabling and starting service..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

# Wait a moment for the service to start
sleep 2

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
- Render directory: ${RENDER_DIR}
- Logs: ${LOG_DIR}/renderer.log

Commands:
- Check service status: systemctl status ${SERVICE_NAME}
- View logs: journalctl -u ${SERVICE_NAME} -f
- Restart service: systemctl restart ${SERVICE_NAME}
- Stop service: systemctl stop ${SERVICE_NAME}

Thank you for installing DIYbyt Renderer Service!
EOL