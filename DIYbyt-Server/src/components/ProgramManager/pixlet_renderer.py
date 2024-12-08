from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import zipfile
import tempfile
import os
import sys
import json
import asyncio
import logging
import signal
import uvicorn
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set
from contextlib import asynccontextmanager
import aiofiles
import aiofiles.os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/diybyt/renderer.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_DIR = Path("/opt/DIYbyt")
STAR_PROGRAMS_DIR = BASE_DIR / "star_programs"
RENDER_DIR = BASE_DIR / "render"
CACHE_DIR = RENDER_DIR / "star_programs_cache"
GIF_DIR = RENDER_DIR / "gifs"
TEMP_DIR = RENDER_DIR / "temp"

# Global state
render_tasks: Dict[str, asyncio.Task] = {}
server_instance: Optional[uvicorn.Server] = None
should_exit = False
file_observer: Optional[Observer] = None

async def log_cache_contents(message: str):
    """Helper function to log cache directory contents"""
    try:
        cache_files = [f.name for f in CACHE_DIR.iterdir() if f.is_file()]
        logger.info(f"{message} - Cache contents: {cache_files}")
    except Exception as e:
        logger.error(f"Error logging cache contents: {e}")

class ProgramFileHandler(FileSystemEventHandler):
    def __init__(self, sync_callback):
        self.sync_callback = sync_callback
        self._debounce_task = None

    def _handle_event(self, event):
        # Only process .star files and program_metadata.json
        if (event.src_path.endswith('.star') or 
            'program_metadata.json' in event.src_path):
            if self._debounce_task:
                self._debounce_task.cancel()
            self._debounce_task = asyncio.create_task(self._debounced_sync())
            logger.info(f"Detected change in {event.src_path}")

    def on_created(self, event):
        logger.info(f"File created: {event.src_path}")
        self._handle_event(event)

    def on_modified(self, event):
        logger.info(f"File modified: {event.src_path}")
        self._handle_event(event)

    def on_deleted(self, event):
        logger.info(f"File deleted: {event.src_path}")
        self._handle_event(event)

    async def _debounced_sync(self):
        """Debounce sync operations to prevent multiple rapid syncs"""
        try:
            await asyncio.sleep(1)  # Wait for 1 second to accumulate changes
            logger.info("File changes detected, triggering sync")
            await self.sync_callback()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in debounced sync: {e}")

async def sync_programs():
    """Synchronizes programs from star_programs to cache, including deletions"""
    try:
        await log_cache_contents("Before sync")
        
        # Create cache directory if it doesn't exist
        CACHE_DIR.mkdir(exist_ok=True)
        
        # Get set of source files
        source_files = {
            item.name for item in STAR_PROGRAMS_DIR.iterdir()
            if item.suffix == '.star' or item.name == 'program_metadata.json'
        }
        logger.info(f"Source files found: {source_files}")
        
        # Get set of cache files
        cache_files = {
            item.name for item in CACHE_DIR.iterdir()
            if item.suffix == '.star' or item.name == 'program_metadata.json'
        }
        logger.info(f"Cache files found: {cache_files}")
        
        # Remove files that no longer exist in source
        files_to_delete = cache_files - source_files
        for filename in files_to_delete:
            file_path = CACHE_DIR / filename
            try:
                if await aiofiles.os.path.exists(file_path):
                    await aiofiles.os.remove(file_path)
                    logger.info(f"Deleted {filename} from cache")
            except Exception as e:
                logger.error(f"Error deleting {filename}: {e}")

        # Copy new/updated files
        for item in STAR_PROGRAMS_DIR.iterdir():
            if item.suffix == '.star' or item.name == 'program_metadata.json':
                dest_path = CACHE_DIR / item.name
                shutil.copy2(item, dest_path)
                os.chmod(dest_path, 0o664)
                logger.info(f"Synced {item.name} to cache")
        
        await log_cache_contents("After sync")
        logger.info("Programs synchronized successfully")
    except Exception as e:
        logger.error(f"Error syncing programs: {e}")
        raise

async def sync_and_update():
    """Combines sync_programs and update_render_tasks into a single operation"""
    try:
        await sync_programs()
        await update_render_tasks()
        logger.info("Sync and render update completed successfully")
    except Exception as e:
        logger.error(f"Error in sync_and_update: {e}")

async def continuous_render(renderer: PixletRenderer, program_name: str, program_path: Path, 
                          slot_number: int, config: dict, refresh_rate: int):
    """Continuously renders a program at specified intervals"""
    temp_output = TEMP_DIR / f"{program_name}.gif"
    logger.info(f"Starting continuous render for {program_name} in slot {slot_number}")
    
    while not should_exit:
        try:
            start_time = datetime.now()
            
            # Perform the render
            render_config = config.get("config", {})
            if await renderer.render_app(program_path, temp_output, render_config):
                await renderer.copy_to_slot(temp_output, slot_number)
            
            # Cleanup temp file
            if temp_output.exists():
                await aiofiles.os.remove(temp_output)
            
            # Calculate sleep time
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(0.1, refresh_rate - elapsed)
            
            await asyncio.sleep(sleep_time)
            
        except asyncio.CancelledError:
            logger.info(f"Render task for {program_name} cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in continuous render for {program_name}: {e}")
            if not should_exit:
                await asyncio.sleep(5)

async def update_render_tasks():
    """Updates the running render tasks based on current metadata"""
    try:
        metadata_path = CACHE_DIR / "program_metadata.json"
        if not metadata_path.exists():
            logger.warning("No metadata file found")
            return

        async with aiofiles.open(metadata_path) as f:
            metadata = json.loads(await f.read())

        # Cancel existing tasks
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        render_tasks.clear()

        # Clean up old GIF slots
        await cleanup_gif_slots(len([p for p in metadata.items() if p[1].get("enabled", False)]))
        
        # Verify cache is clean
        await sync_programs()

        renderer = PixletRenderer()
        slot_number = 0

        # Sort items by the order specified in metadata (if exists) or by name
        sorted_programs = sorted(
            metadata.items(),
            key=lambda x: (x[1].get("order", float('inf')), x[0])
        )

        for program_name, config in sorted_programs:
            if not program_name or not config.get("enabled", False):
                continue

            program_path = CACHE_DIR / program_name
            if not program_path.exists() or not program_name.endswith('.star'):
                logger.warning(f"Invalid program file: {program_name}")
                continue

            refresh_rate = config.get("refresh_rate", 60)
            
            task = asyncio.create_task(
                continuous_render(
                    renderer,
                    program_name,
                    program_path,
                    slot_number,
                    config,
                    refresh_rate
                )
            )
            render_tasks[program_name] = task
            slot_number += 1

    except Exception as e:
        logger.error(f"Error updating render tasks: {e}")
        raise


async def cleanup_gif_slots(active_slots: int):
    """Cleanup unused GIF slots"""
    try:
        # Get all existing slot files
        existing_slots = [f for f in GIF_DIR.glob("slot*.gif")]
        
        # Remove slots that are higher than our active count
        for slot_file in existing_slots:
            try:
                slot_num = int(slot_file.stem.replace('slot', ''))
                if slot_num >= active_slots:
                    await aiofiles.os.remove(slot_file)
                    logger.info(f"Removed unused slot file: {slot_file}")
            except ValueError:
                continue  # Skip files that don't match our naming pattern
    except Exception as e:
        logger.error(f"Error cleaning up GIF slots: {e}")

@app.post("/sync")
async def trigger_sync():
    """Endpoint to trigger manual sync and render update"""
    try:
        await sync_and_update()
        return {"status": "success", "message": "Programs synced and renders restarted"}
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        return {"status": "error", "message": str(e)}

# Serve static files (gifs)
app.mount("/gifs", StaticFiles(directory=GIF_DIR), name="gifs")

async def cleanup():
    """Cleanup temporary files and tasks on shutdown"""
    try:
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

class CustomServer(uvicorn.Server):
    async def shutdown(self, sockets=None):
        global should_exit
        should_exit = True
        
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                
        await super().shutdown(sockets=sockets)

if __name__ == "__main__":
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = CustomServer(config=config)
    server_instance = server
    
    try:
        server.run()
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        asyncio.run(cleanup())