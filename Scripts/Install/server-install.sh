#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base paths
INSTALL_DIR="/opt/DIYbyt"
RENDER_DIR="${INSTALL_DIR}/render"
COMPONENTS_DIR="${RENDER_DIR}/src/components/ProgramManager"
LOG_DIR="/var/log/diybyt"
SERVICE_NAME="diybyt-renderer"
TEMP_DIR="${RENDER_DIR}/temp"
CACHE_DIR="${RENDER_DIR}/star_programs_cache"
GIF_DIR="${RENDER_DIR}/gifs"
VENV_DIR="${RENDER_DIR}/venv"

# Get the actual username (not root)
ACTUAL_USER=$(logname || whoami)

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

# Set up virtual environment
log "Setting up Python virtual environment..."
apt-get update
apt-get install -y python3-venv python3-pip

if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

# Install dependencies in virtual environment
"${VENV_DIR}/bin/pip" install fastapi uvicorn aiofiles watchdog

# Copy and configure systemd service
log "Setting up systemd service..."
cp "${REPO_ROOT}/DIYbyt-Server/systemd/diybyt-renderer.service" "/etc/systemd/system/${SERVICE_NAME}.service"

# Create log file if it doesn't exist
touch "${LOG_DIR}/renderer.log"

# Set proper permissions
log "Setting proper permissions..."

# Set ownership to the actual user
chown -R "${ACTUAL_USER}:${ACTUAL_USER}" "${RENDER_DIR}"
chown -R "${ACTUAL_USER}:${ACTUAL_USER}" "${LOG_DIR}"

# Set directory permissions
chmod 755 "${INSTALL_DIR}"
chmod 755 "${RENDER_DIR}"
chmod 755 "${COMPONENTS_DIR}"
chmod -R 775 "${TEMP_DIR}"
chmod -R 775 "${CACHE_DIR}"
chmod -R 775 "${GIF_DIR}"
chmod -R 775 "${LOG_DIR}"
chmod 2775 "${PROGRAMS_DIR}"  # SetGID bit for shared directories
chmod 2775 "${CACHE_DIR}"
chmod 2775 "${GIF_DIR}"
chmod 2775 "${LOG_DIR}"
# Set specific file permissions
chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"
chmod 666 "${LOG_DIR}/renderer.log"
chmod 755 "${COMPONENTS_DIR}/pixlet_renderer.py"

# Check for pixlet installation
if ! command -v pixlet &> /dev/null; then
    error "Pixlet is not installed or not in PATH. Please install pixlet first."
fi
chmod 755 $(which pixlet)

# Replace username in service file
sed -i "s/User=ycsgc/User=${ACTUAL_USER}/" "/etc/systemd/system/${SERVICE_NAME}.service"
sed -i "s/Group=ycsgc/Group=${ACTUAL_USER}/" "/etc/systemd/system/${SERVICE_NAME}.service"

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