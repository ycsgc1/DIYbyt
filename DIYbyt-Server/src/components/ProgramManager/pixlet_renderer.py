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
PROGRAMS_DIR = BASE_DIR / "star_programs"  # Using star_programs directly now
RENDER_DIR = BASE_DIR / "render"
GIF_DIR = RENDER_DIR / "gifs"
TEMP_DIR = RENDER_DIR / "temp"

# Global state
render_tasks: Dict[str, asyncio.Task] = {}
server_instance: Optional[uvicorn.Server] = None
should_exit = False

# Create the FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class PixletRenderer:
    def __init__(self):
        self.current_renders = {}
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
                return False
            
            logger.info(f"Successfully rendered to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error rendering {app_path}: {e}")
            return False
    
    async def copy_to_slot(self, temp_path: Path, slot_num: int) -> bool:
        """Copies rendered GIF to the appropriate slot"""
        try:
            src_path = Path(temp_path)
            dest_path = GIF_DIR / f"slot{slot_num}.gif"
            
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


async def update_render_tasks():
    """Updates the running render tasks based on current metadata"""
    try:
        logger.info("Starting update_render_tasks")
        metadata_path = PROGRAMS_DIR / "program_metadata.json"
        if not metadata_path.exists():
            logger.warning("No metadata file found")
            return

        async with aiofiles.open(metadata_path) as f:
            metadata = json.loads(await f.read())
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

        # Clean up old GIF slots
        active_count = len([p for p in metadata.items() if p[1].get("enabled", False)])
        logger.info(f"Found {active_count} active programs")
        await cleanup_gif_slots(active_count)

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
        for directory in [PROGRAMS_DIR, RENDER_DIR, GIF_DIR, TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory created/verified: {directory}")
        
        # Initial render setup
        await update_render_tasks()
        logger.info("Initial render tasks started successfully")
        
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        logger.info("Cleaning up...")
        await cleanup()
        logger.info("=== Lifespan context ended ===")

# Attach the lifespan to the app
app.lifespan = lifespan

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

async def cleanup():
    """Cleanup temporary files and tasks on shutdown"""
    try:
        logger.info("Starting cleanup process")
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
            logger.info("Temporary directory cleaned up")
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