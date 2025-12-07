"""
Build macOS/Linux Release Package for PyPottery Suite Launcher

Creates distributable packages with embedded Python using python-build-standalone.
Generates proper .app bundles for macOS and standard directories for Linux.
"""

import os
import sys
import shutil
import zipfile
import urllib.request
import tempfile
import subprocess
import plistlib
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.12.7"

PYTHON_STANDALONE_URLS = {
    "macos-x86_64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-x86_64-apple-darwin-install_only.tar.gz",
    "macos-arm64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-aarch64-apple-darwin-install_only.tar.gz",
    "linux-x86_64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz",
}

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
    print()


def create_icns(png_path: Path, dest_icns: Path):
    """Create .icns file from a png using iconutil"""
    if not png_path.exists():
        print("   ⚠️ Icon PNG not found, skipping ICNS generation")
        return

    print("   🎨 Generating AppIcon.icns...")
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = Path(tmpdir) / "icon.iconset"
        iconset.mkdir()
        
        # Dimensions for iconset
        sizes = [16, 32, 128, 256, 512]
        
        try:
            for size in sizes:
                # Normal
                subprocess.run([
                    "sips", "-z", str(size), str(size), str(png_path),
                    "--out", str(iconset / f"icon_{size}x{size}.png")
                ], check=True, capture_output=True)
                
                # Retina (@2x)
                subprocess.run([
                    "sips", "-z", str(size*2), str(size*2), str(png_path),
                    "--out", str(iconset / f"icon_{size}x{size}@2x.png")
                ], check=True, capture_output=True)
            
            # Convert to icns
            subprocess.run([
                "iconutil", "-c", "icns", str(iconset),
                "-o", str(dest_icns)
            ], check=True, capture_output=True)
            print("   ✓ Created AppIcon.icns")
            
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️ Failed to generate ICNS: {e}")


def create_unix_release(platform_key: str = None):
    """Create Unix release package"""
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    release_dir = script_dir / "release"
    
    platforms_to_build = [platform_key] if platform_key else list(PYTHON_STANDALONE_URLS.keys())
    
    created_packages = []
    
    for platform_name in platforms_to_build:
        is_macos = "macos" in platform_name
        is_linux = "linux" in platform_name
        
        print()
        print("=" * 60)
        print(f"🏗️  Building for: {platform_name}")
        print("=" * 60)
        
        package_base_name = f"PyPottery-Launcher-{platform_name}"
        package_root = release_dir / package_base_name
        
        # Clean previous
        if package_root.exists():
            print(f"\n🧹 Cleaning previous {platform_name} build...")
            shutil.rmtree(package_root)
        
        release_dir.mkdir(parents=True, exist_ok=True)
        
        # --- Directory Structure ---
        if is_macos:
            # Create .app bundle structure
            app_dir = package_root / "PyPottery Launcher.app"
            contents = app_dir / "Contents"
            macos_dir = contents / "MacOS"
            resources = contents / "Resources"
            
            contents.mkdir(parents=True)
            macos_dir.mkdir()
            resources.mkdir()
            
            # Destination for python and launcher files
            python_dest = resources / "python"
            launcher_dest = resources / "launcher"
            bin_dir = macos_dir  # Where the main binary/script goes
            
        else: # Linux
            package_root.mkdir()
            python_dest = package_root / "python"
            launcher_dest = package_root / "launcher"
            resources = package_root # Alias for simplicity
            
            launcher_dest.mkdir()
        
        # 1. Download and Extract Python
        print(f"\n📦 Step 1: Downloading Python {PYTHON_VERSION}...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            python_tar = Path(tmpdir) / "python.tar.gz"
            download_file(PYTHON_STANDALONE_URLS[platform_name], python_tar, f"Python")
            
            # Use system tar to avoid symlink issues (Errno 62)
            print("   Extracting Python (via system tar)...")
            python_dest.parent.mkdir(parents=True, exist_ok=True)
            
            # We assume the tar extracts to a "python" directory.
            # We want to extract it into the destination parent.
            # Note: tar -C changes dir before extracting.
            
            # Logic: tar extracts 'python/...'
            # If we extract to python_dest.parent, we get python_dest.parent/python
            # which is python_dest.
            
            # If python_dest doesn't exist, mkdir it?
            # Actually python-standalone tars usually contain a top level folder name (e.g. 'python').
            # So extracting to the parent of python_dest works.
            
            try:
                subprocess.run(
                    ["tar", "-xzf", str(python_tar), "-C", str(python_dest.parent)],
                    check=True,
                    capture_output=True
                )
                print(f"   ✓ Python extracted")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Extraction failed: {e}")
                continue

        # 2. Copy Launcher Files
        print("\n📦 Step 2: Copying launcher files...")
        
        # Copy launcher module
        src_launcher = project_root / "launcher"
        if launcher_dest.exists(): shutil.rmtree(launcher_dest) # Ensure clean copy
        
        # Using ignore logic to skip __pycache__
        shutil.copytree(src_launcher, launcher_dest, ignore=shutil.ignore_patterns("__pycache__"))
        
        # Copy requirements
        if (project_root / "requirements.txt").exists():
            shutil.copy2(project_root / "requirements.txt", python_dest.parent / "requirements.txt")
        
        # Copy images
        imgs_src = project_root / "imgs"
        imgs_dest = resources / "imgs" if is_macos else package_root / "imgs"
        if imgs_src.exists():
            if imgs_dest.exists(): shutil.rmtree(imgs_dest)
            shutil.copytree(imgs_src, imgs_dest)

        print("   ✓ Copied files")
        
        # Copy icons to resources
        for icon_name in ["icon_app.ico", "icon_app.png"]:
            src = project_root / icon_name
            dst = resources / icon_name
            if src.exists():
                shutil.copy2(src, dst)
        print("   ✓ Copied icons")

        # 3. macOS Specifics (Bundle config)
        if is_macos:
            print("\n🍎 Step 3: Configuring App Bundle...")
            
            # Generate Info.plist
            info_plist = {
                'CFBundleName': 'PyPotteryLauncher',
                'CFBundleDisplayName': 'PyPottery Launcher',
                'CFBundleIdentifier': 'com.lrncrd.pypottery',
                'CFBundleVersion': '1.0.0',
                'CFBundlePackageType': 'APPL',
                'CFBundleExecutable': 'launcher',
                'CFBundleIconFile': 'AppIcon',
                'LSMinimumSystemVersion': '11.0',
                'NSHighResolutionCapable': True,
            }
            with open(contents / "Info.plist", 'wb') as fp:
                plistlib.dump(info_plist, fp)
            
            # Generate Icon
            icon_png = project_root / "icon_app.png"
            create_icns(icon_png, resources / "AppIcon.icns")
            
            # Create Launch Script (Executable)
            launcher_script = macos_dir / "launcher"
            script_content = """#!/bin/bash
# PyPottery Launcher Entry Point

# Calculate resources path relative to this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RESOURCES="$DIR/../Resources"
PYTHON="$RESOURCES/python/bin/python3"

# Install dependencies if needed
if ! "$PYTHON" -c "import customtkinter" 2>/dev/null; then
    # Dialog via AppleScript to show activity
    osascript -e 'display notification "Installing dependencies..." with title "PyPottery Launcher"'
    
    "$PYTHON" -m pip install --upgrade pip --quiet
    "$PYTHON" -m pip install customtkinter pillow psutil requests packaging --quiet
fi

# Run Launcher
"$PYTHON" -c "import sys; sys.path.insert(0, '$RESOURCES'); from launcher.gui import main; main()"
"""
            launcher_script.write_text(script_content, encoding='utf-8')
            launcher_script.chmod(0o755)
            
            print("   ✓ App Bundle configured")

        # 4. Linux Specifics (Launch Scripts)
        else:
            print("\n🐧 Step 3: Creating Linux scripts...")
            
            install_sh = package_root / "install.sh"
            install_sh.write_text(f"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/python/bin/python3"
PIP="$SCRIPT_DIR/python/bin/pip3"

"$PIP" install --upgrade pip
"$PIP" install {' '.join(LAUNCHER_PACKAGES)}
""", encoding='utf-8')
            install_sh.chmod(0o755)

            run_sh = package_root / "PyPottery.sh"
            run_sh.write_text("""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/python/bin/python3"

# Check deps (simple check)
if ! "$PYTHON" -c "import customtkinter" 2>/dev/null; then
    echo "Installing dependencies..."
    "$SCRIPT_DIR/install.sh"
fi

"$PYTHON" -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from launcher.gui import main; main()"
""", encoding='utf-8')
            run_sh.chmod(0o755)
            print("   ✓ Scripts created")

        # 5. Zip Package
        print("\n📦 Step 4: Compressing...")
        zip_path = release_dir / f"{package_base_name}.zip"
        if zip_path.exists(): zip_path.unlink()
        
        # Use subprocess zip for speed and preserving permissions
        subprocess.run(
            ["zip", "-r", "-q", str(zip_path), package_root.name],
            cwd=release_dir,
            check=True
        )
        
        # Calculate size
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"✅ {platform_name}: {zip_path.name} ({size_mb:.1f} MB)")
        
        created_packages.append((platform_name, zip_path))

    return created_packages

def main():
    try:
        if sys.platform == "darwin":
            # On macOS, check for sips/iconutil
            if subprocess.call(["which", "sips"], stdout=subprocess.DEVNULL) != 0:
                print("⚠️  Warning: 'sips' tool not found. Icons may not generate.")
        
        create_unix_release()
        print("\n🎉 Builds Complete!")
        
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
