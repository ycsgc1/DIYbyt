#!/usr/bin/env python3
import sys
import os
import json
import time
import logging
import requests
from pathlib import Path

# Enhanced debug logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG level
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def fetch_metadata(server_url, timeout=10):
    """Fetch metadata with enhanced error reporting"""
    try:
        metadata_url = f"{server_url}:3001/api/metadata"
        logger.debug(f"Attempting to fetch from: {metadata_url}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"Environment variables:")
        for key, value in os.environ.items():
            if 'DIYBYT' in key:
                logger.debug(f"  {key}: {value}")
        
        response = requests.get(metadata_url, timeout=timeout)
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Received data: {json.dumps(data, indent=2)}")
            return data
        else:
            logger.error(f"Failed to fetch metadata: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error fetching metadata: {str(e)}", exc_info=True)
        return None

def main():
    logger.info("Starting debug version of DIYbyt Display Service")
    
    # Get server URL from environment or use default
    server_url = os.getenv('DIYBYT_SERVER_URL', 'http://192.168.1.188')
    logger.debug(f"Using server URL: {server_url}")
    
    try:
        while True:
            logger.info("Fetching metadata...")
            metadata = fetch_metadata(server_url)
            
            if metadata:
                logger.info("Successfully retrieved metadata")
                # Process the metadata here
                time.sleep(5)  # Wait before next fetch
            else:
                logger.error("Failed to get metadata, waiting before retry")
                time.sleep(5)
                
    except KeyboardInterrupt:
        logger.info("Exiting due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)

if __name__ == "__main__":
    main()