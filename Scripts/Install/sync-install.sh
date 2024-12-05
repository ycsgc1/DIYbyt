#!/bin/bash

# Exit on error
set -e

echo "Starting DIYbyt Sync Service installation..."

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo "Please run as root (use sudo)"
        exit 1
    fi
}

# Function to install Python and pip if not present
install_python() {
    if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null; then
        echo "Installing Python3 and pip3..."
        apt-get update
        apt-get install -y python3 python3-pip
    fi
}

# Function to install Python dependencies
install_dependencies() {
    echo "Installing Python dependencies..."
    pip3 install -r ../../DIYbyt-Sync/requirements.txt
}

# Function to create environment file
create_env_file() {
    echo "Creating environment configuration..."
    cat > /opt/DIYbyt/sync/.env << EOL
# Path to star_programs directory
STAR_PROGRAMS_PATH=/opt/DIYbyt/DIYbyt-GUI/star_programs

# Render server URL
RENDER_SERVER_URL=http://localhost:8000

# Optional settings
CHECK_INTERVAL=30
LOG_LEVEL=INFO
EOL
}

# Function to create systemd service
create_service() {
    echo "Creating systemd service..."
    cat > /etc/systemd/system/diybyt-sync.service << EOL
[Unit]
Description=Star Programs Sync Service
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=/opt/DIYbyt/sync
ExecStart=/usr/bin/python3 sync_service.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL
}

# Main installation
main() {
    check_root

    # Install Python and pip if needed
    install_python

    # Create installation directory
    echo "Setting up installation directory..."
    mkdir -p /opt/DIYbyt/sync
    
    # Copy files from DIYbyt-Sync directory
    echo "Copying service files..."
    cp ../../DIYbyt-Sync/sync_service.py /opt/DIYbyt/sync/
    cp ../../DIYbyt-Sync/requirements.txt /opt/DIYbyt/sync/
    
    # Set permissions
    chown -R $SUDO_USER:$SUDO_USER /opt/DIYbyt/sync
    
    # Install dependencies
    install_dependencies
    
    # Create environment file
    create_env_file
    
    # Create and start service
    create_service
    
    echo "Starting service..."
    systemctl daemon-reload
    systemctl enable diybyt-sync
    systemctl start diybyt-sync
    
    echo "Installation complete!"
    echo "The sync service is now running"
    echo "To check service status: systemctl status diybyt-sync"
    echo "Environment configuration: /opt/DIYbyt/sync/.env"
}

# Run main installation
main