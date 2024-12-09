#!/bin/bash

# Exit on any error
set -e

echo "DIYbyt Display Service Installer"
echo "===============================\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Function to get server IP
get_server_ip() {
    local ip
    while true; do
        read -p "Enter the IP address of your DIYbyt render server (e.g., 192.168.1.188): " ip
        # Basic IP validation
        if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo $ip
            return 0
        else
            echo "Invalid IP format. Please try again."
        fi
    done
}

# Create necessary directories
echo "Creating directory structure..."
mkdir -p /opt/DIYbyt/star_programs
mkdir -p /var/log

# Get server IP
SERVER_IP=$(get_server_ip)
echo "Using server IP: $SERVER_IP"

# Create config file
echo "Creating config file..."
cat > /opt/DIYbyt/config.json << EOL
{
    "server_ip": "${SERVER_IP}",
    "programs_path": "/opt/DIYbyt/star_programs"
}
EOL

# Install required packages
echo "Installing required packages..."
apt-get update
apt-get install -y python3-pip python3-dev python3-pillow git curl unzip

# Save current directory
CURRENT_DIR=$(pwd)

# Create temporary directory for matrix installation
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Download and run Adafruit RGB Matrix installer
echo "Installing RGB Matrix library..."
curl -L https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/rgb-matrix.sh -o rgb-matrix.sh
chmod +x rgb-matrix.sh

# Run the Adafruit installer script
# Note: This will prompt for user input
./rgb-matrix.sh

# Return to original directory
cd $CURRENT_DIR

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install requests pillow

# Install the display script
echo "Installing display script..."
install -m 755 diybyt-display.py /usr/local/bin/diybyt-display

# Install and enable systemd service
echo "Installing systemd service..."
install -m 644 diybyt-display.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable diybyt-display.service

echo "Installation complete!"
echo "Please ensure your program_metadata.json is in /opt/DIYbyt/star_programs/"
echo "The display service will start on next reboot"
echo "You can start it manually with: systemctl start diybyt-display"

# Clean up
rm -rf $TEMP_DIR

echo -n "Would you like to reboot now? [y/N] "
read answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    reboot
fi