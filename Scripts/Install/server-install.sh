#!/bin/bash

# Exit on error
set -e

echo "Starting DIYbyt Render Server installation..."

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo "Please run as root (use sudo)"
        exit 1
    fi
}

# Function to install Python and venv if not present
install_python() {
    echo "Installing Python3 and required packages..."
    apt-get update
    apt-get install -y python3 python3-full python3.12-venv
}

# Function to create virtual environment and install dependencies
setup_venv() {
    echo "Creating virtual environment..."
    python3 -m venv /opt/DIYbyt/render/venv
    
    echo "Installing Python dependencies..."
    /opt/DIYbyt/render/venv/bin/pip install fastapi uvicorn python-multipart aiofiles
}

# Function to create directories
create_directories() {
    echo "Creating required directories..."
    mkdir -p /opt/DIYbyt/render/star_programs_cache
    mkdir -p /opt/DIYbyt/render/gifs
    mkdir -p /opt/DIYbyt/render/temp
    mkdir -p /opt/DIYbyt/render/cache
    
    # Set permissions
    chown -R $SUDO_USER:$SUDO_USER /opt/DIYbyt/render
}

# Function to create systemd service for the renderer
create_renderer_service() {
    echo "Creating renderer service..."
    cat > /etc/systemd/system/diybyt-renderer.service << EOL
[Unit]
Description=DIYbyt Renderer Service
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=/opt/DIYbyt/render
ExecStart=/opt/DIYbyt/render/venv/bin/python src/components/ProgramManager/pixlet_renderer.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL
}

# Function to create systemd service for the program manager
create_program_manager_service() {
    echo "Creating program manager service..."
    cat > /etc/systemd/system/diybyt-program-manager.service << EOL
[Unit]
Description=DIYbyt Program Manager Service
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=/opt/DIYbyt/render
ExecStart=/opt/DIYbyt/render/venv/bin/python src/components/ProgramManager/program-manager.py
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

    # Install Python if needed
    install_python

    # Create installation directory
    echo "Setting up installation directory..."
    mkdir -p /opt/DIYbyt/render/src/components/ProgramManager
    
    # Copy files from DIYbyt-Server directory
    echo "Copying service files..."
    cp ../../DIYbyt-Server/src/components/ProgramManager/pixlet_renderer.py /opt/DIYbyt/render/src/components/ProgramManager/
    cp ../../DIYbyt-Server/src/components/ProgramManager/program-manager.py /opt/DIYbyt/render/src/components/ProgramManager/
    
    # Set permissions
    chown -R $SUDO_USER:$SUDO_USER /opt/DIYbyt/render
    
    # Setup virtual environment and install dependencies
    setup_venv
    
    # Create required directories
    create_directories
    
    # Create services
    create_renderer_service
    create_program_manager_service
    
    echo "Starting services..."
    systemctl daemon-reload
    systemctl enable diybyt-renderer diybyt-program-manager
    systemctl start diybyt-renderer diybyt-program-manager
    
    echo "Installation complete!"
    echo "The render server is now running"
    echo "To check service status:"
    echo "  systemctl status diybyt-renderer"
    echo "  systemctl status diybyt-program-manager"
    echo "Renderer is accessible at http://localhost:8000"
}

# Run main installation
main