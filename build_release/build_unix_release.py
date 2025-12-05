"""
Build macOS/Linux Release Package for PyPottery Suite Launcher

Creates distributable packages with embedded Python using python-build-standalone.
This ensures users don't need to have Python installed on their system.

Builds for:
- macOS (x86_64 and ARM64/Apple Silicon)  
- Linux (x86_64)
"""

import os
import sys
import shutil
import zipfile
import tarfile
import urllib.request
import tempfile
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.12.7"

# Python Standalone builds from https://github.com/indygreg/python-build-standalone
# Using the "install_only" builds which are smaller and ready to use
PYTHON_STANDALONE_URLS = {
    "macos-x86_64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-x86_64-apple-darwin-install_only.tar.gz",
    "macos-arm64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-aarch64-apple-darwin-install_only.tar.gz",
    "linux-x86_64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz",
}

# Base packages needed for the launcher
LAUNCHER_PACKAGES = [
    "customtkinter",
    "pillow", 
    "psutil",
    "requests",
    "packaging"
]


def download_file(url: str, dest: Path, desc: str = ""):
    """Download file with progress"""
    print(f"📥 Downloading {desc or url}...")
    
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, downloaded * 100 // total_size)
            bar = "█" * (percent // 2) + "░" * (50 - percent // 2)
            print(f"\r   [{bar}] {percent}%", end="", flush=True)
    
    urllib.request.urlretrieve(url, dest, report_progress)
    print()  # New line after progress


def create_unix_release(platform_key: str = None):
    """Create Unix release package for specified platform or all platforms"""
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    release_dir = script_dir / "release"
    
    # If no platform specified, build all
    platforms_to_build = [platform_key] if platform_key else list(PYTHON_STANDALONE_URLS.keys())
    
    created_packages = []
    
    for platform_name in platforms_to_build:
        print()
        print("=" * 60)
        print(f"🏗️  Building for: {platform_name}")
        print("=" * 60)
        
        package_name = f"PyPottery-Launcher-{platform_name}"
        package_dir = release_dir / package_name
        python_dir = package_dir / "python"
        launcher_dir = package_dir / "launcher"
        
        # Clean previous build for this platform
        if package_dir.exists():
            print(f"\n🧹 Cleaning previous {platform_name} build...")
            shutil.rmtree(package_dir)
        
        # Create directories
        release_dir.mkdir(parents=True, exist_ok=True)
        package_dir.mkdir()
        launcher_dir.mkdir()
        
        # 1. Download and extract Python standalone
        print(f"\n📦 Step 1: Downloading Python {PYTHON_VERSION} for {platform_name}...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            python_tar = Path(tmpdir) / "python.tar.gz"
            download_file(PYTHON_STANDALONE_URLS[platform_name], python_tar, f"Python {PYTHON_VERSION}")
            
            print("   Extracting Python...")
            with tarfile.open(python_tar, 'r:gz') as tf:
                tf.extractall(package_dir)
            
            # The archive extracts to a "python" folder
            print(f"   ✓ Python {PYTHON_VERSION} extracted")
        
        # 2. Note about dependencies
        print("\n📦 Step 2: Dependencies setup...")
        print("   (Dependencies will be installed on first run)")
        
        # 3. Copy launcher files
        print("\n📦 Step 3: Copying launcher files...")
        
        src_launcher = project_root / "launcher"
        for item in src_launcher.iterdir():
            if item.name == "__pycache__":
                continue
            dest = launcher_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        print("   ✓ Copied launcher module")
        
        # Copy requirements.txt
        requirements_src = project_root / "requirements.txt"
        if requirements_src.exists():
            shutil.copy2(requirements_src, package_dir / "requirements.txt")
            print("   ✓ Copied requirements.txt")
        
        # Copy logo images
        imgs_src = project_root / "imgs"
        if imgs_src.exists():
            shutil.copytree(imgs_src, package_dir / "imgs")
            print("   ✓ Copied logo images")
        
        # Copy application icon
        icon_src = project_root / "icon_app.ico"
        if icon_src.exists():
            shutil.copy2(icon_src, package_dir / "icon_app.ico")
            print("   ✓ Copied application icon")
        
        # 4. Create launcher scripts
        print("\n📦 Step 4: Creating launcher scripts...")
        
        # Create install script (installs pip packages on first run)
        install_sh = package_dir / "install.sh"
        install_content = f'''#!/bin/bash
# PyPottery Suite Launcher - Dependency Installer
# This script installs required Python packages using the bundled Python

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/python/bin/python3"
PIP_BIN="$SCRIPT_DIR/python/bin/pip3"

echo "========================================"
echo "  PyPottery Suite - Installing Dependencies"
echo "========================================"
echo

# Check if packages already installed
if "$PYTHON_BIN" -c "import customtkinter" 2>/dev/null; then
    echo "✓ Dependencies already installed"
    exit 0
fi

echo "📦 Installing Python packages..."
"$PIP_BIN" install --upgrade pip --quiet
"$PIP_BIN" install {' '.join(LAUNCHER_PACKAGES)} --quiet

if [ $? -eq 0 ]; then
    echo "✅ Installation complete!"
else
    echo "❌ Installation failed. Please check your internet connection."
    exit 1
fi
'''
        install_sh.write_text(install_content, encoding='utf-8')
        
        # Create main launcher script
        launcher_sh = package_dir / "PyPottery.sh"
        launcher_content = '''#!/bin/bash
# PyPottery Suite Launcher

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/python/bin/python3"

cd "$SCRIPT_DIR"

# Check if dependencies installed, if not run installer
if ! "$PYTHON_BIN" -c "import customtkinter" 2>/dev/null; then
    echo "First time setup - installing dependencies..."
    chmod +x install.sh
    ./install.sh
    if [ $? -ne 0 ]; then
        echo "Setup failed. Press Enter to exit..."
        read
        exit 1
    fi
fi

# Run the launcher
"$PYTHON_BIN" -c "import sys; sys.path.insert(0, '.'); from launcher.gui import main; main()"
'''
        launcher_sh.write_text(launcher_content, encoding='utf-8')
        
        print("   ✓ Created PyPottery.sh")
        print("   ✓ Created install.sh")
        
        # 5. Create README
        readme = package_dir / "README.txt"
        platform_display = {
            "macos-x86_64": "macOS (Intel)",
            "macos-arm64": "macOS (Apple Silicon M1/M2/M3)",
            "linux-x86_64": "Linux (64-bit)"
        }
        readme_content = f'''
╔════════════════════════════════════════════════════════════════╗
║              PyPottery Suite Launcher                          ║
║         Digitizing Pottery Documentation                       ║
║                                                                ║
║         Platform: {platform_display.get(platform_name, platform_name):40} ║
╚════════════════════════════════════════════════════════════════╝

QUICK START
-----------
1. Open Terminal in this folder
2. Make the launcher executable (first time only):
   chmod +x PyPottery.sh install.sh
3. Run: ./PyPottery.sh

The first run will automatically install required dependencies.

REQUIREMENTS
------------
- {platform_display.get(platform_name, platform_name)}
- 8GB RAM minimum (16GB recommended for AI features)
- NVIDIA GPU with CUDA support (optional, Linux only)
- Apple Silicon GPU acceleration (macOS ARM64)

INCLUDED APPLICATIONS
---------------------
• PyPottery Layout - Create publication-ready pottery plates
• PyPottery Lens   - AI-powered pottery fragment detection  
• PyPottery Ink    - AI-assisted digital inking

TROUBLESHOOTING
---------------
If you encounter issues:
1. Ensure the scripts are executable: chmod +x *.sh
2. Delete any "pypottery_env" folder if it exists
3. Run ./install.sh manually to reinstall dependencies

For more help, visit: https://github.com/lrncrd/PyPottery
'''
        readme.write_text(readme_content, encoding='utf-8')
        print("   ✓ Created README.txt")
        
        # 6. Create zip package
        print("\n📦 Step 5: Creating distribution package...")
        
        zip_name = f"PyPottery-Launcher-{platform_name}-v1.0.0"
        zip_path = release_dir / f"{zip_name}.zip"
        
        # Remove old zip if exists
        if zip_path.exists():
            zip_path.unlink()
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in package_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(release_dir)
                    zf.write(file_path, arcname)
        
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        
        print(f"\n✅ {platform_name} BUILD COMPLETE!")
        print(f"   📁 {zip_path.name}")
        print(f"   📊 Size: {size_mb:.1f} MB")
        
        created_packages.append((platform_name, zip_path))
    
    return created_packages


def main():
    """Main entry point"""
    print("=" * 60)
    print("🏗️  PyPottery Suite Launcher - Unix Release Builder")
    print("=" * 60)
    print()
    print("This will build packages for:")
    print("  • macOS Intel (x86_64)")
    print("  • macOS Apple Silicon (ARM64)")
    print("  • Linux (x86_64)")
    print()
    
    packages = create_unix_release()
    
    print()
    print("=" * 60)
    print("🎉 ALL UNIX BUILDS COMPLETE!")
    print("=" * 60)
    print()
    print("📦 Created packages:")
    for name, path in packages:
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"   • {name}: {path.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Build cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
