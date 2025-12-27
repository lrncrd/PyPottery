"""
Application Manager for PyPottery Suite
Handles downloading, launching, and managing PyPottery applications
"""

import os
import sys
import subprocess
import platform
import json
import shutil
import zipfile
import socket
import webbrowser
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
from dataclasses import dataclass
from urllib.request import urlopen, Request
from urllib.error import URLError


@dataclass
class AppInfo:
    """Information about a PyPottery application"""
    id: str  # e.g., "PyPotteryLayout"
    name: str  # e.g., "PyPottery Layout"
    description: str
    repo_owner: str
    repo_name: str
    entry_script: str
    port: int
    min_ram_gb: int
    recommended_ram_gb: int
    requires_gpu: bool
    icon: str
    logo_path: Optional[str] = None
    installed: bool = False
    installed_version: Optional[str] = None
    latest_version: Optional[str] = None
    update_available: bool = False
    is_running: bool = False
    process: Optional[subprocess.Popen] = None


@dataclass 
class AppStatus:
    """Status of a running application"""
    app_id: str
    is_running: bool
    port: int
    pid: Optional[int] = None
    url: Optional[str] = None


@dataclass
class DownloadProgress:
    """Progress information for download callbacks"""
    app_id: str
    stage: str  # "downloading", "extracting", "complete", "error"
    message: str
    bytes_downloaded: int
    bytes_total: int
    percent: float  # 0-100


class AppManager:
    """
    Manages PyPottery applications: download, install, launch, and monitor.
    """
    
    def __init__(self, base_path: Path, python_executable: Path):
        self.base_path = Path(base_path)
        self.apps_path = self.base_path / "apps"
        self.python_executable = Path(python_executable)
        self.is_windows = platform.system() == "Windows"
        
        # Load app configurations
        self.apps: Dict[str, AppInfo] = {}
        self._load_app_configs()
        
        # Running processes
        self._processes: Dict[str, subprocess.Popen] = {}
        
        # Callbacks
        self._status_callback: Optional[Callable[[str, str], None]] = None
        self._download_callback: Optional[Callable[[DownloadProgress], None]] = None
    
    def _load_app_configs(self):
        """Load application configurations from JSON"""
        config_file = Path(__file__).parent / "config" / "apps.json"
        
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            for app_id, app_config in config.get("apps", {}).items():
                self.apps[app_id] = AppInfo(
                    id=app_id,
                    name=app_config.get("name", app_id),
                    description=app_config.get("description", ""),
                    repo_owner=app_config.get("repo_owner", "lrncrd"),
                    repo_name=app_config.get("repo_name", app_id),
                    entry_script=app_config.get("entry_script", "app.py"),
                    port=app_config.get("port", 5000),
                    min_ram_gb=app_config.get("min_ram_gb", 4),
                    recommended_ram_gb=app_config.get("recommended_ram_gb", 8),
                    requires_gpu=app_config.get("requires_gpu", False),
                    icon=app_config.get("icon", "📦"),
                    logo_path=app_config.get("logo", None)
                )
        
        # Check installed status
        self._refresh_installed_status()
    
    def _refresh_installed_status(self):
        """Check which apps are installed"""
        for app_id, app in self.apps.items():
            app_path = self.apps_path / app_id
            app.installed = app_path.exists() and (app_path / app.entry_script).exists()
            
            # Check version file
            version_file = app_path / ".version"
            if version_file.exists():
                app.installed_version = version_file.read_text().strip()
    
    def set_status_callback(self, callback: Callable[[str, str], None]):
        """Set callback for status updates: callback(app_id, message)"""
        self._status_callback = callback
    
    def set_download_callback(self, callback: Callable[["DownloadProgress"], None]):
        """Set callback for download progress updates"""
        self._download_callback = callback
    
    def _report_download_progress(self, app_id: str, stage: str, message: str,
                                   bytes_downloaded: int = 0, bytes_total: int = 0):
        """Report download progress to callback if set"""
        percent = (bytes_downloaded / bytes_total * 100) if bytes_total > 0 else 0
        if self._download_callback:
            self._download_callback(DownloadProgress(
                app_id=app_id,
                stage=stage,
                message=message,
                bytes_downloaded=bytes_downloaded,
                bytes_total=bytes_total,
                percent=percent
            ))
    
    def _report_status(self, app_id: str, message: str):
        """Report status update"""
        if self._status_callback:
            self._status_callback(app_id, message)
    
    def get_app_list(self) -> List[AppInfo]:
        """Get list of all applications"""
        return list(self.apps.values())
    
    def get_app(self, app_id: str) -> Optional[AppInfo]:
        """Get specific application info"""
        return self.apps.get(app_id)
    
    def is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def _detect_version(self, app_path: Path) -> Optional[str]:
        """Detect version from application files"""
        # 1. Try version.txt / VERSION
        for v_file in ["version.txt", "VERSION"]:
            vf = app_path / v_file
            if vf.exists():
                try:
                    return vf.read_text(encoding='utf-8').strip()
                except:
                    pass
            
        # 2. Try __init__.py or _version.py in package directory
        # Look for __version__ = "..."
        try:
            import re
            for item in app_path.rglob("*.py"):
                if item.name in ["__init__.py", "_version.py", "version.py"]:
                    try:
                        content = item.read_text(encoding='utf-8', errors='ignore')
                        match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
                        if match:
                            return match.group(1)
                    except:
                        pass
        except Exception:
            pass
            
        return None
    
    def download_app(self, app_id: str, version: Optional[str] = None) -> bool:
        """
        Download and extract application from GitHub.
        
        Args:
            app_id: Application identifier
            version: Specific version/tag to download, or None for latest
            
        Returns:
            True if successful
        """
        app = self.apps.get(app_id)
        if not app:
            self._report_status(app_id, f"Unknown application: {app_id}")
            self._report_download_progress(app_id, "error", f"Unknown application: {app_id}")
            return False
        
        self._report_status(app_id, f"Downloading {app.name}...")
        self._report_download_progress(app_id, "downloading", f"Starting download of {app.name}...", 0, 0)
        
        # Create apps directory
        self.apps_path.mkdir(parents=True, exist_ok=True)
        app_path = self.apps_path / app_id
        
        # Determine download URL
        if version:
            # Specific version/tag - normalize version format
            # GitHub tags can be with or without 'v' prefix
            zip_url = f"https://github.com/{app.repo_owner}/{app.repo_name}/archive/refs/tags/{version}.zip"
        else:
            # Latest from main branch
            zip_url = f"https://github.com/{app.repo_owner}/{app.repo_name}/archive/refs/heads/main.zip"
        
        try:
            # Download zip file with progress
            self._report_status(app_id, f"Downloading from GitHub...")
            
            # Try the URL, if 404 try with/without 'v' prefix
            request = Request(zip_url, headers={"User-Agent": "PyPottery-Launcher"})
            
            temp_zip = self.base_path / f"temp_{app_id}.zip"
            response = None
            
            try:
                response = urlopen(request, timeout=120)
            except URLError as e:
                if hasattr(e, 'code') and e.code == 404 and version:
                    # Try alternate version format
                    if version.startswith('v'):
                        alt_version = version[1:]  # Remove 'v'
                    else:
                        alt_version = f"v{version}"  # Add 'v'
                    
                    alt_url = f"https://github.com/{app.repo_owner}/{app.repo_name}/archive/refs/tags/{alt_version}.zip"
                    self._report_status(app_id, f"Trying alternate tag format...")
                    alt_request = Request(alt_url, headers={"User-Agent": "PyPottery-Launcher"})
                    
                    try:
                        response = urlopen(alt_request, timeout=120)
                        version = alt_version  # Update version for saving
                    except URLError:
                        # If both fail, try main branch as fallback
                        self._report_status(app_id, f"Tag not found, downloading main branch...")
                        main_url = f"https://github.com/{app.repo_owner}/{app.repo_name}/archive/refs/heads/main.zip"
                        main_request = Request(main_url, headers={"User-Agent": "PyPottery-Launcher"})
                        response = urlopen(main_request, timeout=120)
                        version = "main"
                else:
                    raise
            
            # Get total size if available
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192  # 8KB chunks
            
            with open(temp_zip, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Report progress
                    if total_size > 0:
                        self._report_download_progress(
                            app_id, "downloading",
                            f"Downloading... {downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB",
                            downloaded, total_size
                        )
                    else:
                        self._report_download_progress(
                            app_id, "downloading",
                            f"Downloading... {downloaded / 1024 / 1024:.1f} MB",
                            downloaded, downloaded  # Unknown total
                        )
            
            response.close()
            
            # Remove existing installation
            if app_path.exists():
                self._report_status(app_id, "Removing old version...")
                self._report_download_progress(app_id, "extracting", "Removing old version...", 0, 0)
                shutil.rmtree(app_path)
            
            # Extract zip
            self._report_status(app_id, "Extracting files...")
            self._report_download_progress(app_id, "extracting", "Extracting files...", 0, 0)
            
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                # Get the root folder name in the zip
                root_folder = zip_ref.namelist()[0].split('/')[0]
                file_list = zip_ref.namelist()
                total_files = len(file_list)
                
                for idx, file in enumerate(file_list):
                    zip_ref.extract(file, self.apps_path)
                    if idx % 10 == 0:  # Update every 10 files
                        self._report_download_progress(
                            app_id, "extracting",
                            f"Extracting files... {idx + 1}/{total_files}",
                            idx + 1, total_files
                        )
            
            # Rename extracted folder to standard name
            extracted_path = self.apps_path / root_folder
            if extracted_path.exists():
                extracted_path.rename(app_path)
            
            # Cleanup
            temp_zip.unlink()
            
            # Detect real version if we just downloaded "main"
            # This prevents stuck "Update Available" messages
            detected_version = self._detect_version(app_path)
            
            # If we found a real version in the files, prefer it over "main"
            final_version = version
            if (not version or version in ["main", "master"]) and detected_version:
                final_version = detected_version
            elif not final_version:
                final_version = "main"
            
            # Save version info
            version_file = app_path / ".version"
            version_file.write_text(final_version)
            
            # Update app status
            app.installed = True
            app.installed_version = final_version
            app.update_available = False
            
            self._report_status(app_id, f"{app.name} installed successfully!")
            self._report_download_progress(app_id, "complete", f"{app.name} installed successfully!", 100, 100)
            return True
            
        except URLError as e:
            self._report_status(app_id, f"Download failed: {e}")
            self._report_download_progress(app_id, "error", f"Download failed: {e}", 0, 0)
            return False
        except Exception as e:
            self._report_status(app_id, f"Installation failed: {e}")
            self._report_download_progress(app_id, "error", f"Installation failed: {e}", 0, 0)
            return False
    
    def uninstall_app(self, app_id: str) -> bool:
        """
        Remove an installed application.
        
        Args:
            app_id: Application identifier
            
        Returns:
            True if successful
        """
        app = self.apps.get(app_id)
        if not app:
            return False
        
        # Stop if running
        if app_id in self._processes:
            self.stop_app(app_id)
        
        app_path = self.apps_path / app_id
        if app_path.exists():
            shutil.rmtree(app_path)
        
        app.installed = False
        app.installed_version = None
        
        self._report_status(app_id, f"{app.name} uninstalled")
        return True
    
    def launch_app(self, app_id: str, open_browser: bool = True) -> bool:
        """
        Launch an application.
        
        Args:
            app_id: Application identifier
            open_browser: Whether to open browser after launch
            
        Returns:
            True if launched successfully
        """
        app = self.apps.get(app_id)
        if not app:
            self._report_status(app_id, f"Unknown application: {app_id}")
            return False
        
        if not app.installed:
            self._report_status(app_id, f"{app.name} is not installed")
            return False
        
        # Check if already running
        if app_id in self._processes:
            proc = self._processes[app_id]
            if proc.poll() is None:
                self._report_status(app_id, f"{app.name} is already running")
                if open_browser:
                    webbrowser.open(f"http://localhost:{app.port}")
                return True
        
        # Check port
        if self.is_port_in_use(app.port):
            self._report_status(app_id, f"Port {app.port} is already in use")
            return False
        
        app_path = self.apps_path / app_id
        script_path = app_path / app.entry_script
        
        if not script_path.exists():
            self._report_status(app_id, f"Entry script not found: {script_path}")
            return False
        
        self._report_status(app_id, f"Starting {app.name}...")
        
        # Set environment
        env = os.environ.copy()
        env["PYPOTTERY_LAUNCHED_FROM_WRAPPER"] = "1"
        # Fix encoding issues on Windows with emoji in print statements
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        # Launch process
        try:
            if self.is_windows:
                # Windows: use CREATE_NEW_CONSOLE for separate window
                # Don't pipe stdout/stderr when using CREATE_NEW_CONSOLE - the console handles I/O
                # This prevents buffer blocking during long operations like model downloads
                process = subprocess.Popen(
                    [str(self.python_executable), str(script_path)],
                    cwd=str(app_path),
                    env=env,
                    stdout=None,  # Let the console window handle output
                    stderr=None,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Unix: detach from terminal
                # Don't pipe stdout/stderr - prevents buffer blocking during long operations
                # Use DEVNULL or let the terminal handle output naturally
                process = subprocess.Popen(
                    [str(self.python_executable), str(script_path)],
                    cwd=str(app_path),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            self._processes[app_id] = process
            app.is_running = True
            app.process = process
            
            # NOTE: Don't open browser here - Flask apps open it themselves
            # The Flask apps already have browser opening logic built-in
            
            self._report_status(app_id, f"{app.name} started on port {app.port}")
            return True
            
        except Exception as e:
            self._report_status(app_id, f"Failed to start {app.name}: {e}")
            return False
    
    def stop_app(self, app_id: str) -> bool:
        """
        Stop a running application.
        
        Args:
            app_id: Application identifier
            
        Returns:
            True if stopped successfully
        """
        app = self.apps.get(app_id)
        if not app:
            return False
        
        if app_id not in self._processes:
            self._report_status(app_id, f"{app.name} is not running")
            return False
        
        process = self._processes[app_id]
        
        try:
            # Try graceful termination first
            process.terminate()
            
            # Wait up to 5 seconds
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill
                process.kill()
                process.wait(timeout=2)
            
            del self._processes[app_id]
            app.is_running = False
            app.process = None
            
            self._report_status(app_id, f"{app.name} stopped")
            return True
            
        except Exception as e:
            self._report_status(app_id, f"Failed to stop {app.name}: {e}")
            return False
    
    def get_app_status(self, app_id: str) -> AppStatus:
        """Get current status of an application"""
        app = self.apps.get(app_id)
        if not app:
            return AppStatus(app_id=app_id, is_running=False, port=0)
        
        is_running = False
        pid = None
        
        if app_id in self._processes:
            proc = self._processes[app_id]
            if proc.poll() is None:
                is_running = True
                pid = proc.pid
            else:
                # Process ended, clean up
                del self._processes[app_id]
                app.is_running = False
        
        return AppStatus(
            app_id=app_id,
            is_running=is_running,
            port=app.port,
            pid=pid,
            url=f"http://localhost:{app.port}" if is_running else None
        )
    
    def stop_all_apps(self):
        """Stop all running applications"""
        for app_id in list(self._processes.keys()):
            self.stop_app(app_id)
    
    def get_running_apps(self) -> List[str]:
        """Get list of currently running application IDs"""
        running = []
        for app_id in list(self._processes.keys()):
            if self._processes[app_id].poll() is None:
                running.append(app_id)
            else:
                # Clean up finished process
                del self._processes[app_id]
                if app_id in self.apps:
                    self.apps[app_id].is_running = False
        return running
    
    def open_app_folder(self, app_id: str) -> bool:
        """Open application folder in file explorer"""
        app = self.apps.get(app_id)
        if not app or not app.installed:
            return False
        
        app_path = self.apps_path / app_id
        
        try:
            if self.is_windows:
                os.startfile(str(app_path))
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(app_path)])
            else:
                subprocess.run(["xdg-open", str(app_path)])
            return True
        except Exception:
            return False


if __name__ == "__main__":
    # Test app manager
    import sys
    
    base_path = Path(__file__).parent.parent
    
    # Use system Python for testing
    python_exe = Path(sys.executable)
    
    manager = AppManager(base_path, python_exe)
    
    def status_callback(app_id: str, message: str):
        print(f"[{app_id}] {message}")
    
    manager.set_status_callback(status_callback)
    
    print("Available applications:")
    for app in manager.get_app_list():
        status = "✓ Installed" if app.installed else "Not installed"
        print(f"  {app.icon} {app.name}: {status}")
