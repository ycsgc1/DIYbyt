#!/usr/bin/python3

import os
import time
import json
import requests
import logging
from pathlib import Path
from typing import Dict, Optional
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.expanduser('~/diybyt-sync.log'))
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
        self.last_programs_hash = None
        self.last_metadata_hash = None
        
        # Ensure local directory exists
        self.local_path.mkdir(parents=True, exist_ok=True)
        
    def calculate_hash(self, content: str) -> str:
        """Calculate a simple hash of content"""
        return str(hash(content))
            
    def get_remote_programs(self) -> Optional[Dict]:
        """Get all programs from the remote server"""
        try:
            response = requests.get(f"{self.server_url}/api/programs")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get remote programs: {e}")
            return None
            
    def get_remote_metadata(self) -> Optional[Dict]:
        """Get metadata from the remote server"""
        try:
            response = requests.get(f"{self.server_url}/api/metadata")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get remote metadata: {e}")
            return None
            
    def sync_programs(self, programs: list) -> bool:
        """Sync the provided programs to the local directory"""
        try:
            # First, remove any .star files that aren't in the programs list
            current_files = [f for f in self.local_path.glob("*.star")]
            program_names = [p["name"] for p in programs]
            
            for file in current_files:
                if file.name not in program_names:
                    logger.info(f"Removing old program: {file.name}")
                    file.unlink()
            
            # Now sync all programs
            for program in programs:
                file_path = self.local_path / program["name"]
                with open(file_path, 'w') as f:
                    f.write(program["content"])
                logger.info(f"Synced program: {program['name']}")
                
            return True
        except Exception as e:
            logger.error(f"Failed to sync programs: {e}")
            return False
            
    def sync_metadata(self, metadata: Dict) -> bool:
        """Sync the provided metadata to the local directory"""
        try:
            metadata_path = self.local_path / 'program_metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info("Metadata synchronized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to sync metadata: {e}")
            return False
            
    def check_and_sync(self) -> bool:
        """Check for changes and sync if necessary"""
        needs_sync = False
        
        # Check programs
        programs = self.get_remote_programs()
        if programs is not None:
            programs_hash = self.calculate_hash(str(programs))
            if programs_hash != self.last_programs_hash:
                logger.info("Program changes detected")
                if self.sync_programs(programs):
                    self.last_programs_hash = programs_hash
                    needs_sync = True
        
        # Check metadata
        metadata = self.get_remote_metadata()
        if metadata is not None:
            metadata_hash = self.calculate_hash(str(metadata))
            if metadata_hash != self.last_metadata_hash:
                logger.info("Metadata changes detected")
                if self.sync_metadata(metadata):
                    self.last_metadata_hash = metadata_hash
                    needs_sync = True
        
        return needs_sync
        
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
                if self.check_and_sync():
                    logger.info("Sync completed")
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
    
    syncer = DIYbytSync(server_url, local_path)
    syncer.run(sync_interval)

if __name__ == "__main__":
    main()