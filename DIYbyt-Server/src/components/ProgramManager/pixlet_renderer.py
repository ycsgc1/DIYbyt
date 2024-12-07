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
from typing import Dict, Optional
from contextlib import asynccontextmanager
import aiofiles
import aiofiles.os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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

    def on_created(self, event):
        self._handle_event(event)

    def on_modified(self, event):
        self._handle_event(event)

    def on_deleted(self, event):
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

def handle_exit(signum, frame):
    """Handle exit signals gracefully"""
    global should_exit, file_observer
    logger.info(f"Received signal {signum}. Starting graceful shutdown...")
    should_exit = True
    if file_observer:
        file_observer.stop()
    if server_instance:
        asyncio.create_task(server_instance.shutdown())

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Starting lifespan context ===")
    global file_observer
    try:
        # Create required directories
        for directory in [STAR_PROGRAMS_DIR, RENDER_DIR, CACHE_DIR, GIF_DIR, TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Set up file watching
        event_handler = ProgramFileHandler(sync_callback=sync_and_update)
        file_observer = Observer()
        file_observer.schedule(event_handler, str(STAR_PROGRAMS_DIR), recursive=False)
        file_observer.start()
        logger.info("File observer started successfully")
        
        # Initial sync and render setup
        await sync_programs()
        await update_render_tasks()
        logger.info("Initial sync and render tasks started successfully")
        
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        logger.info("Cleaning up...")
        if file_observer:
            file_observer.stop()
            file_observer.join()
        await cleanup()
        logger.info("=== Lifespan context ended ===")

app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PixletRenderer:
    def __init__(self):
        self.current_renders = {}
        
    async def render_app(self, app_path: Path, output_path: Path, config: dict = None) -> bool:
        """Renders a Pixlet app directly to GIF"""
        try:
            app_path = Path(app_path)
            output_path = Path(output_path)

            if not str(app_path).endswith('.star'):
                logger.error(f"Invalid file extension for {app_path}")
                return False

            output_path = output_path.with_suffix('.gif')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = ["pixlet", "render", str(app_path.absolute())]
            
            if config:
                for key, value in config.items():
                    cmd.append(f"{key}={value}")
            
            cmd.extend(["--gif", "-o", str(output_path.absolute())])
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Render failed: {stderr.decode()}")
                return False
            
            logger.info(f"Successfully rendered to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error rendering {app_path}: {e}")
            return False
    
    async def copy_to_slot(self, temp_path: Path, slot_num: int) -> bool:
        """Copies rendered GIF to the appropriate slot"""
        try:
            dest_path = GIF_DIR / f"slot{slot_num}.gif"
            async with aiofiles.open(temp_path, 'rb') as src, \
                       aiofiles.open(dest_path, 'wb') as dst:
                await dst.write(await src.read())
            logger.info(f"Copied {temp_path} to {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Error copying to slot: {e}")
            return False

async def sync_programs():
    """Synchronizes programs from star_programs to cache"""
    try:
        # Create cache directory if it doesn't exist
        CACHE_DIR.mkdir(exist_ok=True)
        
        # Copy all .star files and metadata
        for item in STAR_PROGRAMS_DIR.iterdir():
            if item.suffix == '.star' or item.name == 'program_metadata.json':
                dest_path = CACHE_DIR / item.name
                shutil.copy2(item, dest_path)
                logger.info(f"Synced {item.name} to cache")
        
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

        renderer = PixletRenderer()
        slot_number = 0

        for program_name, config in metadata.items():
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