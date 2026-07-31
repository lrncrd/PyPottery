#!/usr/bin/env python3
"""
PyPottery Suite Installer
Bootstrap script to install dependencies and launch the GUI launcher.

Usage:
    python install.py              # Install and launch
    python install.py --no-launch  # Install only
    python install.py --upgrade    # Upgrade existing installation
"""

import os
import shutil
import sys
import subprocess
import platform
import argparse
from pathlib import Path
from typing import List, Optional


# Minimum Python version
MIN_PYTHON_VERSION = (3, 12)

# Bootstrap dependencies (minimal set needed for the launcher's web GUI)
BOOTSTRAP_PACKAGES = [
    "flask>=3.0.0",
    "psutil>=5.9.0",
]


def check_python_version():
    """Check if Python version meets requirements"""
    current = sys.version_info[:2]
    if current < MIN_PYTHON_VERSION:
        print(f"❌ Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required")
        print(f"   Current version: {current[0]}.{current[1]}")
        sys.exit(1)
    print(f"✅ Python {current[0]}.{current[1]} detected")


def _find_or_install_uv() -> Optional[Path]:
    """
    Find uv (https://github.com/astral-sh/uv) on PATH or common install dirs,
    installing it via the official installer if it's missing. Returns None on
    any failure - callers must fall back to plain pip, never hard-fail here.
    """
    found = shutil.which("uv")
    if found:
        return Path(found)

    candidates = [Path.home() / ".local" / "bin" / "uv", Path.home() / ".cargo" / "bin" / "uv"]
    if platform.system() == "Windows":
        candidates.append(Path.home() / ".local" / "bin" / "uv.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate

    print("📥 uv not found - installing it for faster package installs...")
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command",
                 "irm https://astral.sh/uv/install.ps1 | iex"],
                capture_output=True, timeout=120
            )
        else:
            subprocess.run(
                ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                capture_output=True, timeout=120
            )
    except Exception:
        pass

    found = shutil.which("uv")
    if found:
        return Path(found)
    for candidate in candidates:
        if candidate.exists():
            return candidate

    print("⚠️  Could not install uv - falling back to pip (this is fine, just slower)")
    return None


def install_packages(packages: List[str], upgrade: bool = False, uv_path: Optional[Path] = None):
    """Install packages, preferring uv (faster) with a pip fallback"""
    print(f"📦 Installing: {', '.join(packages)}")

    if uv_path:
        cmd = [str(uv_path), "pip", "install", "--python", sys.executable]
        if upgrade:
            cmd.append("--upgrade")
        cmd.extend(packages)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        print("⚠️  uv install failed, falling back to pip...")

    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(packages)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Installation failed:")
        print(result.stderr)
        return False

    return True


def check_package_installed(package_name: str) -> bool:
    """Check if a package is installed"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def launch_gui():
    """Launch the PyPottery launcher GUI"""
    script_dir = Path(__file__).parent
    gui_script = script_dir / "launcher" / "gui.py"
    
    if not gui_script.exists():
        print(f"❌ GUI script not found: {gui_script}")
        return False
    
    print("\n🚀 Launching PyPottery Suite Launcher...")
    
    # Launch in a new process
    if platform.system() == "Windows":
        # Use pythonw for no console window on Windows
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        if pythonw.exists():
            subprocess.Popen([str(pythonw), str(gui_script)])
        else:
            subprocess.Popen([sys.executable, str(gui_script)])
    else:
        subprocess.Popen([sys.executable, str(gui_script)])
    
    return True


def print_banner():
    """Print installation banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║               🏺 PyPottery Suite Installer                    ║
║                                                               ║
║   AI-powered tools for archaeological pottery analysis        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_post_install_info():
    """Print post-installation information"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                   Installation Complete!                       ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  The launcher will help you:                                  ║
║                                                               ║
║  1. Set up Python environment with PyTorch (CUDA/MPS/CPU)     ║
║  2. Download PyPottery applications:                          ║
║     • PyPottery Layout - Create pottery tables/layouts        ║
║     • PyPottery Lens   - AI object detection & classification ║
║     • PyPottery Ink    - AI-assisted digital inking           ║
║  3. Launch and manage applications                            ║
║  4. Check for updates automatically                           ║
║                                                               ║
║  The launcher opens in your web browser.                      ║
║                                                               ║
║  To launch again later, run:                                  ║
║     python install.py                                         ║
║                                                               ║
║  Or directly:                                                 ║
║     python launcher/gui.py                                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)


def main():
    parser = argparse.ArgumentParser(
        description="PyPottery Suite Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python install.py              Install and launch GUI
    python install.py --no-launch  Install dependencies only
    python install.py --upgrade    Upgrade existing installation
        """
    )
    parser.add_argument(
        "--no-launch", 
        action="store_true",
        help="Don't launch GUI after installation"
    )
    parser.add_argument(
        "--upgrade",
        action="store_true", 
        help="Upgrade existing packages"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # Check Python version
    check_python_version()

    # Find (or install) uv for faster package installs - falls back to pip if unavailable
    uv_path = _find_or_install_uv()
    if uv_path:
        print(f"✅ Using uv for package installs: {uv_path}")

    # Check/install bootstrap packages
    packages_to_install = []

    for package in BOOTSTRAP_PACKAGES:
        pkg_name = package.split(">=")[0].split("==")[0]
        if not check_package_installed(pkg_name) or args.upgrade:
            packages_to_install.append(package)

    if packages_to_install:
        print("\n📥 Installing required packages...")
        if not install_packages(packages_to_install, upgrade=args.upgrade, uv_path=uv_path):
            print("❌ Failed to install required packages")
            sys.exit(1)
        print("✅ Packages installed successfully")
    else:
        print("✅ All required packages already installed")

    # Verify Flask works (the launcher's web UI depends on it)
    print("\n🔍 Verifying installation...")
    try:
        import flask
        print(f"✅ Flask {flask.__version__} ready")
    except ImportError as e:
        print(f"❌ Failed to import flask: {e}")
        sys.exit(1)

    print_post_install_info()
    
    # Launch GUI
    if not args.no_launch:
        launch_gui()
        print("\n✨ Launcher started! The window should appear shortly.")
    else:
        print("\nTo launch the GUI later, run:")
        print(f"    python {Path(__file__).parent / 'launcher' / 'gui.py'}")


if __name__ == "__main__":
    main()
