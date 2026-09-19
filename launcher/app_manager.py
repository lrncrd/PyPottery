"""
Application Manager for PyPottery Suite
Handles downloading, launching, and managing PyPottery applications
"""

import logging
import os
import signal
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

from .error_messages import classify
from .logging_setup import app_log_dir, guarded
from .process_utils import (
    find_available_port_for_app,
    find_port_owner,
    no_window_kwargs,
    open_path,
)

logger = logging.getLogger("launcher.apps")

# Downloads are unpacked here and only swapped into place once they're known
# to be complete, so a failure can never destroy a working installation.
STAGING_DIRNAME = ".staging"


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
    default_port: int = 5000
    logo_path: Optional[str] = None
    installed: bool = False
    installed_version: Optional[str] = None
    latest_version: Optional[str] = None
    update_available: bool = False
    is_running: bool = False
    is_starting: bool = False
    last_error: Optional[str] = None
    process: Optional[subprocess.Popen] = None


@dataclass 
class AppStatus:
    """Status of a running application"""
    app_id: str
    is_running: bool
    port: int
    pid: Optional[int] = None
    url: Optional[str] = None
    is_starting: bool = False


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
    
    def __init__(self, base_path: Path, python_executable: Path, developer_mode: bool = False):
        self.base_path = Path(base_path)
        self.apps_path = self.base_path / "apps"
        self.python_executable = Path(python_executable)
        self.is_windows = platform.system() == "Windows"
        # Developer mode: sub-apps run from their own git checkout at the repo
        # root (sibling of apps/) instead of a downloaded copy under apps/, so
        # local edits can be tested without pushing/re-downloading a release.
        self.developer_mode = developer_mode

        # Offline Web Assets Manager
        from .vendor_assets_manager import VendorAssetsManager
        self.vendor_assets_manager = VendorAssetsManager(self.base_path)

        def _prepare_vendor_assets():
            self.vendor_assets_manager.ensure_vendor_assets()
            # sync_to_app() normally populates a sub-app's static/vendor when
            # it's launched - the launcher's own UI needs the same treatment,
            # since nothing else ever populates launcher/static/vendor.
            self.vendor_assets_manager.sync_to_app(Path(__file__).parent)

        threading.Thread(
            target=guarded(_prepare_vendor_assets, "vendor_assets"), daemon=True
        ).start()

        # Load app configurations
        self.apps: Dict[str, AppInfo] = {}
        self._load_app_configs()

        # Running processes
        self._processes: Dict[str, subprocess.Popen] = {}
        # Open log files for those processes, closed when they stop.
        self._log_files: Dict[str, object] = {}

        self._cleanup_stale_downloads()


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
                port_val = app_config.get("port", 5000)
                self.apps[app_id] = AppInfo(
                    id=app_id,
                    name=app_config.get("name", app_id),
                    description=app_config.get("description", ""),
                    repo_owner=app_config.get("repo_owner", "lrncrd"),
                    repo_name=app_config.get("repo_name", app_id),
                    entry_script=app_config.get("entry_script", "app.py"),
                    port=port_val,
                    default_port=port_val,
                    min_ram_gb=app_config.get("min_ram_gb", 4),
                    recommended_ram_gb=app_config.get("recommended_ram_gb", 8),
                    requires_gpu=app_config.get("requires_gpu", False),
                    icon=app_config.get("icon", "📦"),
                    logo_path=app_config.get("logo", None)
                )
        
        # Check installed status
        self._refresh_installed_status()

    def _app_path(self, app_id: str) -> Path:
        """Resolve where an app's files live: its git checkout at the repo
        root in developer mode, or the downloaded copy under apps/ otherwise."""
        if self.developer_mode:
            return self.base_path / app_id
        return self.apps_path / app_id

    def refresh_installed_status(self):
        """Public re-scan of installed/version state. In developer mode this
        is the only way to pick up a `git pull`'d VERSION bump without
        restarting the launcher process (the initial scan only runs once, at
        AppManager construction time)."""
        self._refresh_installed_status()

    def _refresh_installed_status(self):
        """Check which apps are installed"""
        for app_id, app in self.apps.items():
            app_path = self._app_path(app_id)
            app.installed = app_path.exists() and (app_path / app.entry_script).exists()

            if self.developer_mode:
                # Dev checkouts carry a real VERSION file, not the launcher's
                # download marker - reuse the same detector as _detect_version.
                app.installed_version = self._detect_version(app_path)
            else:
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
        # 1. Try VERSION - the file each app's auto-release workflow bumps on
        # every release. `version.txt` used to be checked here too, but it's
        # a legacy file the automation never touches, so it silently drifts
        # out of sync and made the launcher display a stale version.
        vf = app_path / "VERSION"
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

        if self.developer_mode:
            message = f"Developer mode: {app.name} runs from its local git checkout - install/update disabled"
            self._report_status(app_id, message)
            self._report_download_progress(app_id, "error", message)
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
            
            staging_root = self.apps_path / STAGING_DIRNAME
            staging_root.mkdir(parents=True, exist_ok=True)
            stage_dir = staging_root / f"{app_id}-{os.getpid()}-{int(time.time())}"
            stage_dir.mkdir(parents=True, exist_ok=True)
            temp_zip = stage_dir / "download.zip"
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
            chunk_size = 65536  # 64KB chunks
            last_report_time = 0
            last_reported_mb = -1.0

            with open(temp_zip, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    current_time = time.time()
                    current_mb = round(downloaded / 1024 / 1024, 1)

                    if (current_time - last_report_time >= 0.12) or (current_mb != last_reported_mb):
                        last_report_time = current_time
                        last_reported_mb = current_mb
                        if total_size > 0:
                            self._report_download_progress(
                                app_id, "downloading",
                                f"Downloading... {current_mb:.1f} MB / {total_size / 1024 / 1024:.1f} MB",
                                downloaded, total_size
                            )
                        else:
                            self._report_download_progress(
                                app_id, "downloading",
                                f"Downloading... {current_mb:.1f} MB",
                                downloaded, downloaded
                            )
            
            response.close()

            # A stream cut short (dropped Wi-Fi, a proxy giving up) yields a
            # file that unzips to garbage or half an app. Catch it here, while
            # the working installation is still untouched.
            if total_size > 0 and downloaded != total_size:
                raise IOError(
                    f"Truncated download: got {downloaded} of {total_size} bytes"
                )

            self._report_download_progress(app_id, "extracting", "Download complete. Preparing extraction...", 0, 100)

            # Extract into staging - the existing install stays exactly where
            # it is until the new one is complete and verified.
            self._report_status(app_id, "Extracting files...")
            self._report_download_progress(app_id, "extracting", "Extracting files...", 0, 100)

            extract_root = stage_dir / "extract"
            extract_root.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                if not file_list:
                    raise zipfile.BadZipFile("The downloaded archive is empty")
                root_folder = file_list[0].split('/')[0]
                total_files = len(file_list)

                for idx, file in enumerate(file_list):
                    zip_ref.extract(file, extract_root)
                    if idx % 10 == 0:  # Update every 10 files
                        self._report_download_progress(
                            app_id, "extracting",
                            f"Extracting files... {idx + 1}/{total_files}",
                            idx + 1, total_files
                        )

            extracted_path = extract_root / root_folder
            if not extracted_path.is_dir():
                raise IOError("The downloaded archive did not contain the expected folder")

            # Does this actually look like the app? Better to find out now than
            # to leave the user with a folder that can't start.
            if not (extracted_path / app.entry_script).exists():
                raise IOError(
                    f"The download is missing {app.entry_script} - it may be an "
                    "incomplete release"
                )

            # Detect real version if we just downloaded "main"
            # This prevents stuck "Update Available" messages
            detected_version = self._detect_version(extracted_path)

            # If we found a real version in the files, prefer it over "main"
            final_version = version
            if (not version or version in ["main", "master"]) and detected_version:
                final_version = detected_version
            elif not final_version:
                final_version = "main"

            # Strip a leading 'v'/'V' - GitHub tag names carry one (e.g. "v3.0.1")
            # but the UI already prepends "v" when displaying installed_version,
            # so keeping it here would render as "vv3.0.1".
            if final_version not in ("main", "master") and final_version.lower().startswith("v") and final_version[1:2].isdigit():
                final_version = final_version[1:]

            (extracted_path / ".version").write_text(final_version)

            # An update of a running app would fight the running process for
            # its own files (guaranteed to fail on Windows).
            if app_id in self._processes:
                self._report_status(app_id, f"Stopping {app.name} to update it...")
                self.stop_app(app_id)

            self._report_download_progress(app_id, "extracting", "Installing...", 95, 100)
            self._swap_into_place(app_id, extracted_path, app_path)

            # Update app status
            app.installed = True
            app.installed_version = final_version
            app.update_available = False

            self._report_status(app_id, f"{app.name} installed successfully!")
            self._report_download_progress(app_id, "complete", f"{app.name} installed successfully!", 100, 100)
            return True

        except Exception as e:
            logger.exception("Installing %s failed", app_id)
            message = classify(e).message
            # The previous installation is still on disk and still valid -
            # re-read the truth from there so the UI can't offer to launch
            # something that isn't there.
            self._refresh_single_app(app_id)
            self._report_status(app_id, f"Installation failed. {message}")
            self._report_download_progress(app_id, "error", f"Installation failed. {message}", 0, 0)
            return False
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)

    def _swap_into_place(self, app_id: str, staged: Path, app_path: Path):
        """
        Replace an installation with a freshly staged one, keeping the old copy
        until the new one is in place so a failure can be rolled back.
        """
        backup = None
        if app_path.exists():
            backup = app_path.with_name(f"{app_path.name}.old-{int(time.time())}")
            self._rename_with_retry(app_path, backup)

        try:
            self._rename_with_retry(staged, app_path)
        except OSError:
            if backup is not None and not app_path.exists():
                # Put the working version back rather than leaving nothing.
                logger.warning("Install swap failed for %s - restoring the previous version", app_id)
                self._rename_with_retry(backup, app_path)
            raise

        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)

    @staticmethod
    def _rename_with_retry(source: Path, target: Path, attempts: int = 3):
        """
        Directory renames lose races with antivirus scanners and file indexers
        on Windows, and those are transient - retry before giving up, then fall
        back to a copy.
        """
        last_error = None
        for attempt in range(attempts):
            try:
                source.rename(target)
                return
            except OSError as e:
                last_error = e
                time.sleep(0.5 * (attempt + 1))
        try:
            shutil.copytree(source, target)
            shutil.rmtree(source, ignore_errors=True)
            return
        except OSError:
            raise last_error if last_error else OSError(f"Could not move {source} to {target}")

    def _refresh_single_app(self, app_id: str):
        """Re-read one app's installed state from disk."""
        app = self.apps.get(app_id)
        if not app:
            return
        app_path = self._app_path(app_id)
        app.installed = (app_path / app.entry_script).exists()
        if not app.installed:
            app.installed_version = None
            return
        version_file = app_path / ".version"
        app.installed_version = (
            version_file.read_text(encoding="utf-8").strip()
            if version_file.exists()
            else self._detect_version(app_path)
        )

    def _cleanup_stale_downloads(self):
        """Clear staging dirs and old temp zips left by an interrupted install."""
        try:
            staging_root = self.apps_path / STAGING_DIRNAME
            if staging_root.exists():
                shutil.rmtree(staging_root, ignore_errors=True)
            for leftover in self.apps_path.glob("*.old-*"):
                shutil.rmtree(leftover, ignore_errors=True)
            for leftover in self.base_path.glob("temp_*.zip"):
                leftover.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not clean up leftover download files")


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

        if self.developer_mode:
            self._report_status(app_id, f"Developer mode: {app.name} runs from its local git checkout - uninstall disabled")
            return False

        # Stop if running
        if app_id in self._processes:
            self.stop_app(app_id)

        app_path = self._app_path(app_id)
        try:
            if app_path.exists():
                shutil.rmtree(app_path)
        except OSError as e:
            logger.exception("Could not remove %s", app_id)
            self._report_status(app_id, f"Could not uninstall {app.name}. {classify(e).message}")
            return False

        app.installed = False
        app.installed_version = None
        app.update_available = False

        self._report_status(app_id, f"{app.name} uninstalled")
        return True
    
    def _is_our_app_running(self, app: AppInfo, port: int) -> bool:
        """Check if an active listener on port belongs to this application."""
        if app.id in self._processes:
            proc = self._processes[app.id]
            if proc.poll() is None:
                return True
        # Check HTTP health/probe endpoint
        try:
            req = Request(f"http://127.0.0.1:{port}/health", headers={"User-Agent": "PyPotteryLauncher"})
            with urlopen(req, timeout=0.8) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        # Check root page
        try:
            req = Request(f"http://127.0.0.1:{port}/", headers={"User-Agent": "PyPotteryLauncher"})
            with urlopen(req, timeout=0.8) as resp:
                data = resp.read(4096).decode("utf-8", errors="ignore")
                if app.id.lower() in data.lower() or "pypottery" in data.lower():
                    return True
        except Exception:
            pass
        return False

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
        
        app.last_error = None

        if not app.installed:
            app.last_error = f"{app.name} is not installed"
            self._report_status(app_id, app.last_error)
            return False
        
        # Check if already running on its current or default port
        active_port = app.port or app.default_port
        if self.is_port_in_use(active_port) and self._is_our_app_running(app, active_port):
            app.is_running = True
            app.is_starting = False
            self._report_status(app_id, f"{app.name} is already running on port {active_port}")
            if open_browser:
                webbrowser.open(f"http://localhost:{active_port}")
            return True

        # Mark application as starting
        app.is_starting = True
        app.is_running = False

        # Determine target port:
        # If default port is available, use it.
        # If default port is in use by another process, allocate an alternative port.
        target_port = app.default_port
        if self.is_port_in_use(target_port):
            owner = find_port_owner(target_port)
            try:
                target_port = find_available_port_for_app(app.default_port)
                logger.info(
                    "Default port %s busy (%s). Starting %s on alternative port %s",
                    app.default_port, owner or "another process", app.name, target_port
                )
                self._report_status(
                    app_id,
                    f"Port {app.default_port} in use ({owner or 'occupied'}). Starting on port {target_port}..."
                )
            except Exception as e:
                msg = f"Port {app.default_port} is in use and no alternative port was found: {e}"
                app.is_starting = False
                app.last_error = msg
                self._report_status(app_id, msg)
                return False

        app.port = target_port

        app_path = self._app_path(app_id)
        script_path = app_path / app.entry_script

        self._report_status(app_id, f"Syncing offline web assets for {app.name}...")
        self.vendor_assets_manager.sync_to_app(app_path)

        self._report_status(app_id, f"Starting {app.name} on port {target_port}...")
        
        # Set environment
        env = os.environ.copy()
        env["PYPOTTERY_LAUNCHED_FROM_WRAPPER"] = "1"
        # Shared model cache dir - apps that respect this (PyPotteryInk, PyPotteryLens)
        # download AI models here instead of into their own folder, so a model already
        # fetched by one app isn't downloaded again by another. Apps run standalone
        # (this var unset) keep caching locally, unchanged.
        env["PYPOTTERY_MODEL_CACHE"] = str(self.base_path / "model_cache")
        env["PORT"] = str(target_port)
        env["PYPOTTERY_PORT"] = str(target_port)
        env["FLASK_RUN_PORT"] = str(target_port)
        # Fix encoding issues on Windows with emoji in print statements
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        # Unbuffered, so a crash's last words actually reach the log file
        # instead of dying in a 4 KB buffer.
        env["PYTHONUNBUFFERED"] = "1"

        # Launch process
        try:
            log_file = self._open_app_log(app_id)

            if self.developer_mode and self.is_windows:
                # A visible console is useful when you're editing the app;
                # for everyone else the output goes to the log file instead.
                process = subprocess.Popen(
                    [str(self.python_executable), str(script_path)],
                    cwd=str(app_path),
                    env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            elif self.is_windows:
                process = subprocess.Popen(
                    [str(self.python_executable), str(script_path)],
                    cwd=str(app_path),
                    env=env,
                    stdout=log_file or subprocess.DEVNULL,
                    stderr=subprocess.STDOUT if log_file else subprocess.DEVNULL,
                    **no_window_kwargs(),
                )
            else:
                process = subprocess.Popen(
                    [str(self.python_executable), str(script_path)],
                    cwd=str(app_path),
                    env=env,
                    stdout=log_file or subprocess.DEVNULL,
                    stderr=subprocess.STDOUT if log_file else subprocess.DEVNULL,
                    start_new_session=True,
                )

            self._processes[app_id] = process
            if log_file:
                self._log_files[app_id] = log_file

            app.is_running = True
            app.is_starting = True
            app.process = process

            threading.Thread(
                target=self._watch_app_startup,
                args=(app_id, process),
                daemon=True,
            ).start()

            self._report_status(app_id, f"Starting {app.name}...")
            return True

        except Exception as e:
            logger.exception("Failed to start %s", app_id)
            self._close_app_log(app_id)
            app.is_starting = False
            msg = f"Failed to start {app.name}. {classify(e).message}"
            app.last_error = msg
            self._report_status(app_id, msg)
            return False

    def _watch_app_startup(self, app_id: str, process: subprocess.Popen):
        """
        Poll app until its port is in use and accepting connections,
        then mark is_starting = False and emit updated status.
        """
        app = self.apps.get(app_id)
        if not app:
            return
        port = app.port
        start_time = time.time()
        # Wait up to 120 seconds for port to open
        while time.time() - start_time < 120:
            if process.poll() is not None:
                # App process terminated unexpectedly before port opened
                app.is_running = False
                app.is_starting = False
                self._close_app_log(app_id)
                msg = f"{app.name} process exited before becoming ready. Check logs/apps/{app_id}.log"
                app.last_error = msg
                self._report_status(app_id, msg)
                return
            if self.is_port_in_use(port):
                app.is_starting = False
                self._report_status(app_id, f"{app.name} is ready on port {port}")
                return
            time.sleep(0.4)
        if app_id in self.apps:
            self.apps[app_id].is_starting = False

    def _open_app_log(self, app_id: str):
        """
        Per-app log file. Without it a sub-app that dies on startup leaves no
        trace at all: the launcher only reports "<app> has stopped".
        """
        directory = app_log_dir()
        if directory is None:
            return None
        try:
            path = directory / f"{app_id}.log"
            if path.exists() and path.stat().st_size > 0:
                previous = directory / f"{app_id}.log.1"
                previous.unlink(missing_ok=True)
                path.rename(previous)
            handle = open(path, "ab")
            handle.write(
                f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} launching {app_id} ===\n".encode()
            )
            handle.flush()
            return handle
        except OSError:
            logger.exception("Could not open a log file for %s", app_id)
            return None

    def _close_app_log(self, app_id: str):
        handle = self._log_files.pop(app_id, None)
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
    
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
            self._terminate_tree(process)

            del self._processes[app_id]
            self._close_app_log(app_id)
            app.is_running = False
            app.is_starting = False
            app.last_error = None
            app.port = app.default_port
            app.process = None

            self._report_status(app_id, f"{app.name} stopped")
            return True

        except Exception as e:
            logger.exception("Failed to stop %s", app_id)
            msg = f"Failed to stop {app.name}: {e}"
            app.last_error = msg
            self._report_status(app_id, msg)
            return False

    def _terminate_tree(self, process: subprocess.Popen):
        """
        Stop a sub-app and everything it spawned.

        terminate() alone only reaches the process we started; PyTorch
        dataloaders and multiprocessing pools leave children behind that keep
        holding the app's port and GPU memory.
        """
        try:
            import psutil
        except ImportError:
            psutil = None

        if psutil is not None:
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except psutil.Error:
                        pass
                parent.terminate()
                _, alive = psutil.wait_procs([parent] + children, timeout=5)
                for survivor in alive:
                    try:
                        survivor.kill()
                    except psutil.Error:
                        pass
                process.poll()
                return
            except psutil.NoSuchProcess:
                process.poll()
                return
            except psutil.Error:
                logger.exception("psutil could not stop the process tree - falling back")

        # No psutil (it's a soft dependency): use whatever the OS gives us.
        if self.is_windows:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True, timeout=30, **no_window_kwargs(),
            )
        else:
            try:
                # start_new_session=True at launch made the app its own process
                # group leader, so this reaches its children too.
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    
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
                self._close_app_log(app_id)
                app.is_running = False
        
        return AppStatus(
            app_id=app_id,
            is_running=is_running,
            port=app.port,
            pid=pid,
            url=f"http://localhost:{app.port}" if is_running else None,
            is_starting=app.is_starting if is_running else False,
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
                self._close_app_log(app_id)
                if app_id in self.apps:
                    self.apps[app_id].is_running = False
        return running
    
    def open_app_folder(self, app_id: str) -> bool:
        """Open application folder in file explorer"""
        app = self.apps.get(app_id)
        if not app or not app.installed:
            return False

        return open_path(self._app_path(app_id))


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
