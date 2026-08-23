"""
Build Windows Release Package for PyPottery Suite Launcher

Uses WinPython - a complete portable Python distribution with tkinter included.
"""

import os
import re
import sys
import shutil
import zipfile
import urllib.request
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# Configuration - WinPython (portable, complete with tkinter)
PYTHON_VERSION = "3.12.10"
# WinPython "dot" version - minimal but includes tkinter (from latest stable release)
WINPYTHON_URL = "https://github.com/winpython/winpython/releases/download/16.6.20250620final/Winpython64-3.12.10.1dot.zip"

# NSIS script template for the installer .exe. Placeholders (__TOKEN__) are
# substituted rather than using str.format/f-strings, since the template is
# dense with NSIS's own "${VAR}" syntax which would otherwise have to be
# escaped everywhere.
NSIS_TEMPLATE = r"""
!define APPNAME "PyPottery Launcher"
!define COMPANY "lrncrd"
!define VERSION "__VERSION__"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\PyPotteryLauncher"

Name "${APPNAME}"
OutFile "__OUTFILE__"
InstallDir "$LOCALAPPDATA\${APPNAME}"
; Per-user install (no UAC prompt) and, crucially, a directory the app can
; keep writing to at runtime (Python venv, downloaded sub-apps) - unlike
; Program Files, which requires admin rights and would reproduce on Windows
; the same "can't write next to myself" class of bug the macOS build hit.
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"

!define MUI_ABORTWARNING
__MUI_ICON__

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "__SRCDIR__\*.*"

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\PyPottery.bat" "" __SHORTCUT_ICON__
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\PyPottery.bat" "" __SHORTCUT_ICON__
    CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\Uninstall.exe"

    WriteUninstaller "$INSTDIR\Uninstall.exe"

    WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APPNAME}"
    WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
    WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${COMPANY}"
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"
    RMDir /r "$INSTDIR"
    DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
"""


def _read_launcher_version(project_root: Path) -> str:
    """Pull the canonical version string straight out of web_server.py rather
    than hand-duplicating it in the build script, where it would drift."""
    web_server_py = project_root / "launcher" / "web_server.py"
    try:
        content = web_server_py.read_text(encoding="utf-8")
        match = re.search(r'LAUNCHER_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


def build_windows_installer(package_dir: Path, release_dir: Path, version: str) -> Optional[Path]:
    """
    Wrap the portable package_dir into a proper Windows installer .exe (NSIS):
    installs per-user under %LOCALAPPDATA%, adds Start Menu / Desktop
    shortcuts, and registers an uninstaller in Add/Remove Programs - instead
    of "extract this zip and find PyPottery.bat yourself".

    Compiled cross-platform via `makensis` (works from macOS/Linux, no
    Windows machine needed - same tool many CI pipelines use for this).
    Skips gracefully with a warning if `makensis` isn't installed.
    """
    print("\n📦 Step 7: Building installer .exe (NSIS)...")

    makensis = shutil.which("makensis")
    if not makensis:
        print("   ⚠️ 'makensis' not found (install via 'brew install makensis' "
              "or see https://nsis.sourceforge.net/) - skipping installer .exe, "
              "the .zip is still available")
        return None

    out_name = "PyPottery-Launcher-Setup.exe"
    out_path = release_dir / out_name
    icon_path = package_dir / "icon_app.ico"

    nsi_content = NSIS_TEMPLATE
    nsi_content = nsi_content.replace("__VERSION__", version)
    nsi_content = nsi_content.replace("__OUTFILE__", str(out_path))
    nsi_content = nsi_content.replace("__SRCDIR__", str(package_dir))

    if icon_path.exists():
        nsi_content = nsi_content.replace("__MUI_ICON__", f'!define MUI_ICON "{icon_path}"')
        nsi_content = nsi_content.replace("__SHORTCUT_ICON__", f'"$INSTDIR\\icon_app.ico"')
    else:
        nsi_content = nsi_content.replace("__MUI_ICON__", "")
        nsi_content = nsi_content.replace("__SHORTCUT_ICON__", "")

    with tempfile.TemporaryDirectory() as tmpdir:
        nsi_path = Path(tmpdir) / "installer.nsi"
        nsi_path.write_text(nsi_content, encoding="utf-8")

        result = subprocess.run(
            [makensis, str(nsi_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("   ⚠️ NSIS compilation failed, skipping installer .exe:")
            print(f"   {result.stdout}\n{result.stderr}")
            return None

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"   ✓ Created {out_path.name} ({size_mb:.1f} MB)")
    return out_path


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


def create_release_package():
    """Create the release package"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    release_dir = script_dir / "release"
    package_dir = release_dir / "PyPottery-Launcher"
    python_dir = package_dir / "python"
    launcher_dir = package_dir / "launcher"
    
    print("=" * 60)
    print("🏗️  PyPottery Suite Launcher - Windows Release Builder")
    print("=" * 60)
    
    # Clean previous build
    if package_dir.exists():
        print("\n🧹 Cleaning previous build...")
        shutil.rmtree(package_dir)
    
    # Create directories
    release_dir.mkdir(parents=True, exist_ok=True)
    package_dir.mkdir()
    launcher_dir.mkdir()
    
    # 1. Download and extract WinPython
    print(f"\n📦 Step 1: Downloading WinPython {PYTHON_VERSION}...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        winpython_zip = tmpdir / "winpython.zip"
        download_file(WINPYTHON_URL, winpython_zip, f"WinPython {PYTHON_VERSION}")
        
        print("   Extracting WinPython (this may take a moment)...")
        extract_dir = tmpdir / "extracted"
        extract_dir.mkdir()
        
        # Extract the zip file
        with zipfile.ZipFile(winpython_zip, 'r') as zf:
            zf.extractall(extract_dir)
        
        # Find the python folder inside
        # WinPython extracts to WPy64-XXXXX/python/ or WPy64-XXXXX/python-X.X.X.amd64/
        winpython_root = None
        for d in extract_dir.iterdir():
            if d.is_dir() and d.name.startswith("WPy"):
                # Check for both "python" and "python-*" subdirectories
                for subdir in d.iterdir():
                    if subdir.is_dir() and (subdir.name == "python" or subdir.name.startswith("python-")):
                        winpython_root = subdir
                        break
                break
        
        if winpython_root and winpython_root.exists():
            shutil.copytree(winpython_root, python_dir)
            print(f"   ✓ Python extracted from {winpython_root.name}")
        else:
            # Fallback: find python.exe directly
            print("   Trying alternative extraction...")
            for item in extract_dir.rglob("python.exe"):
                print(f"   Found: {item}")
                python_dir_src = item.parent
                shutil.copytree(python_dir_src, python_dir)
                print(f"   ✓ Python extracted")
                break
            else:
                contents = list(extract_dir.rglob("*"))[:20]
                raise Exception(f"Could not find Python in WinPython. First 20 items: {contents}")
    
    # NOTE: We're now outside the tempdir context - Python is in its final location
    python_exe = python_dir / "python.exe"
    
    # 2. Verify tkinter works
    print("\n📦 Step 2: Verifying tkinter...")
    result = subprocess.run(
        [str(python_exe), "-c", "import tkinter; print('OK')"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("   ✓ tkinter works!")
    else:
        print(f"   ⚠️ tkinter test: {result.stderr[:100]}")
    
    # 3. Install additional packages (now Python is in final location)
    print("\n📦 Step 3: Installing launcher dependencies...")
    
    # Force install to this Python's site-packages
    site_packages = python_dir / "Lib" / "site-packages"
    
    packages = ["customtkinter", "pillow", "psutil", "requests", "packaging"]
    for pkg in packages:
        print(f"   Installing {pkg}...", end=" ", flush=True)
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", pkg, 
             "--target", str(site_packages),
             "--upgrade", "--no-warn-script-location"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓")
        else:
            print(f"⚠️ {result.stderr[:80] if result.stderr else 'unknown error'}")
    
    # 4. Copy launcher files
    print("\n📦 Step 4: Copying launcher files...")
    
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
    
    # Copy images
    imgs_src = project_root / "imgs"
    if imgs_src.exists():
        shutil.copytree(imgs_src, package_dir / "imgs")
        print("   ✓ Copied images")

    # Copy icons
    icon_src = project_root / "icon_app.ico"
    if icon_src.exists():
        shutil.copy2(icon_src, package_dir / "icon_app.ico")
        
    icon_png_src = project_root / "icon_app.png"
    if icon_png_src.exists():
        shutil.copy2(icon_png_src, package_dir / "icon_app.png")
    print("   ✓ Copied application icons")
    
    # Copy requirements.txt (needed for environment setup)
    requirements_src = project_root / "requirements.txt"
    if requirements_src.exists():
        shutil.copy2(requirements_src, package_dir / "requirements.txt")
        print("   ✓ Copied requirements.txt")
    
    # 5. Create launcher batch file
    print("\n📦 Step 5: Creating launcher...")
    
    launcher_bat = package_dir / "PyPottery.bat"
    launcher_bat.write_text(r'''@echo off
title PyPottery Suite Launcher
cd /d "%~dp0"
REM Use pythonw.exe for windowless GUI launch, START so this window closes immediately
start "" python\pythonw.exe -c "import sys; sys.path.insert(0, '.'); from launcher.gui import main; main()"
''', encoding='utf-8')
    print("   ✓ Created PyPottery.bat")
    
    # README
    readme = package_dir / "README.txt"
    readme.write_text(r'''
    PyPottery Suite Launcher
    ========================

    QUICK START
    -----------
    Double-click "PyPottery.bat" to launch!

    REQUIREMENTS
    ------------
    - Windows 10/11 (64-bit)
    - Internet connection (for app downloads)
    - 8GB RAM minimum

    More info: https://github.com/lrncrd/PyPottery
''', encoding='utf-8')
    print("   ✓ Created README.txt")
    
    # 6. Create zip
    print("\n📦 Step 6: Creating distribution package...")

    version = _read_launcher_version(project_root)
    zip_name = f"PyPottery-Launcher-Windows-v{version}"
    zip_path = release_dir / f"{zip_name}.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in package_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(release_dir)
                zf.write(file_path, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)

    # 7. Installer .exe (NSIS) - the one to actually hand out; the zip above
    # stays around too since it's what the launcher's self-updater consumes.
    installer_path = build_windows_installer(package_dir, release_dir, version)

    print("\n" + "=" * 60)
    print("✅ BUILD COMPLETE!")
    print("=" * 60)
    print(f"\n📁 Zip: {zip_path} ({size_mb:.1f} MB)")
    if installer_path:
        installer_size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"📁 Installer: {installer_path} ({installer_size_mb:.1f} MB)")
        print(f"\n💡 Hand out the .exe - it installs with a normal setup wizard "
              f"(Start Menu shortcut, uninstaller). The .zip is the portable "
              f"fallback/self-update artifact.")
    else:
        print(f"\n💡 Users extract the zip and run PyPottery.bat "
              f"(installer .exe was skipped - see warning above)")

    return installer_path or zip_path


if __name__ == "__main__":
    try:
        create_release_package()
    except KeyboardInterrupt:
        print("\n\n❌ Build cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
