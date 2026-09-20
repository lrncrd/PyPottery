<p align="center">
  <img src="PyPotteryDocs/logo.png" alt="PyPottery Logo" width="200">
</p>

<h1 align="center">PyPottery</h1>

<p align="center">
  <strong>🏺 Digitizing Archaeological Pottery Documentation</strong>
</p>

<p align="center">
  <a href="https://lrncrd.github.io/PyPottery/">📖 Documentation</a> •
  <a href="#-quick-start">🚀 Quick Start</a> •
  <a href="#-tools">🛠️ Tools</a> •
  <a href="https://ko-fi.com/lrncrd">☕ Support</a>
</p>

<p align="center">
  <a href="https://github.com/lrncrd/PyPottery/releases/latest">
    <img src="https://img.shields.io/github/v/release/lrncrd/PyPottery?label=version&color=blue" alt="Latest Release">
  </a>
  <a href="https://github.com/lrncrd/PyPottery/releases">
    <img src="https://img.shields.io/github/downloads/lrncrd/PyPottery/total?label=downloads&color=success" alt="Total Downloads">
  </a>
  <a href="https://github.com/lrncrd/PyPottery/stargazers">
    <img src="https://img.shields.io/github/stars/lrncrd/PyPottery?color=yellow" alt="GitHub Stars">
  </a>
  <a href="https://github.com/lrncrd/PyPottery/commits">
    <img src="https://img.shields.io/github/last-commit/lrncrd/PyPottery?color=orange" alt="Last Commit">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/License-Apache%202.0-green" alt="Apache 2.0 License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-purple" alt="Platforms">
  <img src="https://img.shields.io/badge/GPU-CUDA%20%7C%20MPS-yellow.svg" alt="GPU support">
</p>

> [!NOTE]
> **Under Review**: The **Trace** and **Scan** tools are currently under review. [Trace Repository](https://github.com/lrncrd/PyPotteryTrace) • [Scan Repository](https://github.com/lrncrd/PyPotteryScan)

---

## 🏺 About

**PyPottery** brings traditional archaeological pottery documentation into the digital age. Each manual step in the classical workflow finds its digital counterpart in our suite of specialized tools.

What takes hours manually can be done in minutes. Process hundreds of drawings with consistent, reproducible results.

### Why PyPottery?

| Feature | Description |
|---------|-------------|
| ⚡ **Save Time** | Process hundreds of drawings in batch mode |
| 🎯 **Consistent Quality** | AI models ensure uniform results across your entire corpus |
| 🔄 **Reproducible** | Every step is documented and shareable |
| 🆓 **Open Source** | Free to use, modify, and extend |

---

## 🛠️ Tools

### PyPotteryInk
<img src="PyPotteryDocs/imgs/LogoInk.png" alt="PyPotteryInk" width="60" align="left">

**AI-powered inking of pottery drawings**

Transform rough pencil sketches into clean, publication-ready ink drawings in seconds. Supports CPU, NVIDIA CUDA, and Apple Silicon (MPS).

- Image inking in seconds
- All hardware compatibility
- Batch processing support
- Pretrained models available

**[📖 Documentation](https://lrncrd.github.io/PyPottery/pypotteryink/)** | **[💾 Repository](https://github.com/lrncrd/PyPotteryInk)**

<br clear="left"/>

---

### PyPotteryLayout
<img src="PyPotteryDocs/imgs/LogoLayout.png" alt="PyPotteryLayout" width="60" align="left">

**Create publication-ready layouts automatically**

Arrange multiple pottery drawings with consistent scaling and professional formatting. Export to PDF and SVG.

- Automatic layout generation
- Consistent scaling system
- Publication-ready exports
- SVG export for further editing

**[📖 Documentation](https://lrncrd.github.io/PyPottery/pypotteryink/)** | **[💾 Repository](https://github.com/lrncrd/PyPotteryLayout)**

<br clear="left"/>

---

### PyPotteryLens
<img src="PyPotteryDocs/imgs/LogoLens.png" alt="PyPotteryLens" width="60" align="left">

**Extract pottery images from PDF documents**

Already have published PDFs? Extract pottery images directly from existing documents using computer vision.

- PDF to image conversion
- Computer vision model application
- Annotation review & editing
- Standardized image export

**[📖 Documentation](https://lrncrd.github.io/PyPottery/pypotterylens/)** | **[💾 Repository](https://github.com/lrncrd/PyPotteryLens)**

<br clear="left"/>

---

## 🚀 Quick Start

### Option 1: PyPottery Suite Launcher (Recommended)

The easiest way to get started! Download the pre-packaged launcher with everything included - **no Python installation required**.

<p align="center">
  <a href="https://github.com/lrncrd/PyPottery/releases/latest">
    <img src="https://img.shields.io/badge/Download-PyPottery%20Launcher-667eea?style=for-the-badge&logoColor=white" alt="Download Launcher">
  </a>
</p>

| Platform | Status | Install |
|----------|--------|---------|
| **Windows 10/11** (64-bit) | ✅ Available | Run `PyPottery-Launcher-Setup.exe` — normal setup wizard, Start Menu shortcut included |
| **macOS** | ✅ Available | Open the `.dmg` and drag PyPottery Launcher into **Applications** |
| **Linux** | 🚧 Coming Soon | — |

**Installation:**
1. Grab the installer for your OS from [Releases](https://github.com/lrncrd/PyPottery/releases/latest)
2. Run it (Windows) or drag-to-Applications (macOS) — no Python install required
3. See [Installation Guide](https://lrncrd.github.io/PyPottery/suite_installation.html) for details

### Option 2: Manual Installation

For advanced users who want more control, each tool can be installed separately. See the [Installation Guide](https://lrncrd.github.io/PyPottery/suite_installation.html) for detailed instructions.

---

## 📋 Requirements

- **Python 3.12** (for manual installation)
- **Operating System:** Windows 10/11 or macOS (Linux coming soon)
- **RAM:** 8 GB minimum, 16 GB recommended
- **GPU:** Optional but recommended (NVIDIA CUDA or Apple Silicon)

---

## 📖 Documentation

Full documentation is available at **[lrncrd.github.io/PyPottery](https://lrncrd.github.io/PyPottery/)**

- [Getting Started](https://lrncrd.github.io/PyPottery/suite_installation.html)
- [PyPotteryInk Guide](https://lrncrd.github.io/PyPottery/pypotteryink/)
- [PyPotteryLayout Guide](https://lrncrd.github.io/PyPottery/pypotterylayout/)
- [PyPotteryLens Guide](https://lrncrd.github.io/PyPottery/pypotterylens/)

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

- 🐛 Report bugs via [Issues](https://github.com/lrncrd/PyPottery/issues)
- 💡 Suggest features
- 🔧 Submit pull requests

---

## 📧 Contact

**Lorenzo Cardarelli**  
📧 [lorenzo.cardarelli@uniroma1.it](mailto:lorenzo.cardarelli@uniroma1.it)

Interested in research collaboration or custom model training? [Get in touch!](https://lrncrd.github.io/PyPottery/contact.html)

---

## ☕ Support This Project

If you find PyPottery useful for your research, consider supporting its development:

<p align="center">
  <a href="https://ko-fi.com/lrncrd">
    <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support on Ko-fi">
  </a>
</p>

Your support helps maintain and improve this open-source tool for the archaeological community! 🙏

---



<p align="center">
  <sub>© 2025 Lorenzo Cardarelli</sub>
</p>
