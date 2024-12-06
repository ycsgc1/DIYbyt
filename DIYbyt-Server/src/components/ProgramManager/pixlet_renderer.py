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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CACHE_DIR = Path("/opt/DIYbyt/render/star_programs_cache")
GIF_DIR = Path("/opt/DIYbyt/render/gifs")
TEMP_DIR = Path("/opt/DIYbyt/render/temp")

# Global state
render_tasks: Dict[str, asyncio.Task] = {}
server_instance: Optional[uvicorn.Server] = None
should_exit = False

# Signal handlers
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up renderer tasks...")
    await update_render_tasks()
    yield
    # Shutdown
    logger.info("Cleaning up renderer tasks...")
    await cleanup()

# Initialize FastAPI with lifespan
app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
CACHE_DIR.mkdir(exist_ok=True)
GIF_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

class PixletRenderer:
    def __init__(self):
        self.current_renders = {}
        
    async def render_app(self, app_path: Path, output_path: Path, config: dict = None) -> bool:
        """Renders a Pixlet app directly to GIF"""
        try:
            # Ensure paths are Path objects
            app_path = Path(app_path)
            output_path = Path(output_path)

            # Validate the input file has .star extension
            if not str(app_path).endswith('.star'):
                logger.error(f"Invalid file extension for {app_path}. Must be a .star file.")
                return False

            # Ensure output path has .gif extension
            output_path = output_path.with_suffix('.gif')

            # Create parent directories if they don't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Construct command
            cmd = ["pixlet", "render", str(app_path.absolute())]
            
            if config:
                config_args = []
                for key, value in config.items():
                    config_args.append(f"{key}={value}")
                if config_args:
                    cmd.extend(config_args)
            
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
                raise Exception(f"Pixlet render failed: {stdout.decode()}\n{stderr.decode()}")
            
            logger.info(f"Successfully rendered to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error rendering {app_path}:")
            logger.error(f"Exception message: {str(e)}")
            return False
    
    async def copy_to_slot(self, temp_path: Path, slot_num: int) -> bool:
        """Copies rendered GIF to the appropriate slot"""
        try:
            dest_path = GIF_DIR / f"slot{slot_num}.gif"
            shutil.copy2(temp_path, dest_path)
            logger.info(f"Copied {temp_path} to {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Error copying to slot: {e}")
            return False

async def continuous_render(renderer: PixletRenderer, program_name: str, program_path: Path, 
                          slot_number: int, config: dict, refresh_rate: int):
    """Continuously renders a program at specified intervals"""
    temp_output = TEMP_DIR / f"{program_name}.gif"
    
    while not should_exit:
        try:
            start_time = datetime.now()
            
            # Perform the render
            if await renderer.render_app(program_path, temp_output, config.get("config", {})):
                await renderer.copy_to_slot(temp_output, slot_number)
            
            # Cleanup temp file
            if temp_output.exists():
                temp_output.unlink()
            
            # Calculate sleep time (accounting for render duration)
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(0.1, refresh_rate - elapsed)
            
            await asyncio.sleep(sleep_time)
            
        except asyncio.CancelledError:
            logger.info(f"Render task for {program_name} cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in continuous render for {program_name}: {e}")
            if not should_exit:
                await asyncio.sleep(5)  # Wait before retrying on error

async def update_render_tasks():
    """Updates the running render tasks based on current metadata"""
    try:
        metadata_path = CACHE_DIR / "program_metadata.json"
        if not metadata_path.exists():
            logger.warning("No metadata file found in cache")
            return

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Log the metadata content
        logger.info(f"Loaded metadata: {json.dumps(metadata, indent=2)}")

        # Cancel existing tasks
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        render_tasks.clear()

        # Create new renderer instance
        renderer = PixletRenderer()
        slot_number = 0

        for program_name, config in metadata.items():
            if not program_name or not config.get("enabled", False):
                logger.info(f"Skipping disabled or empty program: {program_name}")
                continue

            program_path = CACHE_DIR / program_name
            if not program_path.exists() or not program_name.endswith('.star'):
                logger.warning(f"Invalid program file: {program_name}")
                continue

            # Get refresh rate from metadata (default to 60 seconds if not specified)
            refresh_rate = config.get("refresh_rate", 60)
            logger.info(f"Starting render task for {program_name} with refresh rate {refresh_rate}")
            
            # Create new continuous render task
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

@app.post("/update")
async def update_programs(file: UploadFile = File(...)):
    """
    Receives a zip file containing the star_programs directory,
    updates the cache, and triggers re-rendering.
    """
    try:
        # Create a temporary file to store the upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        try:
            # Clear existing cache
            if CACHE_DIR.exists():
                shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir()

            # Extract new files
            with zipfile.ZipFile(temp_file.name, 'r') as zip_ref:
                zip_ref.extractall(CACHE_DIR)

            # Update render tasks
            await update_render_tasks()

            return {"status": "success", "message": "Programs updated and renders restarted"}

        finally:
            # Clean up temp file
            os.unlink(temp_file.name)

    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return {"status": "error", "message": str(e)}

# Serve static files (gifs)
app.mount("/gifs", StaticFiles(directory=GIF_DIR), name="gifs")

async def cleanup():
    """Cleanup temporary files and tasks on shutdown"""
    try:
        # Cancel all running tasks
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

class CustomServer(uvicorn.Server):
    """Custom server class to handle graceful shutdown"""
    async def shutdown(self, sockets=None):
        """Shutdown the server gracefully"""
        # Set the should_exit flag
        global should_exit
        should_exit = True
        
        # Cancel all tasks
        for task in render_tasks.values():
            if not task.done():
                task.cancel()
                
        # Call parent shutdown
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