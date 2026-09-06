"""
Environment Manager for PyPottery Suite
Handles virtual environment creation and dependency installation
"""

import os
import sys
import venv
import subprocess
import platform
import json
import shutil
from pathlib import Path
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass

from .hardware_detector import HardwareInfo, detect_hardware
from .process_utils import no_window_kwargs


@dataclass
class InstallProgress:
    """Progress information for installation callbacks"""
    stage: str  # "venv", "pytorch", "dependencies", "complete"
    message: str
    percent: float  # 0-100
    is_error: bool = False


class EnvironmentManager:
    """
    Manages Python virtual environment for PyPottery Suite.
    Handles creation, PyTorch installation, and dependency management.
    """
    
    def __init__(self, base_path: Path, venv_name: str = "pypottery_env"):
        self.base_path = Path(base_path)
        self.venv_path = self.base_path / venv_name
        self.is_windows = platform.system() == "Windows"
        self.is_macos = platform.system() == "Darwin"
        self.is_linux = platform.system() == "Linux"

        # Progress callback
        self._progress_callback: Optional[Callable[[InstallProgress], None]] = None

        # uv (https://github.com/astral-sh/uv) is much faster than venv+pip.
        # Used when available; every uv-based code path below falls back to
        # plain venv/pip on any failure, so this is never a hard requirement.
        self.uv_path: Optional[Path] = self._detect_uv()

    def _detect_uv(self) -> Optional[Path]:
        """Find the uv executable if installed, checking PATH, venv, and common install dirs."""
        found = shutil.which("uv")
        if found:
            return Path(found)

        venv_uv = (self.venv_path / "Scripts" / "uv.exe") if self.is_windows else (self.venv_path / "bin" / "uv")
        if venv_uv.exists():
            return venv_uv

        candidates = [
            Path("/opt/homebrew/bin/uv"),
            Path("/usr/local/bin/uv"),
            Path.home() / ".local" / "bin" / "uv",
            Path.home() / ".cargo" / "bin" / "uv",
            Path.home() / "Library" / "Application Support" / "uv" / "bin" / "uv",
        ]
        if self.is_windows:
            candidates.extend([
                Path.home() / ".local" / "bin" / "uv.exe",
                Path.home() / "AppData" / "Local" / "Programs" / "uv" / "uv.exe",
            ])

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def ensure_uv(self) -> Optional[Path]:
        """
        Ensure uv is available. If not detected globally, installs it inside
        the virtual environment using pip, so that all subsequent dependency
        and PyTorch installations benefit from uv's high performance.
        """
        self.uv_path = self._detect_uv()
        if self.uv_path:
            return self.uv_path

        venv_uv = (self.venv_path / "Scripts" / "uv.exe") if self.is_windows else (self.venv_path / "bin" / "uv")
        if venv_uv.exists():
            self.uv_path = venv_uv
            return self.uv_path

        if self.venv_exists() and self.pip_executable.exists():
            try:
                self._report_progress("venv", "Installing uv via pip for ultra-fast setup...", 11)
                success, _ = self.run_pip_command(["install", "uv", "--quiet"], capture_output=True)
                if success and venv_uv.exists():
                    self.uv_path = venv_uv
                    self._report_progress("venv", "uv package installer ready (fast mode active)", 13)
                    return self.uv_path
            except Exception:
                pass

        return None
    
    @property
    def python_executable(self) -> Path:
        """Get path to Python executable in venv"""
        if self.is_windows:
            return self.venv_path / "Scripts" / "python.exe"
        return self.venv_path / "bin" / "python"
    
    @property
    def pip_executable(self) -> Path:
        """Get path to pip executable in venv"""
        if self.is_windows:
            return self.venv_path / "Scripts" / "pip.exe"
        return self.venv_path / "bin" / "pip"
    
    @property
    def activate_script(self) -> Path:
        """Get path to activation script"""
        if self.is_windows:
            return self.venv_path / "Scripts" / "activate.bat"
        return self.venv_path / "bin" / "activate"
    
    def set_progress_callback(self, callback: Callable[[InstallProgress], None]):
        """Set callback for progress updates"""
        self._progress_callback = callback
    
    def _report_progress(self, stage: str, message: str, percent: float, is_error: bool = False):
        """Report progress to callback if set"""
        if self._progress_callback:
            self._progress_callback(InstallProgress(stage, message, percent, is_error))
    
    def venv_exists(self) -> bool:
        """Check if virtual environment exists"""
        return self.python_executable.exists()

    def base_python(self) -> str:
        """
        Real Python interpreter to use as the base for creating pypottery_env.

        Under normal execution (running from source, or the WinPython
        package's own python.exe) sys.executable already is a real
        interpreter. But inside the PyInstaller-frozen exe, sys.executable
        is PyPottery.exe itself - passing that to `venv`/uv would just
        relaunch the whole app as a second instance instead of creating a
        venv (and even if it didn't, the resulting "venv" would be a copy
        of the frozen exe, not a working Python). The exe package bundles a
        real portable Python next to itself for exactly this, see
        build_windows_release.py's create_pyinstaller_package().
        """
        if getattr(sys, "frozen", False):
            bundled = self.base_path / "python_runtime" / "python.exe"
            if bundled.exists():
                return str(bundled)
            raise RuntimeError(
                f"Bundled Python runtime not found (expected at {bundled}). "
                "Reinstall PyPottery or use the WinPython package instead."
            )
        return sys.executable

    def create_venv(self, force_recreate: bool = False) -> bool:
        """
        Create virtual environment.
        
        Args:
            force_recreate: If True, delete existing venv and create new one
            
        Returns:
            True if successful, False otherwise
        """
        self._report_progress("venv", "Creating virtual environment...", 5)
        
        if self.venv_exists():
            if force_recreate:
                self._report_progress("venv", "Removing existing environment...", 2)
                shutil.rmtree(self.venv_path)
            else:
                self._report_progress("venv", "Virtual environment already exists", 10)
                return True
        
        if self.uv_path:
            try:
                cmd = [str(self.uv_path), "venv", str(self.venv_path), "--python", self.base_python()]
                if force_recreate:
                    cmd.append("--clear")
                subprocess.run(cmd, check=True, capture_output=True, **no_window_kwargs())
                self._report_progress("venv", "Virtual environment created successfully (uv)", 10)
                return True
            except Exception as e:
                self._report_progress(
                    "venv", f"uv venv failed ({e}), falling back to standard venv...", 5
                )

        try:
            # Create venv using subprocess to avoid in-process issues (especially on macOS)
            # which can cause SIGABRT when ensurepip runs in a threaded GUI context
            cmd = [self.base_python(), "-m", "venv", str(self.venv_path)]

            if force_recreate:
                cmd.append("--clear")

            # Run venv creation as external process
            # This isolates the process and prevents signal handlers from conflicting
            subprocess.run(cmd, check=True, capture_output=True, **no_window_kwargs())

            self._report_progress("venv", "Virtual environment created successfully (pip)", 10)
            return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            self._report_progress("venv", f"Failed to create venv: {error_msg}", 0, is_error=True)
            return False
        except Exception as e:
            self._report_progress("venv", f"Failed to create venv: {e}", 0, is_error=True)
            return False
    
    def run_pip_command(self, args: List[str], capture_output: bool = False) -> Tuple[bool, str]:
        """
        Run pip command in the virtual environment.
        
        Args:
            args: Arguments to pass to pip
            capture_output: If True, capture and return output
            
        Returns:
            Tuple of (success, output_or_error)
        """
        cmd = [str(self.pip_executable)] + args
        
        try:
            if capture_output:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout for large packages
                    **no_window_kwargs(),
                )
                output = result.stdout + result.stderr
                return result.returncode == 0, output
            else:
                # Stream output for progress
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    **no_window_kwargs(),
                )
                output_lines = []
                for line in process.stdout:
                    output_lines.append(line)
                    # Could parse progress from pip output here
                
                process.wait()
                return process.returncode == 0, "".join(output_lines)
                
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, str(e)

    def _run_pip(self, args: List[str], capture_output: bool = False) -> Tuple[bool, str]:
        """
        Run a pip-style command (install/list/...) against the venv, preferring
        uv (much faster). Falls back to plain pip only if uv itself can't be
        launched (missing/corrupted binary) - if uv runs and fails for a real
        reason (bad args, network, ...), that failure is returned directly
        instead of silently retried with pip: a venv uv itself created doesn't
        ship pip.exe, so retrying there just replaces a meaningful error with
        a confusing "file not found" one.
        """
        if self.uv_path:
            cmd = [str(self.uv_path), "pip"] + args + ["--python", str(self.python_executable)]
            try:
                if capture_output:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=600, **no_window_kwargs()
                    )
                    return result.returncode == 0, result.stdout + result.stderr
                else:
                    process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                        **no_window_kwargs(),
                    )
                    output_lines = []
                    for line in process.stdout:
                        output_lines.append(line)
                    process.wait()
                    return process.returncode == 0, "".join(output_lines)
            except subprocess.TimeoutExpired:
                return False, "Installation timed out"
            except OSError:
                pass  # uv itself couldn't be launched - fall back to pip below

        return self.run_pip_command(args, capture_output=capture_output)

    def install_pytorch(self, hardware_info: HardwareInfo) -> bool:
        """
        Install PyTorch with correct variant based on hardware.
        
        Args:
            hardware_info: Hardware detection results
            
        Returns:
            True if successful
        """
        self._report_progress("pytorch", "Installing PyTorch...", 15)

        # Base packages
        packages = ["torch", "torchvision", "torchaudio"]
        backend = "uv" if self.uv_path else "pip"

        # Uninstall any previous build first. Without this, switching variant
        # later (e.g. CPU -> CUDA or CUDA -> CPU) can silently no-op: pip/uv
        # won't reinstall an already-satisfied unpinned package, and a plain
        # --upgrade only works one direction (a CUDA build's "+cuXXX" local
        # version segment sorts higher than the bare CPU version per PEP 440,
        # so CPU->CUDA upgrades fine but CUDA->CPU does nothing). Uninstalling
        # first sidesteps that comparison entirely - exits cleanly even if
        # nothing is installed yet.
        # NOTE: `-y` is pip-only syntax (skips its confirmation prompt) - uv
        # doesn't prompt and rejects the flag outright, so it's only added
        # for the plain-pip backend.
        self._report_progress("pytorch", "Removing any existing PyTorch installation...", 16)
        uninstall_args = ["uninstall"] + packages if backend == "uv" else ["uninstall", "-y"] + packages
        self._run_pip(uninstall_args)

        # Build pip command
        cmd = ["install"] + packages

        if hardware_info.pytorch_index_url:
            cmd.extend(["--index-url", hardware_info.pytorch_index_url])

        self._report_progress(
            "pytorch",
            f"Installing PyTorch ({hardware_info.recommended_pytorch_variant}) via {backend}...",
            20
        )

        success, output = self._run_pip(cmd)
        
        if success:
            self._report_progress("pytorch", "PyTorch installed successfully", 40)
        else:
            self._report_progress("pytorch", f"PyTorch installation failed: {output}", 15, is_error=True)
        
        return success
    
    def install_requirements(self, requirements_file: Path) -> bool:
        """
        Install requirements from file, excluding PyTorch packages.
        
        Args:
            requirements_file: Path to requirements.txt
            
        Returns:
            True if successful
        """
        if not requirements_file.exists():
            self._report_progress("dependencies", f"Requirements file not found: {requirements_file}", 40, is_error=True)
            return False
        
        self._report_progress("dependencies", "Installing dependencies...", 45)
        
        # Read requirements and filter out PyTorch packages (already installed)
        pytorch_packages = {"torch", "torchvision", "torchaudio"}
        filtered_requirements = []
        
        with open(requirements_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Extract package name (before ==, >=, etc.)
                pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
                if pkg_name.lower() not in pytorch_packages:
                    filtered_requirements.append(line)
        
        # Create temporary requirements file
        temp_req_file = self.base_path / "temp_requirements.txt"
        with open(temp_req_file, "w") as f:
            f.write("\n".join(filtered_requirements))
        
        try:
            # Install in batches to show progress
            total = len(filtered_requirements)
            batch_size = 10
            
            for i in range(0, total, batch_size):
                batch = filtered_requirements[i:i+batch_size]
                progress = 45 + (i / total) * 45  # 45-90%
                
                self._report_progress(
                    "dependencies", 
                    f"Installing packages ({i+1}-{min(i+batch_size, total)}/{total})...", 
                    progress
                )
                
                success, output = self._run_pip(["install"] + batch)
                if not success:
                    self._report_progress("dependencies", f"Installation failed: {output}", progress, is_error=True)
                    return False
            
            self._report_progress("dependencies", "All dependencies installed", 90)
            return True
            
        finally:
            # Cleanup temp file
            if temp_req_file.exists():
                temp_req_file.unlink()
    
    def install_package(self, package: str) -> bool:
        """Install a single package"""
        success, output = self._run_pip(["install", package])
        return success

    def get_installed_packages(self) -> dict:
        """Get dictionary of installed packages and versions"""
        success, output = self._run_pip(["list", "--format=json"], capture_output=True)
        if success:
            try:
                packages = json.loads(output)
                return {p["name"].lower(): p["version"] for p in packages}
            except json.JSONDecodeError:
                pass
        return {}
    
    def verify_pytorch_installation(self) -> Tuple[bool, str]:
        """
        Verify PyTorch is installed and working correctly.
        
        Returns:
            Tuple of (success, message)
        """
        test_script = """
import torch
import sys

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")

if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    print("MPS (Apple Silicon) available: True")

# Quick tensor test
x = torch.rand(3, 3)
print(f"Tensor test passed: {x.shape}")
"""
        
        try:
            result = subprocess.run(
                [str(self.python_executable), "-c", test_script],
                capture_output=True,
                text=True,
                timeout=30,
                **no_window_kwargs(),
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except Exception as e:
            return False, str(e)
    
    def full_install(self, hardware_info: HardwareInfo, requirements_file: Path) -> bool:
        """
        Perform complete installation: venv + PyTorch + dependencies.
        
        Args:
            hardware_info: Hardware detection results
            requirements_file: Path to requirements.txt
            
        Returns:
            True if all steps successful
        """
        # Step 1: Create venv
        if not self.create_venv():
            return False
        
        # Step 2: Ensure uv is ready for maximum installation speed
        if not self.uv_path:
            self.ensure_uv()

        # Step 3: Install PyTorch
        if not self.install_pytorch(hardware_info):
            return False
        
        # Step 4: Verify PyTorch
        self._report_progress("pytorch", "Verifying PyTorch installation...", 42)
        success, msg = self.verify_pytorch_installation()
        if not success:
            self._report_progress("pytorch", f"PyTorch verification failed: {msg}", 42, is_error=True)
            # Continue anyway, might work for CPU-only
        
        # Step 5: Install other dependencies
        if not self.install_requirements(requirements_file):
            return False
        
        # Step 6: Complete
        self._report_progress("complete", "Installation complete!", 100)
        return True
    
    def get_activation_command(self) -> str:
        """Get command to activate the virtual environment"""
        if self.is_windows:
            return f'"{self.venv_path}\\Scripts\\activate.bat"'
        else:
            return f'source "{self.venv_path}/bin/activate"'


def create_environment(base_path: Path, 
                       requirements_file: Path,
                       progress_callback: Optional[Callable] = None) -> Tuple[bool, EnvironmentManager]:
    """
    Convenience function to create and set up environment.
    
    Args:
        base_path: Base directory for venv
        requirements_file: Path to requirements.txt
        progress_callback: Optional callback for progress updates
        
    Returns:
        Tuple of (success, manager)
    """
    # Detect hardware
    hardware_info = detect_hardware()
    
    # Create manager
    manager = EnvironmentManager(base_path)
    
    if progress_callback:
        manager.set_progress_callback(progress_callback)
    
    # Run installation
    success = manager.full_install(hardware_info, requirements_file)
    
    return success, manager


if __name__ == "__main__":
    # Test environment creation
    import argparse
    
    parser = argparse.ArgumentParser(description="PyPottery Environment Manager")
    parser.add_argument("--base-path", type=Path, default=Path.cwd())
    parser.add_argument("--requirements", type=Path, default=Path.cwd() / "requirements.txt")
    args = parser.parse_args()
    
    def print_progress(progress: InstallProgress):
        status = "❌" if progress.is_error else "✓"
        print(f"[{progress.percent:5.1f}%] {status} {progress.stage}: {progress.message}")
    
    print("Starting environment setup...")
    success, manager = create_environment(
        args.base_path, 
        args.requirements,
        print_progress
    )
    
    if success:
        print(f"\n✅ Environment ready at: {manager.venv_path}")
        print(f"   Activate with: {manager.get_activation_command()}")
    else:
        print("\n❌ Environment setup failed")
        sys.exit(1)
