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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/diybyt/renderer.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_DIR = Path("/opt/DIYbyt")
PROGRAMS_DIR = BASE_DIR / "star_programs"
RENDER_DIR = BASE_DIR / "render"
GIF_DIR = RENDER_DIR / "gifs"
TEMP_DIR = RENDER_DIR / "temp"
FAILED_DIR = RENDER_DIR / "failed"  # New directory for failed renders

# Global state
render_tasks: Dict[str, asyncio.Task] = {}
server_instance: Optional[uvicorn.Server] = None
should_exit = False
file_observer: Optional[Observer] = None

class ProgramChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self._debounce_task = None

    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.star', 'program_metadata.json')):
            logger.info(f"Detected change in {event.src_path}")
            if self._debounce_task:
                self._debounce_task.cancel()
            self._debounce_task = asyncio.create_task(self._debounced_callback())

    async def _debounced_callback(self):
        await asyncio.sleep(1)  # Wait for multiple rapid changes to settle
        await self.callback()

class PixletRenderer:
    def __init__(self):
        self.current_renders = {}
        self.failed_renders = set()
        logger.info("PixletRenderer initialized")
        
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
                logger.error(f"Command failed with return code: {process.returncode}")
                logger.error(f"STDOUT: {stdout.decode()}")
                logger.error(f"STDERR: {stderr.decode()}")
                
                # Save failed render information
                failed_info = {
                    'timestamp': datetime.now().isoformat(),
                    'command': ' '.join(cmd),
                    'returncode': process.returncode,
                    'stdout': stdout.decode(),
                    'stderr': stderr.decode()
                }
                
                failed_path = FAILED_DIR / f"{app_path.stem}_failed.json"
                async with aiofiles.open(failed_path, 'w') as f:
                    await f.write(json.dumps(failed_info, indent=2))
                
                self.failed_renders.add(app_path.stem)
                return False
            
            self.failed_renders.discard(app_path.stem)
            logger.info(f"Successfully rendered to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error rendering {app_path}: {e}")
            self.failed_renders.add(app_path.stem)
            return False
    
    async def copy_to_slot(self, temp_path: Path, slot_num: int) -> bool:
        """Copies rendered GIF to the appropriate slot"""
        try:
            src_path = Path(temp_path)
            dest_path = GIF_DIR / f"slot{slot_num}.gif"
            
            # Don't copy if render failed
            if src_path.stem in self.failed_renders:
                logger.warning(f"Skipping copy for failed render: {src_path.stem}")
                if dest_path.exists():
                    await aiofiles.os.remove(dest_path)
                return False

            # Ensure the source file exists
            if not src_path.exists():
                logger.error(f"Source file {src_path} does not exist")
                return False

            # Ensure destination directory exists and is writable
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use shutil for atomic copy
            shutil.copy2(src_path, dest_path)
            
            # Set permissions on the destination file
            os.chmod(dest_path, 0o666)
            
            logger.info(f"Copied {src_path} to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying to slot: {e}")
            return False

async def setup_file_watcher():
    """Sets up file system watching for program directory"""
    global file_observer
    
    if file_observer:
        file_observer.stop()
        file_observer = None

    handler = ProgramChangeHandler(update_render_tasks)
    observer = Observer()
    observer.schedule(handler, str(PROGRAMS_DIR), recursive=False)
    observer.start()
    file_observer = observer
    logger.info("File watcher set up for program directory")

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
            success = await renderer.render_app(program_path, temp_output, render_config)
            
            if success:
                await renderer.copy_to_slot(temp_output, slot_number)
            else:
                # Remove the slot file if render failed
                slot_file = GIF_DIR / f"slot{slot_number}.gif"
                if slot_file.exists():
                    await aiofiles.os.remove(slot_file)
            
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
        logger.info("Starting update_render_tasks")
        metadata_path = PROGRAMS_DIR / "program_metadata.json"
        logger.info(f"Looking for metadata at: {metadata_path}")
        if not metadata_path.exists():
            logger.warning("No metadata file found")
            return

        # Log metadata content
        async with aiofiles.open(metadata_path) as f:
            metadata_content = await f.read()
            logger.info(f"Metadata content: {metadata_content}")
            metadata = json.loads(metadata_content)
            logger.info(f"Loaded metadata with {len(metadata)} programs")

        # Cancel existing tasks
        logger.info(f"Cancelling {len(render_tasks)} existing tasks")
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        render_tasks.clear()

        # Clean up all GIF slots before starting new renders
        await cleanup_gif_slots(0)  # Clear all slots

        renderer = PixletRenderer()
        slot_number = 0

        # Sort items by the order specified in metadata (if exists) or by name
        sorted_programs = sorted(
            metadata.items(),
            key=lambda x: (x[1].get("order", float('inf')), x[0])
        )

        logger.info(f"Processing {len(sorted_programs)} programs")
        for program_name, config in sorted_programs:
            if not program_name or not config.get("enabled", False):
                logger.info(f"Skipping disabled program: {program_name}")
                continue

            program_path = PROGRAMS_DIR / program_name
            if not program_path.exists() or not program_name.endswith('.star'):
                logger.warning(f"Invalid program file: {program_name}")
                continue

            refresh_rate = config.get("refresh_rate", 60)
            logger.info(f"Starting render task for {program_name} with refresh rate {refresh_rate}")
            
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

        logger.info(f"Successfully started {len(render_tasks)} render tasks")

    except Exception as e:
        logger.error(f"Error updating render tasks: {e}")
        raise

async def cleanup_gif_slots(active_slots: int):
    """Cleanup unused GIF slots"""
    try:
        # Get all existing slot files
        existing_slots = [f for f in GIF_DIR.glob("slot*.gif")]
        logger.info(f"Found {len(existing_slots)} existing slot files")
        
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Starting lifespan context ===")
    try:
        # Create required directories
        for directory in [PROGRAMS_DIR, RENDER_DIR, GIF_DIR, TEMP_DIR, FAILED_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory created/verified: {directory}")
        
        # Set up file watcher
        await setup_file_watcher()
        
        logger.info("About to call update_render_tasks")
        # Initial render setup
        await update_render_tasks()
        logger.info("Initial render tasks completed")
        
        logger.info("Yielding in lifespan")
        yield
        logger.info("After yield in lifespan")
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise
    finally:
        logger.info("Cleaning up...")
        if file_observer:
            file_observer.stop()
            file_observer.join()
        await cleanup()
        logger.info("=== Lifespan context ended ===")

# ... (rest of the code remains the same)

def handle_exit(signum, frame):
    """Handle exit signals gracefully"""
    global should_exit
    logger.info(f"Received signal {signum}. Starting graceful shutdown...")
    should_exit = True
    if server_instance:
        asyncio.create_task(server_instance.shutdown())

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# Create the FastAPI app
app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/sync")
async def trigger_sync():
    """Endpoint to trigger manual render update"""
    try:
        logger.info("Manual render update triggered via HTTP endpoint")
        await update_render_tasks()
        return {"status": "success", "message": "Renders restarted"}
    except Exception as e:
        logger.error(f"Error during manual update: {e}")
        return {"status": "error", "message": str(e)}

# Serve static files (gifs)
app.mount("/gifs", StaticFiles(directory=GIF_DIR), name="gifs")

class CustomServer(uvicorn.Server):
    async def shutdown(self, sockets=None):
        global should_exit
        should_exit = True
        
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                
        await super().shutdown(sockets=sockets)

if __name__ == "__main__":
    logger.info(f"Starting renderer. Using programs from: {PROGRAMS_DIR}")
    logger.info(f"Directory contents: {list(PROGRAMS_DIR.iterdir())}")
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = CustomServer(config=config)
    server_instance = server
    
    try:
        server.run()
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        asyncio.run(cleanup())