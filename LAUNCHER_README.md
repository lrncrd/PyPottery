# PyPottery Suite

🏺 **AI-powered tools for archaeological pottery analysis**

PyPottery Suite is a unified launcher and management system for three specialized applications:

| Application | Description | Port |
|------------|-------------|------|
| **PyPottery Layout** | Create archaeological artefacts tables/layouts from images | 5005 |
| **PyPottery Lens** | AI-powered pottery documentation with object detection | 5001 |
| **PyPottery Ink** | AI-assisted digital inking of pottery drawings | 5003 |

## Quick Start

### Windows
```batch
launch_pypottery.bat
```

### Linux / macOS
```bash
chmod +x launch_pypottery.sh
./launch_pypottery.sh
```

### Or directly with Python
```bash
python install.py
```

## Requirements

- **Python 3.9+** (3.10+ recommended for best compatibility)
- **RAM**: 8GB minimum, 16GB recommended for AI features
- **GPU** (optional but recommended):
  - NVIDIA: CUDA 11.8+ (GTX 1060 6GB or better)
  - Apple: M1/M2/M3 (Metal Performance Shaders)
  - AMD: ROCm 6.0+ (Linux only)

## Features

### 🖥️ Hardware Detection
- Automatic detection of GPU capabilities (CUDA/MPS/ROCm)
- Smart PyTorch variant selection based on your hardware
- System resource monitoring

### 📦 Application Management
- Download applications directly from GitHub
- Automatic version checking and update notifications
- One-click installation and updates

### 🐍 Environment Management
- Automated Python virtual environment setup
- Correct PyTorch installation for your hardware
- Shared dependencies across all applications

### 🚀 Launch Control
- Start/stop applications with a single click
- Automatic browser opening
- Port conflict detection

## Project Structure

```
PyPottery/
├── install.py              # Bootstrap installer
├── launch_pypottery.bat    # Windows launcher
├── launch_pypottery.sh     # Linux/macOS launcher
├── requirements.txt        # Full dependencies
├── launcher/
│   ├── __init__.py
│   ├── gui.py              # Main GUI application
│   ├── hardware_detector.py
│   ├── environment_manager.py
│   ├── app_manager.py
│   ├── update_checker.py
│   └── config/
│       └── apps.json       # App configurations
└── apps/                   # Downloaded applications
    ├── PyPotteryLayout/
    ├── PyPotteryLens/
    └── PyPotteryInk/
```

## How It Works

1. **Bootstrap**: `install.py` installs minimal dependencies (CustomTkinter, psutil)
2. **Launch**: GUI launcher starts with hardware detection
3. **Setup Environment**: Create venv, install PyTorch (correct variant), install dependencies
4. **Install Apps**: Download from GitHub repositories
5. **Run**: Launch applications with proper environment and settings

## Troubleshooting

### "Python not found"
Make sure Python 3.9+ is installed and in your system PATH.

### "tkinter not found" (Linux)
Install tkinter for your distribution:
```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

### CUDA not detected
1. Ensure NVIDIA drivers are installed
2. Verify with `nvidia-smi` command
3. CUDA toolkit is NOT required (PyTorch includes runtime)

### Port already in use
Another application or a previous instance is using the port. Stop the other application or change the port in `launcher/config/apps.json`.

## Links

- **PyPottery Layout**: https://github.com/lrncrd/PyPotteryLayout
- **PyPottery Lens**: https://github.com/lrncrd/PyPotteryLens  
- **PyPottery Ink**: https://github.com/lrncrd/PyPotteryInk
- **Documentation**: https://lrncrd.github.io/PyPottery/

## License

MIT License - see individual repositories for component licenses.

## Author

Lorenzo Cardarelli ([@lrncrd](https://github.com/lrncrd))
