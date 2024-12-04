# DIYbyt-Sync

File synchronization service for DIYbyt that monitors the star_programs directory and syncs changes to the render server.

## Overview

DIYbyt-Sync is a Python service that:
- Monitors the star_programs directory for changes
- Automatically syncs changes to the render server
- Runs as a systemd service
- Works alongside DIYbyt-GUI but operates independently

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your configuration:
```bash
STAR_PROGRAMS_PATH=/path/to/star_programs
RENDER_SERVER_URL=http://your.render.server:8000
```

3. Install the systemd service:
```bash
# Copy service file
sudo cp star-sync.service /etc/systemd/system/

# Edit the service file to update paths and user
sudo nano /etc/systemd/system/star-sync.service

# Enable and start the service
sudo systemctl enable star-sync
sudo systemctl start star-sync
```

## Monitoring

Check service status:
```bash
sudo systemctl status star-sync
```

View logs:
```bash
journalctl -u star-sync -f
```

## Development

To run the service directly for development:
```bash
python sync_service.py
```

## Configuration

The service can be configured through environment variables or the `.env` file:

- `STAR_PROGRAMS_PATH`: Path to the star_programs directory
- `RENDER_SERVER_URL`: URL of the render server
- `CHECK_INTERVAL`: How often to check for changes (in seconds, default: 30)
- `LOG_LEVEL`: Logging level (default: INFO)