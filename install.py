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
import sys
import subprocess
import platform
import argparse
from pathlib import Path


# Minimum Python version
MIN_PYTHON_VERSION = (3, 12)

# Bootstrap dependencies (minimal set needed for launcher GUI)
BOOTSTRAP_PACKAGES = [
    "customtkinter>=5.2.0",
    "psutil>=5.9.0",
    "certifi>=2024.0.0",  # SSL certificates for macOS
]


def check_python_version():
    """Check if Python version meets requirements"""
    current = sys.version_info[:2]
    if current < MIN_PYTHON_VERSION:
        print(f"❌ Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required")
        print(f"   Current version: {current[0]}.{current[1]}")
        sys.exit(1)
    print(f"✅ Python {current[0]}.{current[1]} detected")


def install_packages(packages: list, upgrade: bool = False):
    """Install packages using pip"""
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(packages)
    
    print(f"📦 Installing: {', '.join(packages)}")
    
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
    
    # Check/install bootstrap packages
    packages_to_install = []
    
    for package in BOOTSTRAP_PACKAGES:
        pkg_name = package.split(">=")[0].split("==")[0]
        if not check_package_installed(pkg_name) or args.upgrade:
            packages_to_install.append(package)
    
    if packages_to_install:
        print("\n📥 Installing required packages...")
        if not install_packages(packages_to_install, upgrade=args.upgrade):
            print("❌ Failed to install required packages")
            sys.exit(1)
        print("✅ Packages installed successfully")
    else:
        print("✅ All required packages already installed")
    
    # Verify customtkinter works
    print("\n🔍 Verifying installation...")
    try:
        import customtkinter
        print(f"✅ CustomTkinter {customtkinter.__version__} ready")
    except ImportError as e:
        print(f"❌ Failed to import customtkinter: {e}")
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
