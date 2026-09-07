"""
Build Windows Release Packages for PyPottery Suite Launcher

Produces two independent artifacts:

1. WinPython package - a portable WinPython distribution + PyPottery.bat,
   optionally wrapped into an installer .exe via NSIS (Start Menu shortcut,
   uninstaller). This is the one to hand out normally.
2. PyInstaller package - the launcher compiled into a native PyPottery.exe
   (--onedir: a folder next to the exe, no temp-extraction on every launch,
   no antivirus false-positive risk that --onefile carries). Smaller, no
   installer, just extract and double-click. Also bundles a copy of the
   same portable Python used by package 1, under python_runtime/ - the
   frozen exe's own sys.executable is PyPottery.exe itself, not a real
   interpreter, so it can't be used to create the pypottery_env venv at
   runtime (see EnvironmentManager._base_python()).

Each is built independently - one failing doesn't stop the other (see main()).

IMPORTANT for the PyInstaller package: run this script with an interpreter
that has only the launcher's runtime deps installed (flask, psutil) - NOT
the project's heavy ML dev env (torch, opencv, etc.). Building from an env
like that doesn't just balloon the output size; a conda environment carrying
multiple packages that each bundle their own OpenSSL DLLs can make
PyInstaller pick a mismatched libssl/libcrypto pair, which breaks
`import ssl` in the frozen exe with a DLL load error - and since that
happens deep in a background thread, it fails *silently* (vendor asset
download, update checks and sub-app downloads all go through https and just
quietly do nothing). Verified experimentally: same code, same PyInstaller
version - broken when built from the project's conda env, fine when built
from a clean `python -m venv`. Create one and run this script with its
python.exe; missing flask/psutil/pyinstaller are auto-installed into it.
The WinPython package is unaffected either way - it downloads its own
portable Python and doesn't use the invoking interpreter for anything.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

# ============================================================================
# Shared
# ============================================================================

APP_NAME = "PyPottery"


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


# ============================================================================
# Package 1: WinPython + NSIS installer
# ============================================================================

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
    WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" '"$INSTDIR\icon_app.ico"'
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
    WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${COMPANY}"
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
    ; Best-effort graceful shutdown of a running instance first - it may hold
    ; files under $INSTDIR open (its own venv/DLLs, a spawned sub-app's own
    ; files), which would otherwise make RMDir /r below leave remnants.
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\stop_running_instance.ps1"'

    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"

    ; A file can be transiently locked at the exact moment RMDir /r reaches
    ; it - antivirus real-time scanning is the usual culprit on Windows -
    ; and NSIS doesn't retry on its own, so a single miss leaves that file
    ; (and its parent directory) behind. Same reasoning as
    ; _rename_with_retry() in app_manager.py; retry a few times.
    StrCpy $0 0
    retry_rmdir:
        RMDir /r "$INSTDIR"
        IfFileExists "$INSTDIR\*.*" 0 rmdir_done
        IntOp $0 $0 + 1
        IntCmp $0 5 rmdir_done retry_wait rmdir_done
        retry_wait:
        Sleep 500
        Goto retry_rmdir
    rmdir_done:

    DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
"""


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
    print("\n📦 Step 6: Building installer .exe (NSIS)...")

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


def _download_portable_python(dest_dir: Path) -> Path:
    """
    Download the portable WinPython distribution and extract just its
    python/ folder - a real, standalone python.exe with the full stdlib,
    none of the embeddable-package's ensurepip/venv quirks - into dest_dir.

    Shared by both Windows packages: the WinPython package uses this as the
    launcher's own interpreter; the PyInstaller package bundles a copy purely
    so the frozen exe has a *real* Python to hand to `venv`/uv when it builds
    the pypottery_env venv at runtime. Its own sys.executable is PyPottery.exe
    itself, not a real interpreter - using that would make `-m venv` just
    relaunch the whole app as a second instance instead of creating a venv
    (see EnvironmentManager._base_python() in environment_manager.py).
    """
    print(f"   Downloading WinPython {PYTHON_VERSION} (portable Python)...")

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
            shutil.copytree(winpython_root, dest_dir)
            print(f"   ✓ Python extracted from {winpython_root.name}")
        else:
            # Fallback: find python.exe directly
            print("   Trying alternative extraction...")
            for item in extract_dir.rglob("python.exe"):
                print(f"   Found: {item}")
                shutil.copytree(item.parent, dest_dir)
                print(f"   ✓ Python extracted")
                break
            else:
                contents = list(extract_dir.rglob("*"))[:20]
                raise Exception(f"Could not find Python in WinPython. First 20 items: {contents}")

    # NOTE: We're now outside the tempdir context - Python is in its final location
    return dest_dir / "python.exe"


def create_winpython_package(project_root: Path, release_dir: Path) -> Path:
    """Build the WinPython portable package (+ NSIS installer if available)."""
    package_dir = release_dir / "PyPottery-Launcher"
    python_dir = package_dir / "python"
    launcher_dir = package_dir / "launcher"

    print("=" * 60)
    print("🏗️  Package 1/2: WinPython + installer")
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
    python_exe = _download_portable_python(python_dir)

    # 2. Install additional packages (now Python is in final location)
    print("\n📦 Step 2: Installing launcher dependencies...")

    # Force install to this Python's site-packages
    site_packages = python_dir / "Lib" / "site-packages"

    # The launcher itself is a Flask app opened in the browser (see gui.py) -
    # werkzeug comes along as flask's dependency. psutil is a soft dependency
    # (hardware_detector.py imports it lazily inside a try/except) - without
    # it the app still runs, it just silently reports fake 8GB/4GB RAM.
    packages = ["flask", "psutil"]
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

    # 3. Copy launcher files
    print("\n📦 Step 3: Copying launcher files...")

    # Ensure offline vendor assets (Bootstrap, Icons, Fonts) are present and synced
    try:
        sys.path.insert(0, str(project_root))
        from launcher.vendor_assets_manager import VendorAssetsManager
        v_mgr = VendorAssetsManager(project_root)
        v_mgr.ensure_vendor_assets()
        v_mgr.sync_to_app(project_root / "launcher")
    except Exception as e:
        print(f"   ⚠️ Vendor assets build warning: {e}")

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

    # 4. Create launcher batch file
    print("\n📦 Step 4: Creating launcher...")

    launcher_bat = package_dir / "PyPottery.bat"
    launcher_bat.write_text(r'''@echo off
title PyPottery Suite Launcher
cd /d "%~dp0"
REM Use pythonw.exe for windowless GUI launch, START so this window closes immediately
start "" python\pythonw.exe -c "import sys; sys.path.insert(0, '.'); from launcher.gui import main; main()"
''', encoding='utf-8')
    print("   ✓ Created PyPottery.bat")

    # Best-effort graceful shutdown helper, invoked by the NSIS uninstaller
    # before it deletes the install directory - a running launcher (or a
    # sub-app it spawned) holds files open under here, which would otherwise
    # make RMDir /r leave partial remnants behind. Reads the same lock-file
    # format written by launcher/instance_lock.py (byte 0 is a locking
    # sentinel, the JSON payload starts at offset 1) and calls the existing
    # /api/shutdown route, which already stops every sub-app and releases the
    # lock (see gui.py's _stop_everything()). Silently does nothing if the
    # launcher isn't running - the uninstall proceeds either way.
    stop_script = package_dir / "stop_running_instance.ps1"
    stop_script.write_text(r'''$ErrorActionPreference = "SilentlyContinue"
$lockFile = Join-Path $PSScriptRoot ".pypottery.lock"
if (Test-Path $lockFile) {
    try {
        $raw = [System.IO.File]::ReadAllText($lockFile)
        if ($raw.Length -gt 1) {
            $info = $raw.Substring(1) | ConvertFrom-Json
            if ($info.port) {
                Invoke-WebRequest -Uri "http://127.0.0.1:$($info.port)/api/shutdown" `
                    -Method Post -TimeoutSec 3 -UseBasicParsing | Out-Null
                Start-Sleep -Milliseconds 1500
            }
        }
    } catch {}
}
''', encoding='utf-8')
    print("   ✓ Created stop_running_instance.ps1")

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

    # 5. Create zip
    print("\n📦 Step 5: Creating distribution package...")

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

    # 6. Installer .exe (NSIS) - the one to actually hand out; the zip above
    # stays around too since it's what the launcher's self-updater consumes.
    installer_path = build_windows_installer(package_dir, release_dir, version)

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


# ============================================================================
# Package 2: PyInstaller standalone exe
# ============================================================================

# Packages PyInstaller would otherwise pull in because hardware_detector.py
# has an optional `try: import torch / except ImportError: pass` (used only
# to enrich GPU info if PyTorch happens to already be importable). None of
# this is a real launcher dependency - it's the heavy ML stack the *sub-apps*
# use, which happens to be installed in a dev env used to run the suite
# itself. Left unexcluded, the onedir build balloons from ~30MB to ~900MB.
EXCLUDED_MODULES = [
    "torch", "torchvision", "torchaudio", "transformers", "cv2", "scipy",
    "pandas", "matplotlib", "bitsandbytes", "sympy", "numpy", "PIL",
    "pygments", "rich", "sam2", "ultralytics", "timm", "accelerate",
    "diffusers", "peft", "safetensors", "tokenizers", "huggingface_hub",
    "polars", "GPUtil", "cairocffi", "cairosvg", "reportlab", "openpyxl",
    "fitz", "seaborn", "skimage", "rectpack", "win32com", "pythoncom",
    "pywintypes", "tensorboard", "IPython", "numba", "llvmlite",
]


def _warn_if_heavy_env():
    """
    Best-effort heads-up, not a hard block: importlib.util.find_spec() only
    checks whether a package is installed, it doesn't import it, so this is
    cheap and side-effect-free. See the module docstring for why building
    from an env like this is a real (and silent) problem, not just bloat.
    """
    import importlib.util
    heavy = [m for m in ("torch", "cv2", "transformers") if importlib.util.find_spec(m)]
    if heavy:
        print(f"   [!] WARNING: this interpreter also has {', '.join(heavy)} installed - "
              f"building from here risks a broken 'import ssl' in the frozen exe "
              f"(silently breaks all https downloads). Prefer a clean venv with "
              f"just flask+psutil+pyinstaller. See this file's module docstring.")


def _ensure_runtime_deps():
    """
    flask is the launcher's hard dependency; psutil is a soft one - only
    ever imported lazily inside hardware_detector.py's try/except blocks, so
    a build without it doesn't crash, it just silently reports fake 8GB/4GB
    RAM and wrong CPU core counts instead of real values. Both need to be
    importable from *this* interpreter so PyInstaller's static analysis
    picks them up.
    """
    print("\n📦 Step 1: Checking runtime dependencies (flask, psutil)...")
    missing = [
        pkg for pkg in ("flask", "psutil")
        if subprocess.run(
            [sys.executable, "-c", f"import {pkg}"], capture_output=True
        ).returncode != 0
    ]
    if not missing:
        print("   ✓ flask and psutil already available")
        return

    print(f"   Installing {', '.join(missing)}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", *missing],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not install {', '.join(missing)}:\n{result.stderr}")
    print(f"   ✓ Installed {', '.join(missing)}")


def _ensure_pyinstaller():
    print("\n📦 Step 2: Checking PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"   ✓ PyInstaller {result.stdout.strip()} available")
        return

    print("   Installing PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "pyinstaller"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not install PyInstaller:\n{result.stderr}")
    print("   ✓ PyInstaller installed")


def _run_pyinstaller(project_root: Path, work_dir: Path) -> Path:
    print("\n📦 Step 3: Building with PyInstaller (--onedir)...")

    dist_path = work_dir / "dist"
    build_path = work_dir / "build"
    spec_path = work_dir

    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--icon", str(project_root / "icon_app.ico"),
        "--add-data", f"{project_root / 'launcher' / 'templates'};launcher/templates",
        "--add-data", f"{project_root / 'launcher' / 'static'};launcher/static",
        "--add-data", f"{project_root / 'launcher' / 'config'};launcher/config",
        "--add-data", f"{project_root / 'requirements.txt'};.",
        "--distpath", str(dist_path),
        "--workpath", str(build_path),
        "--specpath", str(spec_path),
    ]
    for module in EXCLUDED_MODULES:
        args.extend(["--exclude-module", module])
    args.append(str(project_root / "launcher" / "gui.py"))

    result = subprocess.run(args, cwd=project_root)
    if result.returncode != 0:
        raise RuntimeError("PyInstaller build failed - see output above")

    package_dir = dist_path / APP_NAME
    if not package_dir.exists():
        raise RuntimeError(f"Expected output not found: {package_dir}")

    size_mb = sum(f.stat().st_size for f in package_dir.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"   ✓ Built {package_dir.name}/ ({size_mb:.1f} MB)")
    return package_dir


def _copy_base_path_assets(project_root: Path, package_dir: Path):
    """
    Copy imgs/ and the app icons next to PyPottery.exe (package_dir), not
    through --add-data - PyInstaller always extracts --add-data files into
    _internal/, but web_server.py's /assets/<path> route serves them from
    state.base_path, which gui.py resolves to package_dir itself (the folder
    the exe lives in). Bundling them via --add-data would land them in the
    wrong place and 404.
    """
    print("\n📦 Step 4: Copying imgs/ and app icons next to the exe...")

    imgs_src = project_root / "imgs"
    if imgs_src.exists():
        shutil.copytree(imgs_src, package_dir / "imgs", dirs_exist_ok=True)
        print("   ✓ Copied imgs/")

    for icon_name in ("icon_app.ico", "icon_app.png"):
        icon_src = project_root / icon_name
        if icon_src.exists():
            shutil.copy2(icon_src, package_dir / icon_name)
    print("   ✓ Copied application icons")


def _write_exe_readme(package_dir: Path):
    readme = package_dir / "README.txt"
    readme.write_text(r'''
    PyPottery Suite Launcher
    ========================

    QUICK START
    -----------
    Double-click "PyPottery.exe" to launch!
    (Keep the "_internal" and "python_runtime" folders next to it - they
    hold the app's files and the bundled Python used to set up sub-apps'
    environments.)

    REQUIREMENTS
    ------------
    - Windows 10/11 (64-bit)
    - Internet connection (for app downloads)
    - 8GB RAM minimum

    More info: https://github.com/lrncrd/PyPottery
''', encoding='utf-8')
    print("   ✓ Created README.txt")


def create_pyinstaller_package(project_root: Path, release_dir: Path) -> Path:
    """Build the PyInstaller standalone exe package."""
    work_dir = release_dir / "_pyinstaller_work"

    print("=" * 60)
    print("🏗️  Package 2/2: PyInstaller standalone exe")
    print("=" * 60)

    if work_dir.exists():
        print("\n🧹 Cleaning previous build...")
        shutil.rmtree(work_dir)
    release_dir.mkdir(parents=True, exist_ok=True)

    _warn_if_heavy_env()
    _ensure_runtime_deps()
    _ensure_pyinstaller()
    package_dir = _run_pyinstaller(project_root, work_dir)
    _copy_base_path_assets(project_root, package_dir)

    print("\n📦 Step 5: Bundling portable Python runtime (for pypottery_env creation)...")
    _download_portable_python(package_dir / "python_runtime")

    print("\n📦 Step 6: Finalizing package...")
    _write_exe_readme(package_dir)

    version = _read_launcher_version(project_root)
    zip_name = f"PyPottery-Launcher-Windows-EXE-v{version}"
    zip_path = release_dir / f"{zip_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in package_dir.rglob('*'):
            if file_path.is_file():
                arcname = Path(APP_NAME) / file_path.relative_to(package_dir)
                zf.write(file_path, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"   ✓ Created {zip_path.name} ({size_mb:.1f} MB)")

    shutil.rmtree(work_dir)

    print(f"\n📁 Zip: {zip_path} ({size_mb:.1f} MB)")
    print(f"\n💡 Users extract the zip and double-click PyPottery.exe - no "
          f"installer, no separate Python required.")

    return zip_path


# ============================================================================
# Entry point
# ============================================================================

def build_all_windows_packages() -> dict:
    """
    Build both Windows packages, isolating one's failure from the other.
    Returns {name: path} for whichever succeeded (empty dict if both failed).
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    release_dir = script_dir / "release"

    results = {}

    try:
        results["WinPython + installer"] = create_winpython_package(project_root, release_dir)
    except Exception as e:
        print(f"\n❌ WinPython package failed: {e}")
        import traceback
        traceback.print_exc()

    print()

    try:
        results["PyInstaller exe"] = create_pyinstaller_package(project_root, release_dir)
    except Exception as e:
        print(f"\n❌ PyInstaller package failed: {e}")
        import traceback
        traceback.print_exc()

    return results


def main():
    results = build_all_windows_packages()

    print("\n" + "=" * 60)
    if results:
        print("✅ BUILD COMPLETE!")
        print("=" * 60)
        for name, path in results.items():
            print(f"   • {name}: {path}")
    else:
        print("❌ Both packages failed - see errors above")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Build cancelled.")
        sys.exit(1)
