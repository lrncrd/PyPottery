# PyPottery Release Build Tools

This folder contains scripts to build distributable packages for the PyPottery Suite Launcher.

## Quick Build

```bash
# Build all releases (run from this folder)
python build_all.py
```

## Individual Builds

### Windows Release
```bash
python build_windows_release.py
```
Creates `release/PyPottery-Launcher-Windows-v1.0.0.zip` containing:
- Python 3.12 Embeddable (~15MB)
- Pre-installed launcher dependencies
- Ready-to-run batch file

### Unix (macOS/Linux) Release
```bash
python build_unix_release.py
```
Creates `release/PyPottery-Launcher-Unix-v1.0.0.zip` containing:
- Launcher source files
- Install script (requires Python 3.10+ on user's system)
- Launch script

## Output

After building, you'll find the release packages in the `release/` folder:
- `PyPottery-Launcher-Windows-v1.0.0.zip` (~25-30MB)
- `PyPottery-Launcher-Unix-v1.0.0.zip` (~1MB)

## Distribution

1. Create a new GitHub Release
2. Upload both zip files as release assets
3. Users download the appropriate package for their OS

## How It Works

### Windows Package
- Includes Python 3.12 embeddable (no system Python required!)
- User extracts zip and runs `PyPottery.bat`
- First run: clicks "Setup Environment" to install PyTorch
- Subsequent runs: instant launch

### Unix Package  
- Requires Python 3.10+ installed on system
- User runs `./install.sh` once to set up venv
- Then runs `./pypottery.sh` to launch

## Notes

- Windows release must be built on Windows (downloads Windows-specific Python)
- Unix release can be built on any platform
- Both packages are self-contained after first setup
- PyTorch is downloaded at first run (~2GB) based on user's GPU
