#!/bin/bash

# Exit on error
set -e

echo "Starting DIYbyt GUI installation..."

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo "Please run as root (use sudo)"
        exit 1
    fi
}

# Function to install Node.js and npm if not present
install_node() {
    if ! command -v node &> /dev/null; then
        echo "Installing Node.js..."
        # Using Node.js 20.x LTS
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    fi
}

# Function to update server.js configuration
update_server_config() {
    local server_js="/opt/DIYbyt/DIYbyt-GUI/src/server.js"
    echo "Updating server configuration..."
    # Create backup of original server.js
    cp "$server_js" "$server_js.backup"
    # Update STAR_PROGRAMS_DIR path
    sed -i "s|const STAR_PROGRAMS_DIR = './star_programs'|const STAR_PROGRAMS_DIR = '/opt/DIYbyt/DIYbyt-GUI/star_programs'|" "$server_js"
}

# Function to create systemd service
create_service() {
    echo "Creating systemd service..."
    cat > /etc/systemd/system/diybyt-gui.service << EOL
[Unit]
Description=DIYbyt GUI Service
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=/opt/DIYbyt/DIYbyt-GUI
ExecStart=/usr/bin/node src/server.js
Restart=always
Environment=NODE_ENV=production
Environment=PORT=3001

[Install]
WantedBy=multi-user.target
EOL
}

# Function to setup directories and permissions
setup_directories() {
    echo "Setting up directories and permissions..."
    
    # Create star_programs directory
    mkdir -p /opt/DIYbyt/DIYbyt-GUI/star_programs
    
    # Set ownership of all directories
    chown -R $SUDO_USER:$SUDO_USER /opt/DIYbyt/DIYbyt-GUI
    
    # Set specific permissions for star_programs directory
    chmod 755 /opt/DIYbyt/DIYbyt-GUI/star_programs
}

# Main installation
main() {
    check_root

    # Install dependencies
    echo "Installing system dependencies..."
    apt-get update
    install_node

    # Create installation directory
    echo "Setting up installation directory..."
    mkdir -p /opt/DIYbyt
    
    # Copy files
    echo "Copying application files..."
    cp -r ../../DIYbyt-GUI /opt/DIYbyt/
    
    # Setup directories and permissions
    setup_directories
    
    # Update server configuration
    update_server_config
    
    # Install npm dependencies and build
    echo "Installing npm dependencies..."
    cd /opt/DIYbyt/DIYbyt-GUI
    sudo -u $SUDO_USER npm install
    
    echo "Building application..."
    sudo -u $SUDO_USER npm run build
    
    # Create and start service
    create_service
    
    echo "Starting service..."
    systemctl daemon-reload
    systemctl enable diybyt-gui
    systemctl start diybyt-gui
    
    echo "Installation complete!"
    echo "The GUI service is now running at http://localhost:3001"
    echo "To check service status: systemctl status diybyt-gui"
    echo "Star programs directory: /opt/DIYbyt/DIYbyt-GUI/star_programs"
    echo "Original server.js configuration backed up as server.js.backup"
}

# Run main installation
main