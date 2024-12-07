#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base paths
INSTALL_DIR="/opt/DIYbyt"
SERVICE_NAME="diybyt-render"
SYSTEMD_DIR="/etc/systemd/system"

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
mkdir -p "${INSTALL_DIR}"/{render,star_programs,render/gifs,render/temp,render/star_programs_cache}

# Set proper permissions
log "Setting permissions..."
chown -R root:root "${INSTALL_DIR}"
chmod -R 755 "${INSTALL_DIR}"

# Copy render service script
log "Installing render service..."
cat > "${INSTALL_DIR}/render_service.py" << 'EOL'
# Paste the entire render_service.py content here
EOL

# Create systemd service
log "Creating systemd service..."
cat > "${SYSTEMD_DIR}/${SERVICE_NAME}.service" << EOL
[Unit]
Description=DIYbyt Render Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/render_service.py
Restart=always
RestartSec=3
StandardOutput=append:/var/log/diybyt-render.log
StandardError=append:/var/log/diybyt-render.log

[Install]
WantedBy=multi-user.target
EOL

# Create log file
touch /var/log/diybyt-render.log
chmod 644 /var/log/diybyt-render.log

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
- Star programs directory: ${INSTALL_DIR}/star_programs
- Rendered GIFs: ${INSTALL_DIR}/render/gifs
- Logs: /var/log/diybyt-render.log

Commands:
- Check service status: systemctl status ${SERVICE_NAME}
- View logs: journalctl -u ${SERVICE_NAME} -f
- Restart service: systemctl restart ${SERVICE_NAME}
- Stop service: systemctl stop ${SERVICE_NAME}

Thank you for installing DIYbyt Render Service!
EOL