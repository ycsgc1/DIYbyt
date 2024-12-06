#!/bin/bash

# Exit on error
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Get the repository root directory (assuming script is in Scripts/Install)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Create diybyt user if it doesn't exist
if ! id "diybyt" &>/dev/null; then
    useradd -r -s /bin/false diybyt
fi

# Install required packages
apt-get update
apt-get install -y python3 python3-pip

# Install Python requirements
pip3 install requests

# Create directories
mkdir -p /opt/DIYbyt/star_programs
chown -R diybyt:diybyt /opt/DIYbyt

# Copy sync service script
cp "${REPO_ROOT}/DIYbyt-Sync/sync_service.py" /usr/local/bin/diybyt-sync
chmod +x /usr/local/bin/diybyt-sync
chown diybyt:diybyt /usr/local/bin/diybyt-sync

# Copy and enable systemd service
cp "${REPO_ROOT}/DIYbyt-Sync/diybyt-sync.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable diybyt-sync
systemctl start diybyt-sync

echo "DIYbyt sync service installed and started!"
echo "Check status with: systemctl status diybyt-sync"
echo "Check logs with: journalctl -u diybyt-sync"