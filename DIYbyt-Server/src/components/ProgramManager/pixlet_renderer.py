import subprocess
import time
import requests
from datetime import datetime
from pathlib import Path
import json

class PixletRenderer:
    def __init__(self, server_url="http://192.168.1.172:5000", cache_dir="cache"):
        self.server_url = server_url
        self.cache_dir = Path(cache_dir)
        self.program_metadata = {}
        self.load_program_metadata()
        self.cache = {}
        self.load_cache()

    def load_program_metadata(self):
        metadata_path = self.cache_dir / "program_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                self.program_metadata = json.load(f)
        else:
            self.program_metadata = {}
            print("No program_metadata.json file found in the cache directory.")

    def load_cache(self):
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".star"):
                filepath = self.cache_dir / filename
                with open(filepath, "r") as f:
                    self.cache[filename] = {
                        "content": f.read()
                    }

    def render_app(self, app_name, output_path):
        """Renders a Pixlet app directly to GIF"""
        try:
            config = self.program_metadata[app_name].get("config", {})
            cmd = ["pixlet", "render", "-"]
            
            # Add config parameters if they exist
            for key, value in config.items():
                cmd.append(f"{key}={value}")
            
            cmd.extend(["--gif", "-o", str(output_path)])
            
            print(f"Executing command: {' '.join(cmd)}")
            
            process = subprocess.run(cmd, input=self.cache[f"{app_name}.star"]["content"].encode(), capture_output=True, text=True)
            
            if process.returncode != 0:
                print(f"Command failed with return code: {process.returncode}")
                print(f"STDOUT: {process.stdout}")
                print(f"STDERR: {process.stderr}")
                raise Exception(f"Pixlet render failed: {process.stdout}\n{process.stderr}")
            
            print(f"Successfully rendered to {output_path}")
            return True
            
        except Exception as e:
            print(f"Error rendering {app_name}:")
            print(f"Exception type: {type(e)}")
            print(f"Exception message: {str(e)}")
            print(f"Full command: {' '.join(cmd)}")
            return False

    def update_server(self, gif_path, slot_id):
        """Uploads GIF to the server"""
        try:
            print(f"Attempting to upload {gif_path} to slot {slot_id}")
            with open(gif_path, 'rb') as f:
                response = requests.post(
                    f"{self.server_url}/update/{slot_id}",
                    data=f.read(),
                    headers={'Content-Type': 'image/gif'}
                )
            if response.status_code == 200:
                print(f"Successfully updated {slot_id}")
                return True
            else:
                print(f"Server responded with status code: {response.status_code}")
                print(f"Response text: {response.text}")
                return False
        except Exception as e:
            print(f"Error updating server:")
            print(f"Exception type: {type(e)}")
            print(f"Exception message: {str(e)}")
            return False

    def run(self):
        """Main runtime loop"""
        print("Starting Pixlet Renderer...")
        print(f"Server URL: {self.server_url}")
        print("Configured apps:")
        for app_name, config in self.program_metadata.items():
            print(f"  - {app_name}: Path: {config['path']}, Slot: {config['slot']}")
        
        # Create temp directory for GIFs if it doesn't exist
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        print("Created temp directory")
        
        # Track last update time for each app
        last_updates = {app_name: datetime.min for app_name in self.program_metadata}
        
        while True:
            current_time = datetime.now()
            
            for app_name, config in self.program_metadata.items():
                if config["enabled"]:
                    # Check if it's time to update this app
                    time_since_update = (current_time - last_updates[app_name]).total_seconds()
                    if time_since_update >= config["duration"] * (1 if config["units"] == "seconds" else config["duration"]):
                        print(f"\nUpdate cycle for {app_name}")
                        
                        # Set up temporary output path
                        output_path = temp_dir / f"{app_name}.gif"
                        print(f"Output path: {output_path}")
                        
                        # Render the app
                        if self.render_app(app_name, output_path):
                            # Update the server
                            if self.update_server(output_path, config["slot"]):
                                print(f"Successfully completed update cycle for {app_name}")
                                last_updates[app_name] = current_time
                            else:
                                print(f"Failed to update server for {app_name}")
                        else:
                            print(f"Failed to render {app_name}")
                        
                        # Cleanup
                        if output_path.exists():
                            print(f"Cleaning up {output_path}")
                            output_path.unlink()
            
            # Sleep for a short time before next check
            time.sleep(1)

def main():
    print("In main function")
    renderer = PixletRenderer()
    try:
        renderer.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        temp_dir = Path("temp")
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                file.unlink()
            temp_dir.rmdir()
        print("Cleanup complete")

if __name__ == "__main__":
    print("Starting main()")
    main()