#!/bin/bash

# Exit on any error
set -e

# Function for logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[ERROR] $1" >&2
    exit 1
}

# Configuration
DIYBYT_HOME="/opt/diybyt"
GUI_SERVICE_NAME="diybyt-gui"
STAR_PROGRAMS_DIR="/opt/diybyt/star_programs"
GUI_PORT=3001

# Check if running as root
if [ $(id -u) -ne 0 ]; then
    error "Installer must be run as root. Try 'sudo bash $0'"
fi

log "Starting DIYbyt GUI installation..."

# Install Node.js and npm
log "Installing Node.js and npm..."
if ! command -v node &> /dev/null; then
    log "Downloading Node.js setup script..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - || error "Failed to download Node.js setup"
    
    log "Installing Node.js packages..."
    apt-get install -y nodejs || error "Failed to install Node.js"
else
    log "Node.js already installed"
fi

# Verify Node.js installation
node --version || error "Node.js installation verification failed"
npm --version || error "npm installation verification failed"

# Create directory structure
log "Creating directory structure..."
mkdir -p $DIYBYT_HOME/gui || error "Failed to create GUI directory"
mkdir -p $STAR_PROGRAMS_DIR || error "Failed to create programs directory"

# Get absolute path to DIYbyt-GUI directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_SOURCE_DIR="$SCRIPT_DIR/../../DIYbyt-GUI"

# Verify source directory exists
log "Verifying source directory..."
if [ ! -d "$GUI_SOURCE_DIR" ]; then
    error "Source directory not found: $GUI_SOURCE_DIR"
fi

# Copy application files
log "Installing application files..."
log "Copying from $GUI_SOURCE_DIR to $DIYBYT_HOME/gui/"
cp -rv "$GUI_SOURCE_DIR/"* $DIYBYT_HOME/gui/ || error "Failed to copy GUI files"

# Verify package.json exists
log "Verifying package.json exists..."
if [ ! -f "$DIYBYT_HOME/gui/package.json" ]; then
    error "package.json not found in $DIYBYT_HOME/gui/"
fi

# Install dependencies
log "Installing npm dependencies..."
cd $DIYBYT_HOME/gui || error "Failed to change to GUI directory"
log "Current directory: $(pwd)"
log "Directory contents:"
ls -la

log "Cleaning npm cache..."
npm cache clean --force

log "Running npm install with verbose output..."
npm install --verbose --no-audit || error "Failed to install npm dependencies"

log "Building application..."
npm run build || error "Failed to build application"

# Create environment file
log "Creating environment configuration..."
cat > $DIYBYT_HOME/gui/.env << EOF
PORT=$GUI_PORT
STAR_PROGRAMS_DIR=$STAR_PROGRAMS_DIR
NODE_ENV=production
VITE_API_URL=http://localhost:$GUI_PORT/api
EOF

# Create systemd service
log "Creating systemd service..."
cat > /etc/systemd/system/$GUI_SERVICE_NAME.service << EOF
[Unit]
Description=DIYbyt GUI Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DIYBYT_HOME/gui
Environment=NODE_ENV=production
Environment=PORT=$GUI_PORT
Environment=STAR_PROGRAMS_DIR=$STAR_PROGRAMS_DIR
ExecStart=/usr/bin/node src/server.js
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Configure directory permissions
log "Setting permissions..."
chown -R root:root $DIYBYT_HOME/gui
chmod 755 $DIYBYT_HOME/gui
chmod 755 $STAR_PROGRAMS_DIR

# Enable and start service
log "Enabling and starting service..."
systemctl enable $GUI_SERVICE_NAME || error "Failed to enable service"
systemctl start $GUI_SERVICE_NAME || error "Failed to start service"

log "Installation complete!"
log "The GUI server should now be running on port $GUI_PORT"
log "You can view logs with: journalctl -u $GUI_SERVICE_NAME -f"

systemctl status $GUI_SERVICE_NAME