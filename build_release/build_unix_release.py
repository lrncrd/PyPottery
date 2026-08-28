"""
Build macOS/Linux Release Package for PyPottery Suite Launcher

Creates distributable packages with embedded Python using python-build-standalone.
Generates proper .app bundles for macOS and standard directories for Linux.
"""

import argparse
import os
import sys
import shutil
import zipfile
import urllib.request
import tempfile
import subprocess
import platform
import plistlib
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.12.7"

PYTHON_STANDALONE_URLS = {
    "macos-x86_64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-x86_64-apple-darwin-install_only.tar.gz",
    "macos-arm64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-aarch64-apple-darwin-install_only.tar.gz",
    "linux-x86_64": f"https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-{PYTHON_VERSION}+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz",
}

APPIMAGETOOL_URL = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"


LAUNCHER_PACKAGES = [
    "flask",
    "psutil",
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

        except FileNotFoundError:
            print("   ⚠️ 'sips'/'iconutil' not found (these are macOS-only tools) - skipping ICNS generation")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️ Failed to generate ICNS: {e}")


def create_dmg(app_dir: Path, release_dir: Path, package_base_name: str,
                volume_name: str = "PyPottery Launcher") -> None:
    """
    Package the .app bundle into a compressed .dmg with the app icon and an
    Applications alias side by side, so people install it the standard macOS
    way (drag app onto Applications). This also fixes Gatekeeper's "App
    Translocation" for anyone who follows the drag prompt, since translocation
    only affects an app launched from its original, unmoved location - it's
    what caused "Read-only file system" errors when the .zip build was
    extracted and launched in place instead of being moved first.

    macOS-only (needs hdiutil/osascript); no-ops with a warning elsewhere,
    e.g. when cross-building a macOS package from a Linux/Windows host.
    """
    print("\n💿 Step 5: Building .dmg installer...")

    dmg_path = release_dir / f"{package_base_name}.dmg"
    if dmg_path.exists():
        dmg_path.unlink()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            staging = Path(tmpdir) / "dmg_staging"
            staging.mkdir()
            shutil.copytree(app_dir, staging / app_dir.name)
            os.symlink("/Applications", staging / "Applications")

            rw_dmg = Path(tmpdir) / "rw.dmg"
            subprocess.run([
                "hdiutil", "create", "-volname", volume_name,
                "-srcfolder", str(staging), "-ov", "-format", "UDRW",
                str(rw_dmg)
            ], check=True, capture_output=True, text=True)

            attach = subprocess.run(
                ["hdiutil", "attach", "-readwrite", "-noverify", "-noautoopen", str(rw_dmg)],
                check=True, capture_output=True, text=True
            )
            lines = attach.stdout.strip().splitlines()
            device = lines[0].split("\t")[0].strip() if lines else None
            mount_point = f"/Volumes/{volume_name}"
            for line in lines:
                parts = line.split("\t")
                if len(parts) >= 3 and parts[2].strip().startswith("/Volumes/"):
                    mount_point = parts[2].strip()

            try:
                # Symmetrical window geometry (600x360 px):
                # Center X is 300. Left icon at 150, Right icon at 450 (equidistant 150px from sides and 300px apart).
                # Vertical center at Y=160 accommodates macOS window titlebar and icon text labels.
                applescript = f'''
                tell application "Finder"
                    tell disk "{volume_name}"
                        open
                        set current view of container window to icon view
                        set toolbar visible of container window to false
                        set statusbar visible of container window to false
                        set the bounds of container window to {{250, 150, 850, 510}}
                        set viewOptions to the icon view options of container window
                        set arrangement of viewOptions to not arranged
                        set icon size of viewOptions to 100
                        set text size of viewOptions to 12
                        set position of item "{app_dir.name}" of container window to {{150, 160}}
                        set position of item "Applications" of container window to {{450, 160}}
                        close
                        open
                        update without registering applications
                        delay 1
                    end tell
                end tell
                '''
                subprocess.run(["osascript", "-e", applescript], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"   ⚠️ Could not style DMG window (continuing anyway): {e.stderr}")

            subprocess.run(["sync"], check=False)
            if device:
                subprocess.run(["hdiutil", "detach", device, "-quiet"], check=True, capture_output=True)
            else:
                subprocess.run(["hdiutil", "detach", mount_point, "-quiet"], check=True, capture_output=True)

            subprocess.run([
                "hdiutil", "convert", str(rw_dmg), "-format", "UDZO",
                "-imagekey", "zlib-level=9", "-o", str(dmg_path)
            ], check=True, capture_output=True, text=True)

        size_mb = dmg_path.stat().st_size / (1024 * 1024)
        print(f"   ✓ Created {dmg_path.name} ({size_mb:.1f} MB)")

    except FileNotFoundError:
        print("   ⚠️ 'hdiutil'/'osascript' not found (these are macOS-only tools) - skipping .dmg build")
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ Failed to build .dmg: {e.stderr if hasattr(e, 'stderr') else e}")


def create_appimage(package_root: Path, release_dir: Path, package_base_name: str) -> None:
    """
    Package the Linux build directory into a standalone .AppImage file.
    AppImage is the Linux equivalent of macOS .dmg / .app bundle:
    a single portable executable that runs on almost any Linux distribution
    without installation or root privileges.
    """
    print("\n💿 Step 5: Building .AppImage container...")
    appimage_path = release_dir / f"{package_base_name}.AppImage"
    if appimage_path.exists():
        appimage_path.unlink()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            appdir = tmp_path / "PyPottery.AppDir"
            shutil.copytree(package_root, appdir)

            # 1. Create AppRun (Entry point script for AppImage)
            app_run = appdir / "AppRun"
            app_run_content = """#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$HERE/python/bin/python3"

if [ "$1" = "--uninstall-desktop" ]; then
    rm -f "$HOME/.local/share/applications/pypottery.desktop"
    rm -f "$HOME/.local/share/icons/hicolor/512x512/apps/pypottery.png"
    rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/pypottery.png"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
    fi
    echo "✅ PyPottery desktop shortcut removed."
    exit 0
fi

# Auto-register application menu shortcut on Linux if running from AppImage
if [ -n "$APPIMAGE" ]; then
    DESKTOP_DIR="$HOME/.local/share/applications"
    ICON_DIR_512="$HOME/.local/share/icons/hicolor/512x512/apps"
    ICON_DIR_256="$HOME/.local/share/icons/hicolor/256x256/apps"
    mkdir -p "$DESKTOP_DIR" "$ICON_DIR_512" "$ICON_DIR_256" 2>/dev/null || true

    if [ -f "$HERE/icon_app.png" ]; then
        cp "$HERE/icon_app.png" "$ICON_DIR_512/pypottery.png" 2>/dev/null || true
        cp "$HERE/icon_app.png" "$ICON_DIR_256/pypottery.png" 2>/dev/null || true
    fi

    cat << EOF > "$DESKTOP_DIR/pypottery.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=PyPottery Launcher
Comment=Digitizing Archaeological Pottery Documentation
Exec="$APPIMAGE"
TryExec="$APPIMAGE"
Icon=pypottery
Terminal=false
Categories=Science;Graphics;
EOF
    chmod +x "$DESKTOP_DIR/pypottery.desktop" 2>/dev/null || true
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    fi
    if command -v gio >/dev/null 2>&1; then
        gio set -t string "$APPIMAGE" metadata::custom-icon "file://$ICON_DIR_512/pypottery.png" 2>/dev/null || true
    fi
fi

# Check deps (just enough to start the web launcher)
if ! "$PYTHON" -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    "$PYTHON" -m pip install --upgrade pip --quiet
    "$PYTHON" -m pip install flask psutil --quiet
fi

exec "$PYTHON" -c "import sys; sys.path.insert(0, '$HERE'); from launcher.gui import main; main()"
"""
            app_run.write_text(app_run_content, encoding='utf-8')
            app_run.chmod(0o755)

            # 2. Create desktop entry file
            desktop_file = appdir / "pypottery.desktop"
            desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=PyPottery Launcher
Comment=Digitizing Archaeological Pottery Documentation
Exec=AppRun
Icon=pypottery
Terminal=false
Categories=Science;Graphics;
"""
            desktop_file.write_text(desktop_content, encoding='utf-8')

            # 3. Copy icons
            icon_src = package_root / "icon_app.png"
            if icon_src.exists():
                shutil.copy2(icon_src, appdir / "pypottery.png")
                dot_icon = appdir / ".DirIcon"
                if dot_icon.exists() or dot_icon.is_symlink():
                    dot_icon.unlink()
                os.symlink("pypottery.png", dot_icon)

            # 4. Locate or download appimagetool
            appimagetool_bin = shutil.which("appimagetool")
            tool_cmd = []

            if appimagetool_bin:
                tool_cmd = [appimagetool_bin]
            else:
                downloaded_tool = tmp_path / "appimagetool"
                download_file(APPIMAGETOOL_URL, downloaded_tool, "appimagetool")
                downloaded_tool.chmod(0o755)
                tool_cmd = [str(downloaded_tool), "--appimage-extract-and-run"]

            # 5. Run appimagetool
            env = os.environ.copy()
            env["ARCH"] = "x86_64"

            res = subprocess.run(
                tool_cmd + [str(appdir), str(appimage_path)],
                env=env,
                check=True,
                capture_output=True,
                text=True
            )

        if appimage_path.exists():
            size_mb = appimage_path.stat().st_size / (1024 * 1024)
            print(f"   ✓ Created {appimage_path.name} ({size_mb:.1f} MB)")
        else:
            print("   ⚠️ appimagetool finished but AppImage file was not generated.")

    except Exception as e:
        print(f"   ⚠️ Could not build AppImage: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"      {e.stderr}")


def _build_single_platform(platform_name: str, release_dir: Path, project_root: Path) -> Path:

    """
    Build the release package for exactly one platform. Raises on failure -
    callers are responsible for isolating one platform's failure from the rest
    of a multi-platform build (e.g. a macOS target built on a Linux host can't
    generate a .icns icon, but that must not abort the Linux build too).
    """
    is_macos = "macos" in platform_name

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

    else:  # Linux
        package_root.mkdir()
        python_dest = package_root / "python"
        launcher_dest = package_root / "launcher"
        resources = package_root  # Alias for simplicity

        launcher_dest.mkdir()

    # 1. Download and Extract Python
    print(f"\n📦 Step 1: Downloading Python {PYTHON_VERSION}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        python_tar = Path(tmpdir) / "python.tar.gz"
        download_file(PYTHON_STANDALONE_URLS[platform_name], python_tar, "Python")

        # Use system tar to avoid symlink issues (Errno 62)
        print("   Extracting Python (via system tar)...")
        python_dest.parent.mkdir(parents=True, exist_ok=True)

        # python-build-standalone tars contain a top-level "python/" folder, so
        # extracting into python_dest.parent produces python_dest itself.
        subprocess.run(
            ["tar", "-xzf", str(python_tar), "-C", str(python_dest.parent)],
            check=True,
            capture_output=True
        )
        print("   ✓ Python extracted")

    # 2. Copy Launcher Files
    print("\n📦 Step 2: Copying launcher files...")

    # Ensure offline vendor assets (Bootstrap, Icons, Fonts) are present and synced
    try:
        sys.path.insert(0, str(project_root))
        from launcher.vendor_assets_manager import VendorAssetsManager
        v_mgr = VendorAssetsManager(project_root)
        v_mgr.ensure_vendor_assets()
        v_mgr.sync_to_app(project_root / "launcher")
    except Exception as e:
        print(f"   ⚠️ Vendor assets build warning: {e}")

    # Copy launcher module
    src_launcher = project_root / "launcher"
    if launcher_dest.exists():
        shutil.rmtree(launcher_dest)  # Ensure clean copy

    # Using ignore logic to skip __pycache__
    shutil.copytree(src_launcher, launcher_dest, ignore=shutil.ignore_patterns("__pycache__"))

    # Copy requirements
    if (project_root / "requirements.txt").exists():
        shutil.copy2(project_root / "requirements.txt", python_dest.parent / "requirements.txt")

    # Copy images
    imgs_src = project_root / "imgs"
    imgs_dest = resources / "imgs" if is_macos else package_root / "imgs"
    if imgs_src.exists():
        if imgs_dest.exists():
            shutil.rmtree(imgs_dest)
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
            'CFBundleVersion': '1.0.2',
            'CFBundlePackageType': 'APPL',
            'CFBundleExecutable': 'launcher',
            'CFBundleIconFile': 'AppIcon',
            'LSMinimumSystemVersion': '11.0',
            'NSHighResolutionCapable': True,
        }
        with open(contents / "Info.plist", 'wb') as fp:
            plistlib.dump(info_plist, fp)

        # Generate Icon (gracefully skipped if sips/iconutil aren't available,
        # e.g. when cross-building a macOS package from a Linux/Windows host)
        icon_png = project_root / "icon_app.png"
        create_icns(icon_png, resources / "AppIcon.icns")

        # Create Launch Script (Executable)
        launcher_script = macos_dir / "launcher"
        script_content = """#!/bin/bash
# PyPottery Launcher Entry Point

# Calculate resources path relative to this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_BUNDLE="$( cd "$DIR/../.." && pwd )"

# macOS Gatekeeper "App Translocation": an app carrying the quarantine flag
# (downloaded via browser/Slack/AirDrop/etc.) that is launched from its
# original, unmoved location gets silently run from a read-only random mount
# under .../AppTranslocation/.../d/. Everything the launcher needs to write
# (the Python venv, downloaded sub-apps) lives inside the bundle itself, so
# that read-only mount breaks setup with "Read-only file system" errors.
# Detect it and self-relocate to /Applications before doing anything else -
# translocation only applies to the original copy, not one moved elsewhere.
if [[ "$APP_BUNDLE" == *"/AppTranslocation/"* ]]; then
    APP_NAME="$(basename "$APP_BUNDLE")"
    TARGET="/Applications/$APP_NAME"

    if osascript -e 'display dialog "PyPottery Launcher deve essere spostato nella cartella Applicazioni per poter scrivere i propri file (ambiente Python, app scaricate). Vuoi spostarlo ora?" with title "PyPottery Launcher" buttons {"Annulla", "Sposta in Applicazioni"} default button "Sposta in Applicazioni" cancel button "Annulla"' >/dev/null 2>&1; then
        rm -rf "$TARGET" 2>/dev/null
        if ditto "$APP_BUNDLE" "$TARGET" 2>/dev/null; then
            xattr -cr "$TARGET" 2>/dev/null
            open "$TARGET"
        else
            osascript -e 'display alert "Spostamento non riuscito" message "Trascina manualmente PyPottery Launcher.app nella cartella Applicazioni, poi riaprilo da lì." as critical'
        fi
    else
        osascript -e 'display alert "Impossibile continuare" message "Trascina PyPottery Launcher.app nella cartella Applicazioni, poi riaprilo da lì." as critical'
    fi
    exit 0
fi

RESOURCES="$DIR/../Resources"
PYTHON="$RESOURCES/python/bin/python3"

# Install dependencies if needed (just enough to start the web launcher -
# everything else, including the heavy PyTorch environment, is installed on
# first run from inside the launcher's own "Setup Environment" button)
if ! "$PYTHON" -c "import flask" 2>/dev/null; then
    # Dialog via AppleScript to show activity
    osascript -e 'display notification "Installing dependencies..." with title "PyPottery Launcher"'

    "$PYTHON" -m pip install --upgrade pip --quiet
    "$PYTHON" -m pip install flask psutil --quiet
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

# Check deps (simple check) - just enough to start the web launcher.
# Everything else (the heavy PyTorch environment, the sub-apps themselves) is
# installed on first run from inside the launcher's own "Setup Environment"
# button, exactly as when running from source.
if ! "$PYTHON" -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    "$SCRIPT_DIR/install.sh"
fi

"$PYTHON" -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from launcher.gui import main; main()"
""", encoding='utf-8')
        run_sh.chmod(0o755)

        install_desktop_sh = package_root / "install_desktop.sh"
        install_desktop_sh.write_text("""#!/bin/bash
# Install PyPottery application shortcut for Linux desktop (GNOME, KDE, XFCE)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR_512="$HOME/.local/share/icons/hicolor/512x512/apps"
ICON_DIR_256="$HOME/.local/share/icons/hicolor/256x256/apps"

mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR_512"
mkdir -p "$ICON_DIR_256"

if [ -f "$SCRIPT_DIR/icon_app.png" ]; then
    cp "$SCRIPT_DIR/icon_app.png" "$ICON_DIR_512/pypottery.png"
    cp "$SCRIPT_DIR/icon_app.png" "$ICON_DIR_256/pypottery.png"
fi

cat << EOF > "$DESKTOP_DIR/pypottery.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=PyPottery Launcher
Comment=Digitizing Archaeological Pottery Documentation
Exec="$SCRIPT_DIR/PyPottery.sh"
Icon=pypottery
Terminal=false
Categories=Science;Graphics;
EOF

chmod +x "$DESKTOP_DIR/pypottery.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "✅ PyPottery launcher shortcut created in $DESKTOP_DIR/pypottery.desktop"
""", encoding='utf-8')
        install_desktop_sh.chmod(0o755)

        print("   ✓ Scripts created (including install_desktop.sh)")

    # 5. Zip Package
    print("\n📦 Step 4: Compressing...")
    zip_path = release_dir / f"{package_base_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    # Use subprocess zip for speed and preserving permissions
    subprocess.run(
        ["zip", "-r", "-q", str(zip_path), package_root.name],
        cwd=release_dir,
        check=True
    )

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✅ {platform_name}: {zip_path.name} ({size_mb:.1f} MB)")

    # The .zip stays the canonical artifact (it's what the launcher's own
    # self-updater downloads, see updater.py), but for macOS also build a
    # .dmg - that's the one to hand a colleague, since it prompts the
    # familiar drag-to-Applications install instead of hitting translocation.
    # For Linux, also build a .AppImage - the Linux equivalent of a .dmg.
    if is_macos:
        create_dmg(app_dir, release_dir, package_base_name)
    else:
        create_appimage(package_root, release_dir, package_base_name)


    return zip_path


def create_unix_release(platform_key=None):
    """
    Create Unix release package(s).

    platform_key: a single platform key, a list of platform keys, or None to
    build every platform in PYTHON_STANDALONE_URLS (the historical default,
    relied on by build_all.py). Each platform is built independently - one
    platform failing (e.g. a macOS target built on a non-macOS host, which
    can't run sips/iconutil) does not prevent the others from completing.
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    release_dir = script_dir / "release"

    if platform_key is None:
        platforms_to_build = list(PYTHON_STANDALONE_URLS.keys())
    elif isinstance(platform_key, str):
        platforms_to_build = [platform_key]
    else:
        platforms_to_build = list(platform_key)

    created_packages = []

    for platform_name in platforms_to_build:
        print()
        print("=" * 60)
        print(f"🏗️  Building for: {platform_name}")
        print("=" * 60)

        try:
            zip_path = _build_single_platform(platform_name, release_dir, project_root)
            created_packages.append((platform_name, zip_path))
        except Exception as e:
            print(f"   ❌ Build failed for {platform_name}: {e}")
            import traceback
            traceback.print_exc()
            print(f"   ⏭️  Skipping {platform_name}, continuing with remaining platforms...")
            continue

    return created_packages


def _default_platforms_for_host() -> list:
    """
    Which platform(s) to build when none are specified on the command line -
    just the host OS/arch, since a fully-correct native package (icon included)
    can only be produced on that OS anyway (sips/iconutil are macOS-only).
    Pass --all to force every platform regardless of host.
    """
    if sys.platform == "darwin":
        machine = platform.machine().lower()
        return ["macos-arm64"] if machine in ("arm64", "aarch64") else ["macos-x86_64"]
    if sys.platform.startswith("linux"):
        return ["linux-x86_64"]
    # Unknown host (e.g. Windows - use build_windows_release.py instead) - fall
    # back to building everything rather than guessing wrong.
    return list(PYTHON_STANDALONE_URLS.keys())


def main():
    parser = argparse.ArgumentParser(
        description="Build PyPottery Suite Launcher release packages (macOS/Linux, embedded Python)"
    )
    parser.add_argument(
        "platform", nargs="?", choices=list(PYTHON_STANDALONE_URLS.keys()),
        help="Specific platform to build. Default: auto-detect from the current OS."
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Build every platform regardless of host OS (a macOS package built "
             "on a non-macOS host will be missing its .icns icon)"
    )
    args = parser.parse_args()

    if args.platform:
        platforms = [args.platform]
    elif args.all:
        platforms = list(PYTHON_STANDALONE_URLS.keys())
    else:
        platforms = _default_platforms_for_host()

    print(f"Building: {', '.join(platforms)}")

    try:
        packages = create_unix_release(platforms)
        if packages:
            print("\n🎉 Build(s) complete!")
            for name, path in packages:
                print(f"   • {name}: {path}")
        else:
            print("\n❌ No packages were built successfully.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n❌ Interrupted")


if __name__ == "__main__":
    main()
