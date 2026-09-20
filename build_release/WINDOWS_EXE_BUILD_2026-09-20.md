# Windows builds, 2026-09-20 (beta channel)

Notes on the launcher packages built on 2026-09-20 to test the `beta` branches of the
five sub-apps through the real launcher, and on how to rebuild them.

## What was built

Two independent Windows packages were built, three files in total, all with the beta channel:

| Package | File (in `build_release/release/`) | Size | SHA-256 |
|---|---|---|---|
| **Installer (NSIS)**, the one to hand out | `PyPottery-Launcher-Setup.exe` | 27.9 MB | `a676a93e3178618a884ddb043669cb1740917fe5ed2be4881daf2750a24d7255` |
| WinPython portable zip (what the installer wraps; also the launcher's self-update artifact) | `PyPottery-Launcher-Windows-v1.1.0.zip` | 43.1 MB | `faf344f3a62d29f5616282f615e75e5a0141e85256f51f0b713dcb94766731b3` |
| **PyInstaller exe** (`PyPottery.exe`, `--onedir`) | `PyPottery-Launcher-Windows-EXE-v1.1.0.zip` | 52.9 MB | `43913b6b3980854e45f1f927e9d3f484dc586d6a9423bce90a2e6c3ab6cc8c79` |

Common to all three: launcher version 1.1.0 (`LAUNCHER_VERSION` in `launcher/web_server.py`, not
bumped); source = the working tree on top of `bd27627` (root `beta`, the beta-channel commit)
**plus** the uncommitted change to `launcher/config/apps.json` (shorter app descriptions), which is
bundled; Python 3.12.10; for the exe, PyInstaller 6.22.3, Flask 3.1.3, psutil 7.2.2, Werkzeug 3.1.8
in a clean venv (16 packages in total).

- The **installer** installs the WinPython package per user under `%LOCALAPPDATA%`, with Start Menu /
  Desktop shortcuts and an uninstaller. The launcher there runs as Python source
  (`PyPottery.bat` starts `python\pythonw.exe` with `from launcher.gui import main`), not as a frozen exe.
- The **PyInstaller zip** holds `PyPottery.exe`, `_internal/`, `python_runtime/` (portable Python used to
  create the sub-apps' venv), `imgs/`, icons and `README.txt`. No installer: extract and double-click.
- `makensis.exe` is installed in `C:\Program Files (x86)\NSIS` but **not on PATH**, so the build script
  reports it as missing and skips the installer. Put that folder on PATH for the run (this build did).

The previous versions of the three files (built 2026-09-11, without the beta channel) were moved to
`release/previous/*.old-build.*`. `build_release/release/` is gitignored, so none of this is in git.

## Two things that matter when rebuilding

1. **Build the PyInstaller exe from a clean venv** (only `flask`, `psutil`, `pyinstaller`), never from the
   conda/dev environment. A mixed environment can make PyInstaller pick a mismatched
   `libssl`/`libcrypto` pair, and then every https download inside the exe (vendor assets, update checks,
   sub-app downloads) fails **silently**. See the docstring of `build_windows_release.py`.
2. **Do not build the PyInstaller exe with `launcher/dev_config.py` present if it says
   `DEVELOPER_MODE = True`.** The file is gitignored but `web_server.py` imports it
   (`from .dev_config import DEVELOPER_MODE`), so PyInstaller bundles it and the exe starts in
   Developer Mode: it runs the checkouts at the repo root and does **not** install or update anything,
   so the beta channel would do nothing. This build was made from a staging copy of the repo without that
   file. (The WinPython package/installer step already skips `dev_config.py` by itself.)

## How it was built

From PowerShell (paths as on this machine; adapt `$repo`):

```powershell
$repo  = 'C:\Users\larth\Documents\PyPottery'
$stage = "$env:TEMP\pypottery_build"; $src = "$stage\src"

# 1. staging copy of what the build reads, WITHOUT dev_config.py
robocopy "$repo\launcher" "$src\launcher" /E /XD __pycache__ graphify-out logs /XF dev_config.py *.pyc
robocopy "$repo\imgs" "$src\imgs" /E
robocopy "$repo\build_release" "$src\build_release" build_windows_release.py
Copy-Item "$repo\icon_app.ico","$repo\icon_app.png","$repo\requirements.txt" $src

# 2. clean venv
python -m venv "$stage\venv"
& "$stage\venv\Scripts\python.exe" -m pip install flask psutil pyinstaller

# 3. build both packages (NSIS on PATH so the installer is produced)
$env:PATH = "C:\Program Files (x86)\NSIS;$env:PATH"
cd "$src\build_release"
& "$stage\venv\Scripts\python.exe" -c "import build_windows_release as b; from pathlib import Path; r=Path('..').resolve(); rel=r/'build_release'/'release'; b.create_winpython_package(r, rel); b.create_pyinstaller_package(r, rel)"
```

The files end up in `$src\build_release\release\`. The WinPython step downloads WinPython (~2 minutes),
the PyInstaller step downloads it again for its `python_runtime/`.

If you script this in Windows PowerShell 5.1, run step 3 through `cmd /c "... > log 2>&1"`: PyInstaller
writes its progress to stderr and `$ErrorActionPreference = 'Stop'` turns that into a fatal error (this
happened once in this session).

The usual way, `python build_windows_release.py` from a clean venv, builds the same two packages; it
needs NSIS on PATH and `launcher/dev_config.py` moved out of the way (or set to `False`) for the exe.

## Checks done

**Installer and WinPython zip:** built without errors. Verified only by inspecting the zip: the bundled
`launcher/app_manager.py` contains the beta channel and there is no `dev_config.py` (only
`dev_config.example.py`). **The installer was not run** (it writes to the registry and `%LOCALAPPDATA%`),
and the WinPython launcher was not started.

**PyInstaller exe:** extracted the zip to a temp folder, put `channel.txt` (`beta`) next to
`PyPottery.exe` and started it on port 5987:

- `/api/state` answers, `launcher_version` 1.1.0, **`developer_mode` false**.
- The log has `Beta channel: sub-apps are installed from their beta branch, not from releases`.
- No `dev_config` file anywhere in the package; no traceback and no ssl error in `launcher.log`.

**Not checked on any package:** installing a sub-app from the real GitHub `beta` branches, launching one,
the browser UI of the packaged launcher, `Setup Environment` (PyTorch download). That is the test to do
now. The beta channel itself was tested only against a fake GitHub (`refs/heads/beta.zip` URL, recorded
version `X.Y.Z-beta`, no release "update" offered on top of it).

## How to test the beta apps

1. Exe zip: extract it somewhere writable (e.g. `C:\PyPottery-beta\`). Installer: run it and note the
   install folder (default under `%LOCALAPPDATA%`). Use a **fresh folder**: an older install in the same
   place keeps its `apps/` and its env.
2. Next to `PyPottery.exe` (or `PyPottery.bat` for the installer), create `channel.txt` containing `beta`
   (`Set-Content channel.txt beta -Encoding ascii`), or set `PYPOTTERY_CHANNEL=beta` before starting.
   The launcher log (`logs\launcher.log`, first lines) shows the "Base path" and, when active, the
   "Beta channel" warning.
   **Quit the launcher completely before creating the file** (Task Manager: end every `PyPottery.exe`).
   Starting the exe a second time does not start a new launcher: it only reopens the running one
   ("Another instance is already running" in the log), which has already read the channel. In the builds
   of 2026-09-20 the channel is read once at startup, so an app installed by a launcher that was
   already open before `channel.txt` existed comes from the release, not from `beta`; uninstall it and
   install again after a full restart. From the next build on, the channel is re-read at every install.
3. Start it, **Setup Environment** (first run), then **Install** each app. Installed apps show a version
   such as `0.3.2-beta`; if one shows a plain version, the channel was not active when it was installed.
4. Launch each app and go through the fixes of 2026-09-20 (see `PUBLICATION.md`, "Fixes from the manual
   test round"): Lens (YOLO listed under AI models, zone labels Z1/Z2, Select tool `V` and Ctrl+Z), Ink
   (Open Output Folder in Batch, many images in the batch preview), Scan (gap between the OCR boxes,
   remove a parsed field, collapsed examples, unsaved-line warning), Trace (Export/Delete gap, status text
   under Generate SVG, black symmetry/diameter lines).
5. To go back to releases: delete `channel.txt` (or the variable) and reinstall the apps; a beta install is
   never replaced by "update" on its own.

Once the beta apps are verified, merge to `main` one app at a time (each push to `main` auto-releases):
back up `main` as a branch first, merge `beta`, push, wait for the release. The five app `beta` branches
are already on GitHub; the root `beta` is not (the remote is at `9ba88c7`).

## macOS (from a checkout, no packaged build)

There is no packaged macOS build with the beta channel: the macOS/Linux packages cannot be
cross-built from Windows (`PUBLICATION.md`). To test on a Mac, run the launcher from a checkout of the
root `beta` branch (after pushing it) with the channel on:

```bash
git clone -b beta https://github.com/lrncrd/PyPottery.git && cd PyPottery
PYPOTTERY_CHANNEL=beta ./launch_pypottery.sh     # or: PYPOTTERY_CHANNEL=beta python3 install.py
```

A fresh clone has no `launcher/dev_config.py`, so it is not in Developer Mode and it installs the apps
into `apps/` from their `beta` branches. Without the root `beta` pushed, a Mac would get the old
launcher, which has no beta channel.

## Leftovers

- Temp files of these builds: `%TEMP%\pypottery_build\` (staging copy, venv, `smoke\` test extraction
  with a `channel.txt`), safe to delete.
- The exe and the installer are not code-signed: Windows SmartScreen will warn on first run.
