"""
Launcher Updater Module
Handles self-updating of the PyPottery Launcher
"""

import os
import sys
import time
import shutil
import zipfile
import tempfile
import platform
import subprocess
from pathlib import Path
from dataclasses import dataclass
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Optional, Callable, Set


@dataclass
class LauncherProgress:
    """Progress information for launcher update callbacks"""
    stage: str  # "downloading", "extracting", "installing", "restarting", "complete", "error"
    message: str
    bytes_downloaded: int = 0
    bytes_total: int = 0
    percent: float = 0.0
    error: bool = False


# Directories and files that must NEVER be overwritten or removed during a launcher update
PRESERVED_PATHS: Set[str] = {
    "apps",
    "model_cache",
    ".venv",
    "env",
    "venv",
    ".git",
    ".gitignore",
    ".DS_Store",
    "dev_config.py",
    ".pypottery",
    "usability_test.zip",
    "__pycache__",
}


class LauncherUpdater:
    """
    Manages self-updating for the PyPottery Launcher suite.
    Downloads release packages, safely extracts and updates files while preserving
    user data and virtual environments, and triggers clean application restart.
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path).resolve()
        self.launcher_path = self.base_path / "launcher"

    def update(
        self,
        version: str,
        repo_owner: str = "lrncrd",
        repo_name: str = "PyPottery",
        progress_callback: Optional[Callable[[LauncherProgress], None]] = None,
    ) -> bool:
        """
        Update the launcher from a GitHub release tag or archive.

        Args:
            version: Target version or tag (e.g., "1.2.0" or "v1.2.0" or "main")
            repo_owner: GitHub repository owner (default "lrncrd")
            repo_name: GitHub repository name (default "PyPottery")
            progress_callback: Callback(LauncherProgress)

        Returns:
            True if successful
        """
        def report(stage: str, msg: str, downloaded: int = 0, total: int = 0, pct: float = 0.0, is_err: bool = False):
            if progress_callback:
                progress_callback(LauncherProgress(
                    stage=stage,
                    message=msg,
                    bytes_downloaded=downloaded,
                    bytes_total=total,
                    percent=pct,
                    error=is_err,
                ))

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / "launcher_update.zip"

                # 1. Determine download URLs with fallback
                if version in ("main", "master"):
                    urls_to_try = [
                        f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/{version}.zip"
                    ]
                else:
                    clean_v = version.lstrip("v")
                    tag_with_v = f"v{clean_v}"
                    urls_to_try = [
                        f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_with_v}.zip",
                        f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{clean_v}.zip",
                        f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/main.zip",
                    ]

                response = None
                successful_url = None
                for url in urls_to_try:
                    report("downloading", "Connecting to GitHub...", 0, 0, 0.0)
                    req = Request(url, headers={"User-Agent": "PyPottery-Launcher"})
                    try:
                        resp = urlopen(req, timeout=120)
                        if resp.status == 200:
                            response = resp
                            successful_url = url
                            break
                    except URLError:
                        continue

                if not response:
                    report("error", f"Could not find update package for version {version}", 0, 0, 0.0, is_err=True)
                    return False

                # 2. Download file with chunked streaming and rich progress
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536  # 64KB
                last_report_time = 0.0

                with open(zip_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        curr_time = time.time()
                        if curr_time - last_report_time >= 0.1:
                            last_report_time = curr_time
                            curr_mb = downloaded / (1024 * 1024)
                            if total_size > 0:
                                total_mb = total_size / (1024 * 1024)
                                pct = min(50.0, (downloaded / total_size) * 50.0)
                                report(
                                    "downloading",
                                    f"Downloading update... {curr_mb:.1f} MB / {total_mb:.1f} MB",
                                    downloaded, total_size, pct
                                )
                            else:
                                report(
                                    "downloading",
                                    f"Downloading update... {curr_mb:.1f} MB",
                                    downloaded, downloaded, 25.0
                                )

                response.close()
                report("extracting", "Download complete. Extracting update package...", 0, 100, 55.0)

                # 3. Extract to temp directory
                extract_path = temp_path / "extracted"
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    namelist = zip_ref.namelist()
                    total_files = len(namelist)
                    for idx, file_item in enumerate(namelist):
                        zip_ref.extract(file_item, extract_path)
                        if idx % 10 == 0 or idx == total_files - 1:
                            pct = 55.0 + ((idx + 1) / total_files) * 25.0  # 55% -> 80%
                            report(
                                "extracting",
                                f"Extracting files... {idx + 1}/{total_files}",
                                idx + 1, total_files, pct
                            )

                # 4. Find root of extracted package
                source_root = None
                for root, dirs, files in os.walk(extract_path):
                    if "launcher" in dirs:
                        candidate = Path(root)
                        if (candidate / "launcher" / "gui.py").exists():
                            source_root = candidate
                            break

                if not source_root:
                    report("error", "Invalid update package: launcher structure not found", 0, 0, 0.0, is_err=True)
                    return False

                # 5. Install updates selectively
                report("installing", "Installing launcher updates...", 0, 100, 85.0)
                self._copy_selective(source_root, self.base_path)

                # Set executable permissions on scripts on macOS/Linux
                if platform.system() != "Windows":
                    for script_name in ["launch_pypottery.sh", "launch_pypottery.command"]:
                        script_file = self.base_path / script_name
                        if script_file.exists():
                            try:
                                script_file.chmod(0o755)
                            except OSError:
                                pass

                report("complete", "Launcher update installed successfully!", 100, 100, 100.0)
                return True

        except Exception as e:
            report("error", f"Update failed: {e}", 0, 0, 0.0, is_err=True)
            return False

    def _copy_selective(self, src_root: Path, dest_root: Path):
        """
        Copy new files into base_path, skipping blacklisted paths (user data, models, venvs).
        """
        for item in src_root.iterdir():
            name = item.name
            if name in PRESERVED_PATHS or name.startswith("temp_") or name.startswith("."):
                continue

            dest_item = dest_root / name

            if item.is_dir():
                # Recursive selective copy for directories (launcher, imgs, PyPotteryDocs, etc.)
                self._copy_tree_selective(item, dest_item)
            else:
                # Overwrite root level files (install.py, launch_pypottery.sh, requirements.txt, etc.)
                shutil.copy2(item, dest_item)

    def _copy_tree_selective(self, src: Path, dst: Path):
        """Recursively copy directory tree, overwriting files while respecting exclusions"""
        if not dst.exists():
            dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            if item.name in PRESERVED_PATHS or item.name.startswith("temp_") or item.name == "__pycache__":
                continue

            dst_item = dst / item.name
            if item.is_dir():
                self._copy_tree_selective(item, dst_item)
            else:
                shutil.copy2(item, dst_item)

    def spawn_new_instance(self, python_executable: Optional[Path] = None) -> bool:
        """
        Spawn a new launcher process detached from the current process.
        """
        python_exe = python_executable or Path(sys.executable)
        gui_script = self.base_path / "launcher" / "gui.py"
        if not gui_script.exists():
            return False

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            if platform.system() == "Windows":
                pythonw = python_exe.parent / "pythonw.exe"
                target_python = pythonw if pythonw.exists() else python_exe
                flags = 0 if pythonw.exists() else subprocess.CREATE_NEW_CONSOLE
                subprocess.Popen(
                    [str(target_python), str(gui_script)],
                    cwd=str(self.base_path),
                    env=env,
                    creationflags=flags
                )
            else:
                subprocess.Popen(
                    [str(python_exe), str(gui_script)],
                    cwd=str(self.base_path),
                    env=env,
                    start_new_session=True
                )
            return True
        except Exception as e:
            print(f"Failed to spawn new launcher instance: {e}")
            return False

    def restart(self, python_executable: Optional[Path] = None):
        """Legacy restart method - fallback if spawn is not used"""
        self.spawn_new_instance(python_executable)
        sys.exit(0)
