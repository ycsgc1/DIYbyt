import asyncio
import aiohttp
import logging
from pathlib import Path
import json
import hashlib
import zipfile
import tempfile
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment
STAR_PROGRAMS_PATH = Path(os.getenv('STAR_PROGRAMS_PATH', './star_programs'))
RENDER_SERVER_URL = os.getenv('RENDER_SERVER_URL', 'http://localhost:8000')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StarProgramsHandler(FileSystemEventHandler):
    def __init__(self, sync_service):
        self.sync_service = sync_service
        self.debounce_timer = None
        
    def on_any_event(self, event):
        """Handle any file system event in the watched directory"""
        # Ignore directory events and temporary files
        if event.is_directory or event.src_path.endswith('.tmp'):
            return
            
        # Cancel existing timer
        if self.debounce_timer:
            self.debounce_timer.cancel()
            
        # Set new timer for sync
        self.debounce_timer = asyncio.create_task(self.debounce_sync())
        
    async def debounce_sync(self):
        """Wait briefly before triggering sync to batch rapid changes"""
        await asyncio.sleep(2)  # Wait 2 seconds for changes to settle
        await self.sync_service.sync_to_server()

class SyncService:
    def __init__(self, 
                 star_programs_path: Path,
                 render_server_url: str,
                 check_interval: int = 30):
        self.star_programs_path = Path(star_programs_path)
        self.render_server_url = render_server_url
        self.check_interval = check_interval
        self.last_hash = None
        self.observer = None
        self.session = None
        
    def calculate_directory_hash(self) -> str:
        """Calculate a hash of the entire star_programs directory"""
        hasher = hashlib.sha256()
        
        # Get all files recursively, sort for consistent ordering
        files = sorted(
            f for f in self.star_programs_path.rglob('*') 
            if f.is_file() and not f.name.startswith('.')
        )
        
        for file_path in files:
            # Add file path to hash
            hasher.update(str(file_path.relative_to(self.star_programs_path)).encode())
            
            # Add file contents to hash
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
                    
        return hasher.hexdigest()
        
    async def create_zip_archive(self) -> Path:
        """Create a zip archive of the star_programs directory"""
        # Create temporary zip file
        temp_zip = Path(tempfile.mktemp(suffix='.zip'))
        
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files in the directory
            for file_path in self.star_programs_path.rglob('*'):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    arcname = file_path.relative_to(self.star_programs_path)
                    zipf.write(file_path, arcname)
                    
        return temp_zip
        
    async def sync_to_server(self):
        """Check for changes and sync to render server if needed"""
        try:
            current_hash = self.calculate_directory_hash()
            
            if current_hash != self.last_hash:
                logger.info("Changes detected, syncing to render server...")
                
                # Create zip archive
                zip_path = await self.create_zip_archive()
                
                try:
                    # Send to server
                    async with aiohttp.ClientSession() as session:
                        with open(zip_path, 'rb') as f:
                            files = {'file': f}
                            async with session.post(
                                f"{self.render_server_url}/update",
                                data=files
                            ) as response:
                                if response.status == 200:
                                    logger.info("Sync successful")
                                    self.last_hash = current_hash
                                else:
                                    logger.error(f"Sync failed: {await response.text()}")
                finally:
                    # Cleanup zip file
                    zip_path.unlink()
                    
        except Exception as e:
            logger.error(f"Error during sync: {e}")
            
    async def start(self):
        """Start the sync service"""
        try:
            # Set up watchdog observer
            self.observer = Observer()
            handler = StarProgramsHandler(self)
            self.observer.schedule(
                handler, 
                str(self.star_programs_path), 
                recursive=True
            )
            self.observer.start()
            
            logger.info(f"Started monitoring {self.star_programs_path}")
            
            # Initial sync
            await self.sync_to_server()
            
            # Keep the service running
            while True:
                await asyncio.sleep(self.check_interval)
                await self.sync_to_server()  # Periodic check for changes
                
        except Exception as e:
            logger.error(f"Service error: {e}")
            if self.observer:
                self.observer.stop()
        
    async def stop(self):
        """Stop the sync service"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Sync service stopped")

def main():
    # Create and run service
    service = SyncService(STAR_PROGRAMS_PATH, RENDER_SERVER_URL, CHECK_INTERVAL)
    
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        asyncio.run(service.stop())

if __name__ == "__main__":
    main()