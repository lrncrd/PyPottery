"""
Environment Manager for PyPottery Suite
Handles virtual environment creation and dependency installation
"""

import logging
import os
import re
import sys
import time
import venv
import subprocess
import platform
import json
import shutil
from pathlib import Path
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass

from .error_messages import classify
from .hardware_detector import HardwareInfo, detect_hardware, detect_venv_pytorch
from .process_utils import no_window_kwargs, resource_path

logger = logging.getLogger("launcher.env")

# Written only once a full install has actually succeeded. Its absence is what
# tells a half-finished environment (venv created, PyTorch download died) apart
# from a working one - the interpreter existing proves nothing.
ENV_MARKER_NAME = ".pypottery_env.json"
ENV_MARKER_SCHEMA = 1


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
    
    def __init__(self, base_path: Path, venv_name: str = "pypottery_env", developer_mode: bool = False):
        self.base_path = Path(base_path)
        self.venv_name = venv_name
        self.venv_path = self.base_path / venv_name
        self.developer_mode = developer_mode
        self.system_python = Path(sys.executable)
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

        # Deliberately python_available(), not venv_exists(): this runs during
        # an install, when the environment is by definition not "ready" yet.
        if self.python_available() and self.pip_executable.exists():
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
        """Get path to Python executable in venv or system python in developer mode"""
        if self.developer_mode:
            return self.system_python
        if self.is_windows:
            return self.venv_path / "Scripts" / "python.exe"
        return self.venv_path / "bin" / "python"
    
    @property
    def pip_executable(self) -> Path:
        """Get path to pip executable in venv or system pip in developer mode"""
        if self.developer_mode:
            pip_which = shutil.which("pip")
            if pip_which:
                return Path(pip_which)
            if self.is_windows:
                candidate = self.system_python.parent / "Scripts" / "pip.exe"
            else:
                candidate = self.system_python.parent / "pip"
            if candidate.exists():
                return candidate
            return Path("pip")
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
    
    def _report_progress(self, stage: str, message: str, percent: float,
                         is_error: bool = False, detail: str = ""):
        """
        Report progress to callback if set.

        `detail` is the raw tool output (pip/uv can emit hundreds of lines):
        it goes to the log file only, never into the UI.
        """
        if detail:
            logger.log(logging.ERROR if is_error else logging.INFO,
                       "%s [%s]\n%s", message, stage, detail.strip())
        elif is_error:
            logger.error("%s [%s]", message, stage)

        if self._progress_callback:
            self._progress_callback(InstallProgress(stage, message, percent, is_error))

    # ---- Environment state --------------------------------------------

    @property
    def marker_path(self) -> Path:
        return self.venv_path / ENV_MARKER_NAME

    def _read_marker(self) -> Optional[dict]:
        try:
            data = json.loads(self.marker_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if data.get("schema") == ENV_MARKER_SCHEMA else None

    def _write_marker(self, hardware_info: HardwareInfo):
        payload = {
            "schema": ENV_MARKER_SCHEMA,
            "pytorch_variant": hardware_info.recommended_pytorch_variant,
            "pytorch_index_url": hardware_info.pytorch_index_url,
            "python_version": platform.python_version(),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        tmp = self.marker_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self.marker_path)
        except OSError:
            logger.exception("Could not write the environment marker")

    def _clear_marker(self):
        try:
            self.marker_path.unlink()
        except OSError:
            pass

    def python_available(self) -> bool:
        """Can the interpreter actually be run? (Not 'is it complete'.)"""
        python = self.python_executable
        if self.developer_mode:
            return python.exists()
        # A venv built from an AppImage's temporary mount leaves a symlink
        # pointing at a path that no longer exists on the next launch;
        # exists() already returns False for that, but be explicit about it.
        if not python.exists():
            return False
        try:
            result = subprocess.run(
                [str(python), "-c", "pass"], capture_output=True, timeout=20, **no_window_kwargs()
            )
            return result.returncode == 0
        except Exception:
            return False

    def env_state(self) -> dict:
        """
        What shape is the environment in?

        absent     - never created
        broken     - present but the interpreter won't run (deleted, or a
                     dangling symlink from a previous AppImage mount)
        incomplete - interpreter runs, but the install never finished
        ready      - usable
        """
        python = self.python_executable
        payload = {
            "python_executable": str(python),
            "variant": None,
            "reason": "",
            "developer_mode": self.developer_mode,
        }

        if self.developer_mode:
            return {
                **payload,
                "status": "ready",
                "ready": True,
                "exists": True,
                "variant": "system",
                "reason": "Developer Mode active: using active terminal Python environment",
            }

        if not self.venv_path.exists():
            return {**payload, "status": "absent", "ready": False, "exists": False,
                    "reason": "No Python environment yet"}

        if not self.python_available():
            return {**payload, "status": "broken", "ready": False, "exists": True,
                    "reason": "The Python environment is damaged and needs to be rebuilt"}

        marker = self._read_marker()
        if not marker:
            return {**payload, "status": "incomplete", "ready": False, "exists": True,
                    "reason": "Setup did not finish - the environment needs repairing"}

        return {**payload, "status": "ready", "ready": True, "exists": True,
                "variant": marker.get("pytorch_variant")}

    def venv_exists(self) -> bool:
        """True only for an environment that finished installing and still runs."""
        if self.developer_mode:
            return True
        return self.env_state()["status"] == "ready"

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

        For an AppImage the problem is the same in a different disguise:
        sys.executable lives on a temporary mount whose path changes on every
        run, so a venv built from it dangles the next time the app starts.
        ensure_base_python() copies that interpreter somewhere permanent and
        this returns the copy.
        """
        if getattr(sys, "frozen", False):
            for root in (resource_path(), self.base_path):
                bundled = root / "python_runtime" / "python.exe"
                if bundled.exists():
                    return str(bundled)
            raise RuntimeError(
                "Bundled Python runtime not found (expected at "
                f"{resource_path() / 'python_runtime' / 'python.exe'}). "
                "Reinstall PyPottery or use the WinPython package instead."
            )

        if os.environ.get("APPIMAGE"):
            bundled = self._appimage_runtime_dir() / "bin" / "python3"
            if bundled.exists():
                return str(bundled)
            raise RuntimeError(
                f"Bundled Python runtime not found (expected at {bundled}). "
                "Make sure PyPottery can write to the folder containing the .AppImage file."
            )

        return sys.executable

    def _appimage_runtime_dir(self) -> Path:
        return self.base_path / "python_runtime"

    def ensure_base_python(self):
        """
        Give the launcher a Python interpreter that will still be there next
        time. Only does anything inside an AppImage, where the bundled
        interpreter lives on a mount that disappears when the app exits.
        """
        if getattr(sys, "frozen", False) or not os.environ.get("APPIMAGE"):
            return

        target = self._appimage_runtime_dir()
        marker = target / ".pypottery_runtime.json"
        version = platform.python_version()

        if (target / "bin" / "python3").exists():
            try:
                if json.loads(marker.read_text(encoding="utf-8")).get("python_version") == version:
                    return
            except (OSError, ValueError):
                pass  # Unreadable or from an older build - copy it again.

        source = Path(sys.executable).resolve().parent.parent
        self._report_progress(
            "venv", "Preparing the bundled Python runtime (one-time, this takes a minute)...", 2
        )
        logger.info("Copying AppImage runtime %s -> %s", source, target)

        staging = target.with_name("python_runtime.tmp")
        try:
            if staging.exists():
                shutil.rmtree(staging)
            shutil.copytree(source, staging, symlinks=True)
            (staging / ".pypottery_runtime.json").write_text(
                json.dumps({"python_version": version}), encoding="utf-8"
            )
            if target.exists():
                shutil.rmtree(target)
            os.replace(staging, target)
            self._report_progress("venv", "Bundled Python runtime ready", 4)
        except OSError as e:
            shutil.rmtree(staging, ignore_errors=True)
            self._report_progress("venv", classify(e).message, 0, is_error=True, detail=str(e))
            raise

    def create_venv(self, force_recreate: bool = False) -> bool:
        """
        Create virtual environment.
        
        Args:
            force_recreate: If True, delete existing venv and create new one
            
        Returns:
            True if successful, False otherwise
        """
        self._report_progress("venv", "Creating virtual environment...", 5)

        self.ensure_base_python()

        if self.venv_path.exists():
            reusable = self.python_available() and not force_recreate
            if reusable:
                self._report_progress("venv", "Virtual environment already exists", 10)
                return True
            # Deleting outright rather than passing --clear: neither venv nor
            # uv replaces a *dangling* symlink (the state an AppImage leaves
            # behind once its temporary mount is gone), so they would both
            # "succeed" and leave the environment just as broken.
            self._report_progress("venv", "Removing the previous environment...", 2)
            try:
                shutil.rmtree(self.venv_path)
            except OSError as e:
                self._report_progress(
                    "venv", classify(e).message, 0, is_error=True, detail=str(e)
                )
                return False

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
            self._report_progress(
                "pytorch", f"PyTorch installation failed. {classify(output).message}",
                15, is_error=True, detail=output,
            )

        return success
    
    def install_requirements(self, requirements_file: Path,
                             hardware_info: Optional[HardwareInfo] = None) -> bool:
        """
        Install requirements from file, excluding PyTorch packages.

        Args:
            requirements_file: Path to requirements.txt
            hardware_info: If given, used after installing to confirm a
                transitive dependency didn't silently swap out the GPU build
                of PyTorch for a CPU one (see the re-check below).

        Returns:
            True if successful
        """
        if not requirements_file.exists():
            self._report_progress("dependencies", f"Requirements file not found: {requirements_file}", 40, is_error=True)
            return False

        self._report_progress("dependencies", "Installing dependencies...", 45)

        # Read requirements and filter out PyTorch packages (already installed).
        # requirements.txt is a file we author ourselves, not arbitrary user
        # input, so this doesn't need to be a full pip requirements parser -
        # but it does need to not mis-handle its own valid syntax:
        #  - "-r other.txt" / "--extra-index-url ..." / "-e ." are pip options,
        #    not package names, and must never be split across a batch boundary
        #    (they'd be sent to pip completely detached from what they modify);
        #  - an inline "package==1.0  # note" comment must not become part of
        #    the version spec passed to pip.
        pytorch_packages = {"torch", "torchvision", "torchaudio"}
        filtered_requirements = []
        global_pip_args = []

        with open(requirements_file, "r") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                # Strip an inline comment (a '#' preceded by whitespace),
                # mirroring pip's own COMMENT_RE - a bare '#' with no
                # preceding space is left alone (could be part of a URL).
                line = re.sub(r"(?:\s+)#.*$", "", line).strip()
                if not line:
                    continue
                if line.startswith("-"):
                    global_pip_args.extend(line.split())
                    continue
                # Extract package name (before ==, >=, etc.)
                pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
                if pkg_name.lower() not in pytorch_packages:
                    filtered_requirements.append(line)

        # Install in batches to show progress
        total = len(filtered_requirements)
        batch_size = 10

        for i in range(0, total, batch_size):
            batch = filtered_requirements[i:i + batch_size]
            progress = 45 + (i / total) * 45 if total else 45  # 45-90%

            self._report_progress(
                "dependencies",
                f"Installing packages ({i+1}-{min(i+batch_size, total)}/{total})...",
                progress
            )

            success, output = self._run_pip(["install"] + global_pip_args + batch)
            if not success:
                self._report_progress(
                    "dependencies", f"Installing dependencies failed. {classify(output).message}",
                    progress, is_error=True, detail=output,
                )
                return False

        self._report_progress("dependencies", "All dependencies installed", 88)

        if hardware_info is not None:
            self._reverify_pytorch_variant(hardware_info)

        return True

    def _reverify_pytorch_variant(self, hardware_info: HardwareInfo):
        """
        A transitive dependency pulled in by requirements.txt (something
        merely requiring "torch>=2.0", say) can in principle make pip
        resolve and reinstall a plain CPU build from PyPI's default index,
        silently undoing a GPU install that just succeeded. Cheap insurance:
        check what's actually there now, and if it doesn't match, put the
        right build back.
        """
        wants_cuda = bool(hardware_info.pytorch_index_url) and \
            hardware_info.recommended_pytorch_variant.startswith("cu")
        if not wants_cuda:
            return

        _, device = detect_venv_pytorch(self.python_executable)
        if device and device.startswith("CUDA"):
            return

        self._report_progress(
            "dependencies",
            "A dependency reset PyTorch to a CPU-only build - reinstalling the GPU version...",
            89,
        )
        packages = ["torch", "torchvision", "torchaudio"]
        cmd = ["install", "--force-reinstall"] + packages + ["--index-url", hardware_info.pytorch_index_url]
        success, output = self._run_pip(cmd)
        if not success:
            self._report_progress(
                "dependencies", f"Could not restore the GPU build of PyTorch. {classify(output).message}",
                89, detail=output,
            )
    
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
    
    def full_install(self, hardware_info: HardwareInfo, requirements_file: Path,
                     force_recreate: bool = False) -> bool:
        """
        Perform complete installation: venv + PyTorch + dependencies.
        
        Args:
            hardware_info: Hardware detection results
            requirements_file: Path to requirements.txt
            force_recreate: Rebuild the venv from scratch instead of reusing it

        Returns:
            True if all steps successful
        """
        # Any environment being (re)built is incomplete until proven otherwise:
        # clearing the marker first means a run that dies halfway can never
        # leave behind something that still claims to be ready.
        self._clear_marker()

        # Step 1: Create venv
        if not self.create_venv(force_recreate=force_recreate):
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
            # Not fatal - a CPU-only install can still be perfectly usable -
            # but the full output belongs in the log, not in the UI.
            self._report_progress(
                "pytorch", "PyTorch verification reported a problem - continuing anyway", 42,
                detail=msg,
            )

        # Step 5: Install other dependencies
        if not self.install_requirements(requirements_file, hardware_info):
            return False

        # Step 6: Complete
        self._write_marker(hardware_info)
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
