"""
Launcher Updater Module
Handles self-updating of the PyPottery Launcher
"""

import os
import sys
import shutil
import zipfile
import tempfile
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request
from typing import Optional, Callable

class LauncherUpdater:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.launcher_path = base_path / "launcher"
        
    def update(self, download_url: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> bool:
        """
        Update the launcher from a zip URL.
        
        Args:
            download_url: URL to the zip file (GitHub release)
            progress_callback: Callback(message, percent)
            
        Returns:
            True if successful
        """
        try:
            # Create temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / "update.zip"
                
                # 1. Download
                if progress_callback:
                    progress_callback("Downloading update...", 0.0)
                
                self._download_file(download_url, zip_path, progress_callback)
                
                # 2. Extract
                if progress_callback:
                    progress_callback("Extracting files...", 50.0)
                
                extract_path = temp_path / "extracted"
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                # Find the 'launcher' directory in extracted files
                # GitHub zips usually have a root folder like 'PyPottery-main'
                source_launcher = None
                for root, dirs, files in os.walk(extract_path):
                    if "launcher" in dirs:
                        possible_path = Path(root) / "launcher"
                        # Verify it looks like our launcher
                        if (possible_path / "gui.py").exists():
                            source_launcher = possible_path
                            break
                            
                if not source_launcher:
                    raise Exception("Could not find 'launcher' directory in update package")
                
                # 3. Install (Overwrite)
                if progress_callback:
                    progress_callback("Installing updates...", 75.0)
                
                # We can replace files even if running, usually
                # But to be safe, we'll iterate and copy
                self._copy_tree(source_launcher, self.launcher_path)
                
                if progress_callback:
                    progress_callback("Update complete!", 100.0)
                    
                return True
                
        except Exception as e:
            print(f"Update failed: {e}")
            return False

    def _download_file(self, url: str, dest: Path, callback: Optional[Callable] = None):
        """Download file with progress"""
        req = Request(url, headers={"User-Agent": "PyPottery-Launcher"})
        with urlopen(req) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0 and callback:
                        percent = min(40.0, (downloaded / total_size) * 40.0) # Scale to 0-40% of total process
                        callback(f"Downloading... {int(percent/0.4)}%", percent)

    def _copy_tree(self, src: Path, dst: Path):
        """Copy directory tree, overwriting files"""
        if not dst.exists():
            dst.mkdir(parents=True)
            
        for item in src.iterdir():
            dst_item = dst / item.name
            if item.is_dir():
                self._copy_tree(item, dst_item)
            else:
                shutil.copy2(item, dst_item)

    def restart(self):
        """Restart the application"""
        # Use the current python interpreter
        python = sys.executable
        # Restart the script
        os.execl(python, python, *sys.argv)
