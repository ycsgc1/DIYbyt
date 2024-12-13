#!/usr/bin/env python3
import sys
import os
import json
import time
import logging
import requests
from PIL import Image
import io
from pathlib import Path
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import threading
from queue import Queue

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/diybyt/display.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
SERVER_URL = os.getenv('DIYBYT_SERVER_URL', 'http://localhost')

class GIFPreprocessor:
    def __init__(self, matrix):
        self.matrix = matrix
        self.queue = Queue(maxsize=1)
        self.current_thread = None

    def start_preprocessing(self, gif_url):
        """Start preprocessing the next GIF in a separate thread"""
        if self.current_thread and self.current_thread.is_alive():
            logger.warning("Previous preprocessing thread still running")
            return

        self.current_thread = threading.Thread(
            target=self._preprocess_gif,
            args=(gif_url,),
            daemon=True
        )
        self.current_thread.start()

    def _preprocess_gif(self, gif_url):
        """Worker function to fetch and preprocess a GIF"""
        try:
            # Clear queue of any old preprocessed data
            while not self.queue.empty():
                self.queue.get_nowait()

            gif = self._get_gif_from_server(gif_url)
            if gif:
                canvases = self._process_frames(gif)
                if canvases:
                    self.queue.put(canvases)
                gif.close()
        except Exception as e:
            logger.error(f"Error preprocessing GIF: {e}", exc_info=True)

    def _get_gif_from_server(self, url, timeout=10):
        """Fetch GIF from server with timeout and error handling"""
        try:
            logger.info(f"Fetching from {url}")
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return Image.open(io.BytesIO(response.content))
            else:
                logger.error(f"Failed to fetch GIF: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching GIF: {e}", exc_info=True)
            return None

    def _process_frames(self, gif):
        """Process all frames of the GIF into canvases"""
        try:
            canvases = []
            num_frames = gif.n_frames
            logger.info(f"Preprocessing {num_frames} frames...")
            
            for frame_index in range(num_frames):
                gif.seek(frame_index)
                frame = gif.copy()
                frame.thumbnail((self.matrix.width, self.matrix.height), Image.LANCZOS)
                canvas = self.matrix.CreateFrameCanvas()
                canvas.SetImage(frame.convert('RGB'))
                canvases.append(canvas)
            
            return canvases
        except Exception as e:
            logger.error(f"Error processing frames: {e}", exc_info=True)
            return None

    def get_next_frames(self, timeout=None):
        """Get the preprocessed frames, waiting if necessary"""
        try:
            return self.queue.get(timeout=timeout)
        except:
            return None

def setup_matrix():
    """Initialize the RGB matrix with settings from environment variables"""
    options = RGBMatrixOptions()
    options.rows = int(os.getenv('DIYBYT_MATRIX_ROWS', '32'))
    options.cols = int(os.getenv('DIYBYT_MATRIX_COLS', '64'))
    options.gpio_slowdown = int(os.getenv('DIYBYT_GPIO_SLOWDOWN', '4'))
    options.disable_hardware_pulsing = os.getenv('DIYBYT_DISABLE_HARDWARE_PULSING', 'true').lower() == 'true'
    
    if os.getenv('DIYBYT_MATRIX_CHAIN_LENGTH'):
        options.chain_length = int(os.getenv('DIYBYT_MATRIX_CHAIN_LENGTH'))
    if os.getenv('DIYBYT_MATRIX_PARALLEL'):
        options.parallel = int(os.getenv('DIYBYT_MATRIX_PARALLEL'))
    if os.getenv('DIYBYT_MATRIX_BRIGHTNESS'):
        options.brightness = int(os.getenv('DIYBYT_MATRIX_BRIGHTNESS'))
    
    return RGBMatrix(options=options)

def fetch_metadata(server_url, timeout=10):
    """Fetch metadata directly from server"""
    try:
        metadata_url = f"{server_url}:3001/api/metadata"
        logger.info(f"Fetching metadata from {metadata_url}")
        response = requests.get(metadata_url, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to fetch metadata: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error fetching metadata: {e}", exc_info=True)
        return None

def process_metadata(metadata):
    """Process metadata into list of enabled programs"""
    if not metadata:
        return []
    
    enabled_programs = []
    for program_name, program_config in metadata.items():
        if program_name == '_config':
            continue
        
        if program_config.get('enabled', False):
            program_config = {
                'name': program_name,
                'duration': program_config.get('duration', '30'),
                'durationUnit': program_config.get('durationUnit', 'seconds'),
                'order': program_config.get('order', 999),
                'slot': f'slot{len(enabled_programs)}.gif'
            }
            enabled_programs.append(program_config)
    
    return sorted(enabled_programs, key=lambda x: x['order'])

def display_gif(matrix, canvases, duration, duration_unit):
    """Display preprocessed GIF frames based on duration settings"""
    try:
        num_frames = len(canvases)
        cur_frame = 0
        
        if duration_unit == "loops":
            logger.info(f"Displaying for {duration} loops")
            for _ in range(int(duration)):
                for cur_frame in range(num_frames):
                    matrix.SwapOnVSync(canvases[cur_frame])
        else:  # seconds
            logger.info(f"Displaying for {duration} seconds")
            start_time = time.time()
            while time.time() - start_time < float(duration):
                matrix.SwapOnVSync(canvases[cur_frame])
                cur_frame = (cur_frame + 1) % num_frames
                    
    except KeyboardInterrupt:
        logger.info("Display stopped by user")
        raise
    except Exception as e:
        logger.error(f"Error displaying GIF: {e}", exc_info=True)

def main():
    logger.info("Starting DIYbyt Display Service")
    
    matrix = setup_matrix()
    logger.info("Matrix initialized")
    
    preprocessor = GIFPreprocessor(matrix)
    
    while True:
        try:
            # Start of new cycle - get fresh metadata
            logger.info("Starting new display cycle")
            metadata = fetch_metadata(SERVER_URL)
            programs = process_metadata(metadata)
            
            if not programs:
                logger.warning("No enabled programs found")
                time.sleep(5)
                continue
            
            # Start preprocessing first GIF after metadata check
            next_gif_url = f"{SERVER_URL}:8000/gifs/{programs[0]['slot']}"
            preprocessor.start_preprocessing(next_gif_url)
            
            # Display all programs in sequence
            for i, program in enumerate(programs):
                logger.info(f"\nDisplaying program: {program['name']}")
                
                # Get the preprocessed frames
                canvases = preprocessor.get_next_frames()
                
                if canvases:
                    # Start preprocessing next GIF while displaying current one
                    if i < len(programs) - 1:
                        next_gif_url = f"{SERVER_URL}:8000/gifs/{programs[i + 1]['slot']}"
                        preprocessor.start_preprocessing(next_gif_url)
                    
                    # Display current GIF
                    display_gif(
                        matrix,
                        canvases,
                        duration=program['duration'],
                        duration_unit=program['durationUnit']
                    )
                else:
                    logger.error(f"Failed to get GIF for {program['name']}")
                    time.sleep(5)
            
            logger.info("Display cycle complete")
                
        except KeyboardInterrupt:
            logger.info("\nExiting...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    main()