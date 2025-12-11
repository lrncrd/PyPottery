"""
PyPottery Suite Launcher - Main GUI Application
CustomTkinter-based interface for managing PyPottery applications
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
import json
import sys
import os
from pathlib import Path
from typing import Optional, Dict
import webbrowser

# Add launcher to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher.hardware_detector import detect_hardware, get_hardware_summary, HardwareInfo
from launcher.environment_manager import EnvironmentManager, InstallProgress
from launcher.app_manager import AppManager, AppInfo, DownloadProgress
from launcher.update_checker import UpdateChecker, UpdateInfo

# Try to import PIL for image loading
try:
    if sys.platform == "darwin":
        # Disable PIL on macOS to avoid crash with embedded Python
        # The launcher will fall back to using emojis defined in app config
        HAS_PIL = False
    else:
        from PIL import Image
        HAS_PIL = True
except ImportError:
    HAS_PIL = False


def load_app_logo(logo_path: Optional[str], base_path: Path, size: tuple = (48, 48)) -> Optional[ctk.CTkImage]:
    """Load app logo as CTkImage, returns None if not available"""
    if not logo_path or not HAS_PIL:
        return None
    
    full_path = base_path / logo_path
    if not full_path.exists():
        return None
    
    try:
        img = Image.open(full_path)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


class DownloadDialog(ctk.CTkToplevel):
    """Modal dialog for showing download progress"""
    
    def __init__(self, master, app_name: str, app_icon: str = "📦"):
        super().__init__(master)
        
        self.title(f"Downloading {app_name}")
        self.geometry("480x210")
        self.resizable(False, False)
        
        # Make modal
        self.transient(master)
        if sys.platform != "darwin":
            self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 480) // 2
        y = master.winfo_y() + (master.winfo_height() - 210) // 2
        self.geometry(f"+{x}+{y}")
        
        # Content - Light theme
        self.configure(fg_color="#f8fafc")
        
        # Header with icon
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(24, 12))
        
        ctk.CTkLabel(
            header_frame,
            text=app_icon,
            font=("Segoe UI Emoji", 36)
        ).pack(side="left", padx=(0, 16))
        
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            title_frame,
            text=f"Installing {app_name}",
            font=("Segoe UI", 17, "bold"),
            text_color="#1f2937",
            anchor="w"
        ).pack(fill="x")
        
        self.status_label = ctk.CTkLabel(
            title_frame,
            text="Preparing download...",
            font=("Segoe UI", 11),
            text_color="#6b7280",
            anchor="w"
        )
        self.status_label.pack(fill="x")
        
        # Progress bar with gradient color
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=24, pady=16)
        
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame, 
            height=12, 
            corner_radius=6,
            progress_color="#667eea"
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)
        
        # Progress details
        self.details_label = ctk.CTkLabel(
            progress_frame,
            text="0%",
            font=("Segoe UI", 10),
            text_color="#9ca3af"
        )
        self.details_label.pack(pady=(6, 0))
        
        # Close button (disabled during download)
        self.cancel_btn = ctk.CTkButton(
            self,
            text="Close",
            width=100,
            corner_radius=8,
            fg_color="#667eea",
            hover_color="#5a6fd6",
            state="disabled",
            command=self._on_close
        )
        self.cancel_btn.pack(pady=(4, 24))
        
        self._is_complete = False
        self._is_error = False
        
        # Prevent closing during download
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
    
    def update_progress(self, progress: DownloadProgress):
        """Update the dialog with download progress"""
        self.status_label.configure(text=progress.message)
        
        if progress.stage == "downloading":
            if progress.bytes_total > 0:
                self.progress_bar.set(progress.percent / 100)
                self.details_label.configure(
                    text=f"{progress.percent:.1f}% - {progress.bytes_downloaded / 1024 / 1024:.1f} MB / {progress.bytes_total / 1024 / 1024:.1f} MB"
                )
            else:
                # Indeterminate - use animation
                self.progress_bar.set(0.5)
                self.details_label.configure(text=f"{progress.bytes_downloaded / 1024 / 1024:.1f} MB downloaded")
        
        elif progress.stage == "extracting":
            if progress.bytes_total > 0:
                self.progress_bar.set(progress.percent / 100)
                self.details_label.configure(text=f"Extracting: {progress.bytes_downloaded}/{progress.bytes_total} files")
            else:
                self.progress_bar.set(0.9)
                self.details_label.configure(text="Extracting files...")
        
        elif progress.stage == "complete":
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color="#10b981")  # Green
            self.status_label.configure(text="✅ " + progress.message, text_color="#10b981")
            self.details_label.configure(text="100% - Complete!")
            self._is_complete = True
            self.cancel_btn.configure(state="normal", text="Close")
        
        elif progress.stage == "error":
            self.progress_bar.configure(progress_color="#ef4444")  # Red
            self.status_label.configure(text="❌ " + progress.message, text_color="#ef4444")
            self.details_label.configure(text="Installation failed")
            self._is_error = True
            self.cancel_btn.configure(state="normal", text="Close")
    
    def _on_close_attempt(self):
        """Handle window close attempt"""
        if self._is_complete or self._is_error:
            self.destroy()
        # Otherwise ignore - don't allow closing during download
    
    def _on_close(self):
        """Handle close button click"""
        self.destroy()


class ConsoleOutput(ctk.CTkFrame):
    """Modern styled console output widget"""
    
    def __init__(self, master, height=150, **kwargs):
        super().__init__(master, **kwargs)
        
        self.configure(
            corner_radius=12,
            fg_color="white",
            border_width=1,
            border_color="#e5e7eb"
        )
        
        # Header with gradient-like styling
        header = ctk.CTkFrame(self, fg_color="#f1f5f9", corner_radius=0, height=32)
        header.pack(fill="x", padx=1, pady=(1, 0))
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="● Console",
            font=("Segoe UI", 11, "bold"),
            text_color="#667eea"
        ).pack(side="left", padx=12, pady=4)
        
        # Clear button in header
        self._clear_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=50,
            height=22,
            corner_radius=6,
            font=("Segoe UI", 10),
            fg_color="#e5e7eb",
            hover_color="#d1d5db",
            text_color="#374151",
            command=self.clear
        )
        self._clear_btn.pack(side="right", padx=8, pady=4)
        
        # Text area with modern font
        self._textbox = ctk.CTkTextbox(
            self,
            height=height - 32,
            corner_radius=0,
            fg_color="#1e1e2e",  # Dark background for contrast
            text_color="#cdd6f4",  # Light text
            font=("JetBrains Mono", 11) if self._font_exists("JetBrains Mono") else ("Cascadia Code", 11) if self._font_exists("Cascadia Code") else ("Consolas", 11),
            border_width=0,
            scrollbar_button_color="#45475a",
            scrollbar_button_hover_color="#585b70"
        )
        self._textbox.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self._textbox.configure(state="disabled")
    
    def _font_exists(self, font_name: str) -> bool:
        """Check if a font exists"""
        try:
            import tkinter.font as tkfont
            return font_name.lower() in [f.lower() for f in tkfont.families()]
        except:
            return False
    
    def log(self, message: str, tag: str = "info"):
        """Add message to console with colored prefix"""
        self._textbox.configure(state="normal")
        
        # Add timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color-coded prefixes
        prefix_map = {
            "info": ("•", "#89b4fa"),      # Blue
            "success": ("✓", "#a6e3a1"),   # Green
            "error": ("✗", "#f38ba8"),     # Red
            "warning": ("▲", "#f9e2af"),   # Yellow
            "progress": ("○", "#cba6f7")   # Purple
        }
        prefix, _ = prefix_map.get(tag, ("•", "#cdd6f4"))
        
        self._textbox.insert("end", f"[{timestamp}] {prefix} {message}\n")
        self._textbox.see("end")
        self._textbox.configure(state="disabled")
    
    def clear(self):
        """Clear console"""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")


class AppCard(ctk.CTkFrame):
    """Card widget for displaying an application"""
    
    def __init__(self, master, app_info: AppInfo, launcher: "PyPotteryLauncher", **kwargs):
        super().__init__(master, **kwargs)
        self.app_info = app_info
        self.launcher = launcher
        
        self.configure(corner_radius=12, fg_color="white", border_width=1, border_color="#e5e7eb")
        
        # Header row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(12, 8))
        
        # Try to load logo image with proper aspect ratio
        logo_image = self._load_logo_with_aspect_ratio(app_info.logo_path, launcher.base_path, max_size=64)
        
        if logo_image:
            self.icon_label = ctk.CTkLabel(
                header_frame, 
                image=logo_image,
                text=""
            )
            self._logo_image = logo_image  # Keep reference to prevent garbage collection
        else:
            self.icon_label = ctk.CTkLabel(
                header_frame, 
                text=app_info.icon,
                font=("Segoe UI Emoji", 32)
            )
        self.icon_label.pack(side="left", padx=(0, 12))
        
        name_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        name_frame.pack(side="left", fill="x", expand=True)
        
        self.name_label = ctk.CTkLabel(
            name_frame,
            text=app_info.name,
            font=("Segoe UI", 16, "bold"),
            text_color="#1f2937",
            anchor="w"
        )
        self.name_label.pack(fill="x")
        
        self.desc_label = ctk.CTkLabel(
            name_frame,
            text=app_info.description[:60] + "..." if len(app_info.description) > 60 else app_info.description,
            font=("Segoe UI", 11),
            text_color="#6b7280",
            anchor="w"
        )
        self.desc_label.pack(fill="x")
        
        # Status badge
        self.status_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        self.status_frame.pack(side="right")
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Not installed",
            font=("Segoe UI", 10),
            corner_radius=6,
            fg_color="#e5e7eb",
            text_color="#6b7280",
            padx=10,
            pady=3
        )
        self.status_label.pack()
        
        # Info row
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=15, pady=5)
        
        port_text = f"Port: {app_info.port}"
        ram_text = f"RAM: {app_info.min_ram_gb}GB min"
        gpu_text = "GPU required" if app_info.requires_gpu else "CPU OK"
        
        ctk.CTkLabel(info_frame, text=port_text, font=("Segoe UI", 10), text_color="#9ca3af").pack(side="left", padx=(0, 15))
        ctk.CTkLabel(info_frame, text=ram_text, font=("Segoe UI", 10), text_color="#9ca3af").pack(side="left", padx=(0, 15))
        ctk.CTkLabel(info_frame, text=gpu_text, font=("Segoe UI", 10), text_color="#9ca3af").pack(side="left")
        
        # Version info
        self.version_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=("Segoe UI", 10),
            text_color="#9ca3af"
        )
        self.version_label.pack(side="right")
        
        # Buttons row
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(5, 12))
        
        self.install_btn = ctk.CTkButton(
            button_frame,
            text="Install",
            width=100,
            corner_radius=8,
            fg_color="#667eea",
            hover_color="#5a6fd6",
            command=self._on_install
        )
        self.install_btn.pack(side="left", padx=(0, 6))
        
        self.launch_btn = ctk.CTkButton(
            button_frame,
            text="Launch",
            width=100,
            corner_radius=8,
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_launch
        )
        self.launch_btn.pack(side="left", padx=(0, 6))
        
        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="Stop",
            width=80,
            corner_radius=8,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._on_stop
        )
        self.stop_btn.pack(side="left", padx=(0, 6))
        
        self.update_btn = ctk.CTkButton(
            button_frame,
            text="Update",
            width=80,
            corner_radius=8,
            fg_color="#f59e0b",
            hover_color="#d97706",
            command=self._on_update
        )
        self.update_btn.pack(side="left")
        
        # Folder button
        self.folder_btn = ctk.CTkButton(
            button_frame,
            text="📁",
            width=40,
            corner_radius=8,
            fg_color="#e5e7eb",
            hover_color="#d1d5db",
            text_color="#374151",
            command=self._on_open_folder
        )
        self.folder_btn.pack(side="right")
        
        # Initial state
        self.update_ui()
    
    def _load_logo_with_aspect_ratio(self, logo_path: Optional[str], base_path: Path, max_size: int = 64) -> Optional[ctk.CTkImage]:
        """Load logo maintaining aspect ratio"""
        if not logo_path or not HAS_PIL:
            return None
        
        full_path = base_path / logo_path
        if not full_path.exists():
            return None
        
        try:
            img = Image.open(full_path)
            # Calculate size maintaining aspect ratio
            orig_width, orig_height = img.size
            ratio = min(max_size / orig_width, max_size / orig_height)
            new_width = int(orig_width * ratio)
            new_height = int(orig_height * ratio)
            return ctk.CTkImage(light_image=img, dark_image=img, size=(new_width, new_height))
        except Exception:
            return None
    
    def update_ui(self):
        """Update UI based on app state"""
        app = self.app_info
        
        if app.is_running:
            self.status_label.configure(
                text="● Running",
                fg_color="#dcfce7",
                text_color="#166534"
            )
            self.launch_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.install_btn.configure(state="disabled")
        elif app.installed:
            self.status_label.configure(
                text="Installed",
                fg_color="#dbeafe",
                text_color="#1e40af"
            )
            self.launch_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.install_btn.configure(text="Reinstall")
        else:
            self.status_label.configure(
                text="Not installed",
                fg_color="#e5e7eb",
                text_color="#6b7280"
            )
            self.launch_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self.install_btn.configure(text="Install", state="normal")
        
        # Version info
        if app.installed_version:
            version_text = f"v{app.installed_version}"
            if app.update_available and app.latest_version:
                version_text += f" → v{app.latest_version}"
                self.update_btn.configure(state="normal")
            else:
                self.update_btn.configure(state="disabled")
            self.version_label.configure(text=version_text)
        else:
            self.version_label.configure(text="")
            self.update_btn.configure(state="disabled")
        
        # Folder button
        self.folder_btn.configure(state="normal" if app.installed else "disabled")
    
    def _on_install(self):
        self.launcher.install_app(self.app_info.id)
    
    def _on_launch(self):
        self.launcher.launch_app(self.app_info.id)
    
    def _on_stop(self):
        self.launcher.stop_app(self.app_info.id)
    
    def _on_update(self):
        self.launcher.update_app(self.app_info.id)
    
    def _on_open_folder(self):
        self.launcher.open_app_folder(self.app_info.id)


class HardwarePanel(ctk.CTkFrame):
    """Panel displaying hardware information"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.configure(corner_radius=12, fg_color="white", border_width=1, border_color="#e5e7eb")
        
        # Header
        ctk.CTkLabel(
            self,
            text="💻 System Information",
            font=("Segoe UI", 14, "bold"),
            text_color="#374151"
        ).pack(padx=15, pady=(12, 8), anchor="w")
        
        # Info container
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        
        self.labels: Dict[str, ctk.CTkLabel] = {}
        
        label_names = {
            "os": "OS",
            "cpu": "CPU", 
            "ram": "RAM",
            "gpu": "GPU",
            "pytorch": "PyTorch"
        }
        
        for key in ["os", "cpu", "ram", "gpu", "pytorch"]:
            frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            
            ctk.CTkLabel(
                frame,
                text=label_names[key] + ":",
                font=("Segoe UI", 11, "bold"),
                text_color="#667eea",
                width=70,
                anchor="w"
            ).pack(side="left")
            
            self.labels[key] = ctk.CTkLabel(
                frame,
                text="Detecting...",
                font=("Segoe UI", 11),
                text_color="#4b5563",
                anchor="w"
            )
            self.labels[key].pack(side="left", fill="x", expand=True)
    
    def update_info(self, hw_info: HardwareInfo):
        """Update displayed hardware info"""
        self.labels["os"].configure(text=f"{hw_info.os_name} ({hw_info.architecture})")
        self.labels["cpu"].configure(text=f"{hw_info.cpu_name[:40]}... ({hw_info.cpu_cores} cores)")
        self.labels["ram"].configure(text=f"{hw_info.ram_total_gb:.1f} GB total, {hw_info.ram_available_gb:.1f} GB free")
        
        if hw_info.cuda_available and hw_info.gpus:
            gpu_text = f"✅ {hw_info.gpus[0].name} (CUDA {hw_info.cuda_version})"
        elif hw_info.mps_available:
            gpu_text = "✅ Apple Silicon (MPS)"
        elif hw_info.rocm_available:
            gpu_text = "✅ AMD GPU (ROCm)"
        else:
            gpu_text = "❌ CPU only"
        
        self.labels["gpu"].configure(text=gpu_text)
        self.labels["pytorch"].configure(text=f"Recommended: {hw_info.recommended_pytorch_variant}")


class EnvironmentPanel(ctk.CTkFrame):
    """Panel for environment setup"""
    
    def __init__(self, master, launcher: "PyPotteryLauncher", **kwargs):
        super().__init__(master, **kwargs)
        self.launcher = launcher
        
        self.configure(corner_radius=12, fg_color="white", border_width=1, border_color="#e5e7eb")
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkLabel(
            header_frame,
            text="🐍 Python Environment",
            font=("Segoe UI", 14, "bold"),
            text_color="#374151"
        ).pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            header_frame,
            text="Not configured",
            font=("Segoe UI", 11),
            text_color="#6b7280"
        )
        self.status_label.pack(side="right")
        
        # Progress bar with gradient colors
        self.progress_bar = ctk.CTkProgressBar(self, height=8, corner_radius=4, progress_color="#667eea")
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 8))
        self.progress_bar.set(0)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 10),
            text_color="#6b7280"
        )
        self.progress_label.pack(padx=15, pady=(0, 8))
        
        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(0, 12))
        
        self.setup_btn = ctk.CTkButton(
            button_frame,
            text="Setup Environment",
            corner_radius=8,
            fg_color="#667eea",
            hover_color="#5a6fd6",
            command=self._on_setup
        )
        self.setup_btn.pack(side="left", padx=(0, 8))
        
        self.verify_btn = ctk.CTkButton(
            button_frame,
            text="Verify",
            width=80,
            corner_radius=8,
            fg_color="#764ba2",
            hover_color="#6b4190",
            command=self._on_verify
        )
        self.verify_btn.pack(side="left")
    
    def update_status(self, installed: bool, message: str = ""):
        """Update environment status"""
        if installed:
            self.status_label.configure(text="✅ Ready", text_color="#10b981")
            self.setup_btn.configure(text="Reinstall")
            self.progress_bar.set(1.0)  # Full bar when configured
        else:
            self.status_label.configure(text="❌ Not configured", text_color="#ef4444")
            self.setup_btn.configure(text="Setup Environment")
            self.progress_bar.set(0)
        
        if message:
            self.progress_label.configure(text=message)
    
    def update_progress(self, progress: InstallProgress):
        """Update progress bar and label"""
        self.progress_bar.set(progress.percent / 100)
        self.progress_label.configure(
            text=progress.message,
            text_color="red" if progress.is_error else "gray50"
        )
    
    def _on_setup(self):
        self.launcher.setup_environment()
    
    def _on_verify(self):
        self.launcher.verify_environment()


class PyPotteryLauncher(ctk.CTk):
    """Main launcher application window"""
    
    APP_NAME = "PyPottery Suite Launcher"
    VERSION = "1.0.1"
    
    # Color palette
    GRADIENT_START = "#667eea"
    GRADIENT_END = "#764ba2"
    PRIMARY_COLOR = "#667eea"
    PRIMARY_HOVER = "#5a6fd6"
    SUCCESS_COLOR = "#10b981"
    SUCCESS_HOVER = "#059669"
    DANGER_COLOR = "#ef4444"
    DANGER_HOVER = "#dc2626"
    WARNING_COLOR = "#f59e0b"
    WARNING_HOVER = "#d97706"
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title(f"{self.APP_NAME} v{self.VERSION}")
        self.geometry("950x750")
        self.minsize(850, 650)
        
        # Set appearance - Light theme only
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # Base paths
        self.base_path = Path(__file__).parent.parent
        self.requirements_file = self.base_path / "requirements.txt"
        
        # Set window icon
        self._set_window_icon()
        
        # Managers (initialized after hardware detection)
        self.hardware_info: Optional[HardwareInfo] = None
        self.env_manager: Optional[EnvironmentManager] = None
        self.app_manager: Optional[AppManager] = None
        self.update_checker = UpdateChecker()
        
        # App cards
        self.app_cards: Dict[str, AppCard] = {}
        
        # Monitoring timer ID
        self._monitor_timer = None
        
        # Build UI
        self._build_ui()
        
        # Initialize in background
        self.after(100, self._initialize)
    
    def _set_window_icon(self):
        """Set the window icon"""
        icon_path = self.base_path / "icon_app.ico"
        if icon_path.exists():
            try:
                # For Windows, use iconbitmap
                if sys.platform == "win32":
                    self.iconbitmap(str(icon_path))
                else:
                    # For macOS/Linux, try to set icon via PhotoImage
                    # CustomTkinter handles this differently, we use standard Tk
                    icon_png = self.base_path / "icon_app.png"
                    if icon_png.exists():
                        try:
                            # Use standard PhotoImage (supports PNG in Tk 8.6+)
                            img = tk.PhotoImage(file=str(icon_png))
                            self.wm_iconphoto(True, img)
                        except Exception:
                            pass
            except Exception:
                pass  # Ignore icon errors
    
    def _start_app_monitoring(self):
        """Start periodic monitoring of running apps"""
        def check_apps():
            if self.app_manager:
                for app_id in list(self.app_manager._processes.keys()):
                    status = self.app_manager.get_app_status(app_id)
                    if not status.is_running:
                        # App stopped - update UI
                        if app_id in self.app_manager.apps:
                            self.app_manager.apps[app_id].is_running = False
                        self._refresh_app_card(app_id)
                        self.console.log(f"{self.app_manager.apps[app_id].name} has stopped", "info")
            
            # Schedule next check
            self._monitor_timer = self.after(3000, check_apps)  # Check every 3 seconds
        
        # Start monitoring
        self._monitor_timer = self.after(3000, check_apps)
    
    def _stop_app_monitoring(self):
        """Stop app monitoring"""
        if self._monitor_timer:
            self.after_cancel(self._monitor_timer)
            self._monitor_timer = None
    
    def _build_ui(self):
        """Build the main UI"""
        # Configure main window background
        self.configure(fg_color="#f8fafc")
        
        # Main container with scrolling
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="#f8fafc")
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header with centered logo
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        # Center container for logo and title
        center_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        center_container.pack(expand=True)
        
        # Load main logo
        self.main_logo = None
        logo_path = self.base_path / "imgs" / "Logo.png"
        if logo_path.exists() and HAS_PIL:
            try:
                img = Image.open(logo_path)
                self.main_logo = ctk.CTkImage(light_image=img, dark_image=img, size=(60, 60))
            except Exception:
                pass
        
        if self.main_logo:
            ctk.CTkLabel(
                center_container,
                image=self.main_logo,
                text=""
            ).pack(side="left", padx=(0, 12))
        
        ctk.CTkLabel(
            center_container,
            text="PyPottery Suite",
            font=("Segoe UI", 26, "bold"),
            text_color="#1f2937"
        ).pack(side="left")
        
        # Check Updates button (right side, styled)
        ctk.CTkButton(
            header_frame,
            text="🔄 Check Updates",
            width=140,
            height=36,
            corner_radius=18,
            fg_color=self.PRIMARY_COLOR,
            hover_color=self.PRIMARY_HOVER,
            command=self._check_updates
        ).pack(side="right", padx=5)
        
        # Hardware panel
        self.hardware_panel = HardwarePanel(self.main_frame)
        self.hardware_panel.pack(fill="x", pady=(0, 10))
        
        # Environment panel
        self.env_panel = EnvironmentPanel(self.main_frame, self)
        self.env_panel.pack(fill="x", pady=(0, 10))
        
        # Apps section header
        apps_header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        apps_header.pack(fill="x", pady=(15, 8))
        
        ctk.CTkLabel(
            apps_header,
            text="📦 Applications",
            font=("Segoe UI", 16, "bold"),
            text_color="#374151"
        ).pack(side="left")
        
        # Apps container
        self.apps_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.apps_frame.pack(fill="x", pady=(0, 15))
        
        # Console (self-contained with header)
        self.console = ConsoleOutput(self.main_frame, height=180)
        self.console.pack(fill="x", pady=(0, 10))
        
        # Footer
        footer = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer.pack(fill="x")
        
        ctk.CTkLabel(
            footer,
            text=f"PyPottery Suite Launcher v{self.VERSION} | github.com/lrncrd",
            font=("Segoe UI", 10),
            text_color="#9ca3af"
        ).pack(side="left")
    
    def _initialize(self):
        """Initialize managers and detect hardware"""
        self.console.log("Initializing PyPottery Suite Launcher...", "info")
        
        # Detect hardware in background
        def detect():
            self.hardware_info = detect_hardware()
            self.after(0, self._on_hardware_detected)
        
        threading.Thread(target=detect, daemon=True).start()
    
    def _on_hardware_detected(self):
        """Called when hardware detection completes"""
        self.console.log("Hardware detection complete", "success")
        self.hardware_panel.update_info(self.hardware_info)
        
        # Initialize environment manager
        self.env_manager = EnvironmentManager(self.base_path)
        self.env_manager.set_progress_callback(self._on_env_progress)
        
        # Check if environment exists
        if self.env_manager.venv_exists():
            self.env_panel.update_status(True, "Environment ready")
            self.console.log("Python environment found", "success")
            self.console.log(f"Using Python: {self.env_manager.python_executable}", "info")
            
            # Initialize app manager with venv Python
            self.app_manager = AppManager(
                self.base_path,
                self.env_manager.python_executable
            )
        else:
            self.env_panel.update_status(False, "Environment not set up")
            self.console.log("Python environment not found - please run Setup", "warning")
            
            # Initialize with system Python temporarily
            self.app_manager = AppManager(
                self.base_path,
                Path(sys.executable)
            )
        
        # Set app manager callback
        self.app_manager.set_status_callback(self._on_app_status)
        
        # Create app cards
        self._create_app_cards()
        
        # Start monitoring running apps
        self._start_app_monitoring()
        
        # Check for updates
        self._check_updates()
    
    def _create_app_cards(self):
        """Create cards for each application"""
        for app_info in self.app_manager.get_app_list():
            card = AppCard(self.apps_frame, app_info, self)
            card.pack(fill="x", pady=5)
            self.app_cards[app_info.id] = card
    
    def _on_env_progress(self, progress: InstallProgress):
        """Handle environment installation progress"""
        self.after(0, lambda: self.env_panel.update_progress(progress))
        self.after(0, lambda: self.console.log(progress.message, "error" if progress.is_error else "progress"))
    
    def _on_app_status(self, app_id: str, message: str):
        """Handle app status updates"""
        self.after(0, lambda: self.console.log(f"[{app_id}] {message}", "info"))
        self.after(0, lambda: self._refresh_app_card(app_id))
    
    def _refresh_app_card(self, app_id: str):
        """Refresh a specific app card"""
        if app_id in self.app_cards:
            self.app_cards[app_id].app_info = self.app_manager.apps[app_id]
            self.app_cards[app_id].update_ui()
    
    def _check_updates(self):
        """Check for updates from GitHub"""
        self.console.log("Checking for updates...", "info")
        
        def check():
            apps = {}
            for app_id, app_info in self.app_manager.apps.items():
                apps[app_id] = (
                    app_info.repo_owner,
                    app_info.repo_name,
                    app_info.installed_version
                )
            
            results = self.update_checker.check_all_updates(apps)
            self.after(0, lambda: self._on_updates_checked(results))
        
        threading.Thread(target=check, daemon=True).start()
    
    def _on_updates_checked(self, results: Dict[str, UpdateInfo]):
        """Handle update check results"""
        updates_available = 0
        
        for app_id, update_info in results.items():
            if app_id in self.app_manager.apps:
                app = self.app_manager.apps[app_id]
                app.latest_version = update_info.latest_version
                app.update_available = update_info.update_available
                
                if update_info.update_available:
                    updates_available += 1
                    self.console.log(
                        f"{app.name}: Update available v{update_info.latest_version}",
                        "warning"
                    )
                
                self._refresh_app_card(app_id)
        
        if updates_available == 0:
            self.console.log("All applications are up to date", "success")
        else:
            self.console.log(f"{updates_available} update(s) available", "warning")
    
    # === Public Actions ===
    
    def setup_environment(self):
        """Set up Python virtual environment"""
        if not self.requirements_file.exists():
            self.console.log(f"Requirements file not found: {self.requirements_file}", "error")
            return
        
        self.console.log("Starting environment setup...", "info")
        
        def setup():
            success = self.env_manager.full_install(
                self.hardware_info,
                self.requirements_file
            )
            self.after(0, lambda: self._on_setup_complete(success))
        
        threading.Thread(target=setup, daemon=True).start()
    
    def _on_setup_complete(self, success: bool):
        """Handle environment setup completion"""
        if success:
            self.console.log("Environment setup complete!", "success")
            self.env_panel.update_status(True, "Ready")
            
            # Update app manager to use venv Python
            self.app_manager = AppManager(
                self.base_path,
                self.env_manager.python_executable
            )
            self.app_manager.set_status_callback(self._on_app_status)
        else:
            self.console.log("Environment setup failed", "error")
            self.env_panel.update_status(False, "Setup failed")
    
    def verify_environment(self):
        """Verify PyTorch installation"""
        if not self.env_manager or not self.env_manager.venv_exists():
            self.console.log("Environment not set up", "error")
            return
        
        self.console.log("Verifying PyTorch installation...", "info")
        
        def verify():
            success, message = self.env_manager.verify_pytorch_installation()
            self.after(0, lambda: self._on_verify_complete(success, message))
        
        threading.Thread(target=verify, daemon=True).start()
    
    def _on_verify_complete(self, success: bool, message: str):
        """Handle verification completion"""
        if success:
            self.console.log("PyTorch verification passed!", "success")
            for line in message.strip().split("\n"):
                self.console.log(f"  {line}", "info")
        else:
            self.console.log(f"PyTorch verification failed: {message}", "error")
    
    def install_app(self, app_id: str):
        """Install an application with progress dialog"""
        app = self.app_manager.apps.get(app_id)
        if not app:
            return
        
        # Get latest version
        version = app.latest_version if app.latest_version and app.latest_version != "unknown" else None
        
        self.console.log(f"Installing {app.name}...", "info")
        
        # Create download dialog
        dialog = DownloadDialog(self, app.name, app.icon)
        
        def on_progress(progress: DownloadProgress):
            """Handle download progress updates"""
            self.after(0, lambda p=progress: dialog.update_progress(p))
        
        def install():
            # Set progress callback
            old_callback = self.app_manager._download_callback
            self.app_manager.set_download_callback(on_progress)
            
            try:
                success = self.app_manager.download_app(app_id, version)
            finally:
                # Restore old callback
                self.app_manager._download_callback = old_callback
            
            self.after(0, lambda: self._refresh_app_card(app_id))
        
        threading.Thread(target=install, daemon=True).start()
    
    def update_app(self, app_id: str):
        """Update an application with progress dialog"""
        app = self.app_manager.apps.get(app_id)
        if not app or not app.update_available:
            return
        
        self.console.log(f"Updating {app.name} to v{app.latest_version}...", "info")
        
        # Create download dialog
        dialog = DownloadDialog(self, app.name, app.icon)
        
        def on_progress(progress: DownloadProgress):
            """Handle download progress updates"""
            self.after(0, lambda p=progress: dialog.update_progress(p))
        
        def update():
            # Set progress callback
            old_callback = self.app_manager._download_callback
            self.app_manager.set_download_callback(on_progress)
            
            try:
                success = self.app_manager.download_app(app_id, app.latest_version)
                if success:
                    self.after(0, lambda: self.console.log(f"{app.name} updated successfully!", "success"))
            finally:
                # Restore old callback
                self.app_manager._download_callback = old_callback
            
            self.after(0, lambda: self._refresh_app_card(app_id))
        
        threading.Thread(target=update, daemon=True).start()
    
    def launch_app(self, app_id: str):
        """Launch an application"""
        if not self.env_manager or not self.env_manager.venv_exists():
            self.console.log("Please set up environment first", "error")
            return
        
        self.app_manager.launch_app(app_id)
        self._refresh_app_card(app_id)
    
    def stop_app(self, app_id: str):
        """Stop an application"""
        self.app_manager.stop_app(app_id)
        self._refresh_app_card(app_id)
    
    def open_app_folder(self, app_id: str):
        """Open application folder"""
        self.app_manager.open_app_folder(app_id)
    
    def on_closing(self):
        """Handle window close"""
        # Stop monitoring
        self._stop_app_monitoring()
        
        # Stop all running apps
        if self.app_manager:
            # Automatically stop all apps without confirmation
            self.app_manager.stop_all_apps()
        
        self.destroy()


def main():
    """Main entry point"""
    app = PyPotteryLauncher()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
