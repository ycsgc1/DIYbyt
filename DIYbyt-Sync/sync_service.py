#!/usr/bin/python3

import os
import time
import json
import requests
import logging
from pathlib import Path
from typing import Dict, Optional
import sys

# Ensure log directory exists
log_dir = Path("/var/log")
if not log_dir.exists():
    os.makedirs(log_dir, exist_ok=True)

# Configure logging
# Configure logging
log_file = os.path.expanduser('~/diybyt-sync.log') if os.getuid() != 0 else '/var/log/diybyt-sync.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

class DIYbytSync:
    def __init__(self, server_url: str, local_path: str):
        """
        Initialize the sync service
        
        Args:
            server_url: URL of the GUI server (e.g., "http://localhost:3001" or "http://192.168.1.100:3001")
            local_path: Path where star programs should be stored locally
        """
        self.server_url = server_url.rstrip('/')
        self.local_path = Path(local_path)
        self.last_hash = None
        
        # Ensure local directory exists
        self.local_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized sync service for {server_url} -> {local_path}")
        
    def get_remote_hash(self) -> Optional[str]:
        """Get the hash of the remote directory"""
        try:
            response = requests.get(f"{self.server_url}/api/sync/hash")
            response.raise_for_status()
            return response.json()['hash']
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed to {self.server_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get remote hash: {e}")
            return None
            
    def get_remote_files(self) -> Optional[Dict]:
        """Get all files from the remote server"""
        try:
            response = requests.get(f"{self.server_url}/api/sync/all")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed to {self.server_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get remote files: {e}")
            return None
            
    def sync_files(self, files: Dict) -> bool:
        """Sync the provided files to the local directory"""
        try:
            for filename, content in files.items():
                file_path = self.local_path / filename
                # Ensure parent directories exist
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w') as f:
                    f.write(content)
            logger.info(f"Successfully synchronized {len(files)} files")
            return True
        except Exception as e:
            logger.error(f"Failed to sync files: {e}")
            return False
            
    def check_and_sync(self) -> bool:
        """Check for changes and sync if necessary"""
        remote_hash = self.get_remote_hash()
        
        if remote_hash is None:
            logger.warning("Could not get remote hash, skipping sync")
            return False
            
        if remote_hash != self.last_hash:
            logger.info("Changes detected, syncing files...")
            files = self.get_remote_files()
            
            if files is None:
                logger.warning("Could not get remote files, skipping sync")
                return False
                
            if self.sync_files(files):
                self.last_hash = remote_hash
                return True
                
        return False
        
    def run(self, interval: int = 5):
        """
        Run the sync service continuously
        
        Args:
            interval: Number of seconds to wait between sync checks
        """
        logger.info(f"Starting DIYbyt sync service")
        logger.info(f"Server URL: {self.server_url}")
        logger.info(f"Local path: {self.local_path}")
        logger.info(f"Check interval: {interval} seconds")
        
        while True:
            try:
                self.check_and_sync()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Sync service stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(interval)

def main():
    # Load configuration from environment variables or use defaults
    server_url = os.getenv('DIYBYT_SERVER_URL', 'http://localhost:3001')
    local_path = os.getenv('DIYBYT_PROGRAMS_PATH', '/opt/DIYbyt/star_programs')
    sync_interval = int(os.getenv('DIYBYT_SYNC_INTERVAL', '5'))
    
    try:
        syncer = DIYbytSync(server_url, local_path)
        syncer.run(sync_interval)
    except Exception as e:
        logger.error(f"Fatal error in sync service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()