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

# Get current user (the one who sudo'ed)
ACTUAL_USER=$(who mom likes | awk '{print $1}')

# Install required packages
apt-get update
apt-get install -y python3 python3-requests

# Create directories
mkdir -p /opt/DIYbyt/star_programs
mkdir -p /var/log/diybyt

# Set ownership
chown -R ${ACTUAL_USER}:${ACTUAL_USER} /opt/DIYbyt
chown -R ${ACTUAL_USER}:${ACTUAL_USER} /var/log/diybyt

# Copy sync service script
cp "${REPO_ROOT}/DIYbyt-Sync/sync_service.py" /usr/local/bin/diybyt-sync
chmod +x /usr/local/bin/diybyt-sync
chown ${ACTUAL_USER}:${ACTUAL_USER} /usr/local/bin/diybyt-sync

# Copy and enable systemd service
cp "${REPO_ROOT}/DIYbyt-Sync/diybyt-sync.service" /etc/systemd/system/
sed -i "s/ycsgc/${ACTUAL_USER}/g" /etc/systemd/system/diybyt-sync.service

systemctl daemon-reload
systemctl enable diybyt-sync
systemctl start diybyt-sync

echo "DIYbyt sync service installed and started!"
echo "Check status with: systemctl status diybyt-sync"
echo "Check logs with: tail -f /var/log/diybyt/sync.log"