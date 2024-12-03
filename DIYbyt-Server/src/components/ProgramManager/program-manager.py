import os
import time
import hashlib
from pathlib import Path
import json

class StarFileCacher:
    def __init__(self, star_programs_dir="star_programs", cache_dir="cache"):
        self.star_programs_dir = Path(star_programs_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.program_metadata = {}
        self.load_program_metadata()
        self.cache = {}
        self.update_flag_path = self.cache_dir / "update_flag.txt"

    def load_program_metadata(self):
        metadata_path = self.star_programs_dir / "program_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                self.program_metadata = json.load(f)
        else:
            self.program_metadata = {}
            print("No program_metadata.json file found.")

    def get_file_hash(self, filepath):
        """Calculate the hash of a file to detect changes"""
        with open(filepath, "rb") as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
        return file_hash.hexdigest()

    def update_cache(self):
        """Check for changes in .star files and update the cache"""
        for filename in os.listdir(self.star_programs_dir):
            if filename.endswith(".star"):
                filepath = self.star_programs_dir / filename
                if filename not in self.cache or self.get_file_hash(filepath) != self.cache[filename]["hash"]:
                    print(f"Updating cache for {filename}")
                    with open(filepath, "r") as f:
                        self.cache[filename] = {
                            "hash": self.get_file_hash(filepath),
                            "content": f.read()
                        }
                    self.set_update_flag()

    def set_update_flag(self):
        """Set the update flag to indicate that the cache has been updated"""
        with open(self.update_flag_path, "w") as f:
            f.write("true")

    def clear_update_flag(self):
        """Clear the update flag"""
        if self.update_flag_path.exists():
            self.update_flag_path.unlink()

    def run(self):
        """Main loop to monitor for changes and update the cache"""
        print("Starting Star File Cacher...")
        print(f"Star Programs Directory: {self.star_programs_dir}")
        print(f"Cache Directory: {self.cache_dir}")

        while True:
            self.update_cache()
            time.sleep(5)  # Check for updates every 5 seconds

def main():
    cacher = StarFileCacher()
    try:
        cacher.run()
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()