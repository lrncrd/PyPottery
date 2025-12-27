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
from launcher.updater import LauncherUpdater

# Try to import PIL for image loading
try:
    if sys.platform == "darwin":
        # Disable PIL on macOS to avoid crash with embedded Python
        # The launcher will fall back to using emojis defined in app config
        HAS_PIL = False
    else:
        from PIL import Image, ImageTk
        HAS_PIL = True
except ImportError:
    HAS_PIL = False


class Theme:
    """Application visual theme configuration"""
    # Colors are (Light Mode, Dark Mode)
    
    # Backgrounds
    BG_MAIN = ("#f8fafc", "#0f172a")      # Window background
    BG_CARD = ("#ffffff", "#1e293b")      # Card/Panel background
    BG_HOVER = ("#f1f5f9", "#334155")     # Hover states
    BG_HEADER = ("#f1f5f9", "#1e293b")    # Header backgrounds
    
    # Text
    TEXT_MAIN = ("#1f2937", "#f8fafc")    # Primary text
    TEXT_DIM = ("#6b7280", "#94a3b8")     # Secondary text
    
    # Borders
    BORDER = ("#e5e7eb", "#334155")
    
    # Brand/Status
    PRIMARY = ("#667eea", "#6366f1")
    PRIMARY_HOVER = ("#5a6fd6", "#4f46e5")
    
    SUCCESS = ("#10b981", "#22c55e")
    SUCCESS_HOVER = ("#059669", "#16a34a")
    
    DANGER = ("#ef4444", "#ef4444")
    DANGER_HOVER = ("#dc2626", "#b91c1c")
    
    WARNING = ("#f59e0b", "#f59e0b")
    
    # Console
    CONSOLE_BG = ("#1e1e2e", "#020617")
    CONSOLE_FG = ("#cdd6f4", "#e2e8f0")


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
        
        # Content - Adaptive theme
        self.configure(fg_color=Theme.BG_MAIN)
        
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
            text_color=Theme.TEXT_MAIN,
            anchor="w"
        ).pack(fill="x")
        
        self.status_label = ctk.CTkLabel(
            title_frame,
            text="Preparing download...",
            font=("Segoe UI", 11),
            text_color=Theme.TEXT_DIM,
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
            progress_color=Theme.PRIMARY
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)
        
        # Progress details
        self.details_label = ctk.CTkLabel(
            progress_frame,
            text="0%",
            font=("Segoe UI", 10),
            text_color=Theme.TEXT_DIM
        )
        self.details_label.pack(pady=(6, 0))
        
        # Close button (disabled during download)
        self.cancel_btn = ctk.CTkButton(
            self,
            text="Close",
            width=100,
            corner_radius=8,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
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
            self.progress_bar.configure(progress_color=Theme.SUCCESS)  # Green
            self.status_label.configure(text="✅ " + progress.message, text_color=Theme.SUCCESS)
            self.details_label.configure(text="100% - Complete!")
            self._is_complete = True
            self.cancel_btn.configure(state="normal", text="Close")
        
        elif progress.stage == "error":
            self.progress_bar.configure(progress_color=Theme.DANGER)  # Red
            self.status_label.configure(text="❌ " + progress.message, text_color=Theme.DANGER)
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
    """Modern collapsible console output widget"""
    
    def __init__(self, master, height=200, **kwargs):
        super().__init__(master, **kwargs)
        
        self.expanded_height = height
        self.collapsed_height = 40
        self.is_expanded = False
        
        self.configure(
            corner_radius=12,
            fg_color=Theme.BG_CARD,
            border_width=1,
            border_color=Theme.BORDER
        )
        
        # Header (Always visible)
        self.header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, height=40)
        self.header.pack(fill="x", padx=1, pady=1)
        self.header.pack_propagate(False)
        
        # Status indicator dot
        self.status_dot = ctk.CTkLabel(
            self.header,
            text="●",
            font=("Segoe UI", 14),
            text_color=Theme.TEXT_DIM
        )
        self.status_dot.pack(side="left", padx=(12, 6))
        
        # Latest log message in header (for collapsed view)
        self.last_msg_label = ctk.CTkLabel(
            self.header,
            text="Ready",
            font=("Segoe UI", 11),
            text_color=Theme.TEXT_DIM,
            anchor="w"
        )
        self.last_msg_label.pack(side="left", fill="x", expand=True)
        
        # Toggle button
        self.toggle_btn = ctk.CTkButton(
            self.header,
            text="Show Logs",
            width=80,
            height=24,
            corner_radius=6,
            font=("Segoe UI", 11),
            fg_color=Theme.BG_HOVER,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT_MAIN,
            command=self.toggle
        )
        self.toggle_btn.pack(side="right", padx=12)
        
        # Clear button
        self._clear_btn = ctk.CTkButton(
            self.header,
            text="Clear",
            width=50,
            height=24,
            corner_radius=6,
            font=("Segoe UI", 11),
            fg_color="transparent",
            hover_color=Theme.BG_HOVER,
            text_color=Theme.TEXT_DIM,
            command=self.clear
        )
        self._clear_btn.pack(side="right", padx=(0, 4))
        
        # Text area container (Collapsible)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Don't pack initially (start collapsed)
        
        # Text area
        self._textbox = ctk.CTkTextbox(
            self.content_frame,
            height=height - 50,
            corner_radius=0,
            fg_color=Theme.CONSOLE_BG,
            text_color=Theme.CONSOLE_FG,
            font=("JetBrains Mono", 11) if self._font_exists("JetBrains Mono") else ("Consolas", 11),
            border_width=0
        )
        self._textbox.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self._textbox.configure(state="disabled")

    def toggle(self):
        """Toggle console expansion"""
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.configure(text="Show Logs")
            self.configure(height=self.collapsed_height)
        else:
            self.content_frame.pack(fill="both", expand=True)
            self.toggle_btn.configure(text="Hide Logs")
            
        self.is_expanded = not self.is_expanded
        
    def _font_exists(self, font_name: str) -> bool:
        """Check if a font exists"""
        try:
            import tkinter.font as tkfont
            return font_name.lower() in [f.lower() for f in tkfont.families()]
        except:
            return False
    
    def log(self, message: str, tag: str = "info"):
        """Add message to console"""
        self._textbox.configure(state="normal")
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        prefix_map = {
            "info": ("•", "#89b4fa"),
            "success": ("✓", "#a6e3a1"),
            "error": ("✗", "#f38ba8"),
            "warning": ("▲", "#f9e2af"),
            "progress": ("○", "#cba6f7")
        }
        prefix, color = prefix_map.get(tag, ("•", "#cdd6f4"))
        
        # Update header preview
        self.last_msg_label.configure(text=f"{prefix} {message}")
        
        # Flash status dot
        if tag == "error":
            self.status_dot.configure(text_color=Theme.DANGER)
        elif tag == "success":
            self.status_dot.configure(text_color=Theme.SUCCESS)
        elif tag == "warning":
            self.status_dot.configure(text_color=Theme.WARNING)
        else:
            self.status_dot.configure(text_color=Theme.PRIMARY)
            
        full_msg = f"[{timestamp}] {prefix} {message}\n"
        self._textbox.insert("end", full_msg)
        self._textbox.see("end")
        self._textbox.configure(state="disabled")
    
    def clear(self):
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
        self.last_msg_label.configure(text="Console cleared")


class AppCard(ctk.CTkFrame):
    """Refined App Card with Smart Action Button"""
    
    def __init__(self, master, app_info: AppInfo, launcher: "PyPotteryLauncher", **kwargs):
        super().__init__(master, **kwargs)
        self.app_info = app_info
        self.launcher = launcher
        
        self.configure(
            corner_radius=16,
            fg_color=Theme.BG_CARD,
            border_width=1,
            border_color=Theme.BORDER
        )
        
        # Main layout: Icon | Content | Actions
        
        # 1. Icon Section
        icon_frame = ctk.CTkFrame(self, fg_color="transparent")
        icon_frame.pack(side="left", padx=20, pady=20)
        
        logo_image = self._load_logo_with_aspect_ratio(app_info.logo_path, launcher.base_path, max_size=56)
        if logo_image:
            self.icon_label = ctk.CTkLabel(icon_frame, image=logo_image, text="")
            self._logo_image = logo_image
        else:
            self.icon_label = ctk.CTkLabel(icon_frame, text=app_info.icon, font=("Segoe UI Emoji", 36))
        self.icon_label.pack()
        
        # 2. Content Section
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(side="left", fill="both", expand=True, pady=16)
        
        # Title Row
        title_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        title_row.pack(fill="x")
        
        self.name_label = ctk.CTkLabel(
            title_row,
            text=app_info.name,
            font=("Segoe UI", 18, "bold"),
            text_color=Theme.TEXT_MAIN,
            anchor="w"
        )
        self.name_label.pack(side="left")
        
        # Status Badge (Small, pill shaped)
        self.status_badge = ctk.CTkLabel(
            title_row,
            text="Off",
            font=("Segoe UI", 10, "bold"),
            text_color=Theme.TEXT_DIM,
            fg_color=Theme.BG_HOVER,
            corner_radius=10,
            padx=8
        )
        self.status_badge.pack(side="left", padx=10)
        
        # Description
        self.desc_label = ctk.CTkLabel(
            content_frame,
            text=app_info.description,
            font=("Segoe UI", 12),
            text_color=Theme.TEXT_DIM,
            anchor="w"
        )
        self.desc_label.pack(fill="x", pady=(2, 8))
        
        # Metadata Row
        meta_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        meta_frame.pack(fill="x")
        
        # Helper for meta tags
        def add_tag(parent, icon, text):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", padx=(0, 12))
            ctk.CTkLabel(f, text=icon, font=("Segoe UI Emoji", 10)).pack(side="left", padx=(0,4))
            ctk.CTkLabel(f, text=text, font=("Segoe UI", 11), text_color=Theme.TEXT_DIM).pack(side="left")
            
        add_tag(meta_frame, "🔌", f"Port {app_info.port}")
        add_tag(meta_frame, "💾", f"{app_info.min_ram_gb}GB")
        if app_info.requires_gpu:
            add_tag(meta_frame, "⚡", "GPU")
            
        # Version
        self.version_label = ctk.CTkLabel(
            meta_frame,
            text="",
            font=("Segoe UI", 11),
            text_color=Theme.TEXT_DIM
        )
        self.version_label.pack(side="left", padx=12)
        
        # 3. Action Section
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(side="right", padx=20, fill="y", pady=16)
        
        # Smart Primary Button (Install / Launch / Stop)
        self.main_action_btn = ctk.CTkButton(
            action_frame,
            text="Install",
            width=120,
            height=38,
            corner_radius=19,
            font=("Segoe UI", 13, "bold"),
            command=self._on_smart_action
        )
        self.main_action_btn.pack(pady=(0, 8))
        
        # Secondary actions row
        sec_actions = ctk.CTkFrame(action_frame, fg_color="transparent")
        sec_actions.pack()
        
        self.update_btn = ctk.CTkButton(
            sec_actions,
            text="⬆",
            width=32,
            height=32,
            corner_radius=8,
            fg_color=Theme.WARNING,
            hover_color=Theme.WARNING,
            command=self._on_update
        )
        # Packed only when needed
        
        self.folder_btn = ctk.CTkButton(
            sec_actions,
            text="📂",
            width=32,
            height=32,
            corner_radius=8,
            fg_color=Theme.BG_HOVER,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT_MAIN,
            command=self._on_open_folder
        )
        self.folder_btn.pack(side="right")
        
        self.update_ui()

    def update_ui(self):
        app = self.app_info
        
        # Update Status Badge & Main Button
        if app.is_running:
            self.status_badge.configure(text="RUNNING", text_color=Theme.SUCCESS, fg_color=Theme.BG_HOVER)
            self.main_action_btn.configure(
                text="Stop",
                fg_color=Theme.DANGER, 
                hover_color=Theme.DANGER_HOVER,
                state="normal"
            )
        elif app.installed:
            self.status_badge.configure(text="READY", text_color=Theme.PRIMARY, fg_color=Theme.BG_HOVER)
            self.main_action_btn.configure(
                text="Launch",
                fg_color=Theme.SUCCESS,
                hover_color=Theme.SUCCESS_HOVER,
                state="normal"
            )
            self.folder_btn.configure(state="normal")
        else:
            self.status_badge.configure(text="NOT INSTALLED", text_color=Theme.TEXT_DIM, fg_color=Theme.BG_HOVER)
            self.main_action_btn.configure(
                text="Install",
                fg_color=Theme.PRIMARY,
                hover_color=Theme.PRIMARY_HOVER,
                state="normal"
            )
            self.folder_btn.configure(state="disabled")

        # Update Version Info
        if app.installed_version:
            v_text = f"v{app.installed_version}"
            if app.update_available:
                self.update_btn.pack(side="right", padx=4)
                v_text += " • Update Available"
            else:
                self.update_btn.pack_forget()
            self.version_label.configure(text=v_text)
        else:
            self.version_label.configure(text="")
            self.update_btn.pack_forget()

    def _on_smart_action(self):
        if self.app_info.is_running:
            self.launcher.stop_app(self.app_info.id)
        elif self.app_info.installed:
            self.launcher.launch_app(self.app_info.id)
        else:
            self.launcher.install_app(self.app_info.id)

    # ... Include helper methods ...
    def _load_logo_with_aspect_ratio(self, logo_path: Optional[str], base_path: Path, max_size: int = 64) -> Optional[ctk.CTkImage]:
        if not logo_path or not HAS_PIL: return None
        full_path = base_path / logo_path
        if not full_path.exists(): return None
        try:
            img = Image.open(full_path)
            orig_width, orig_height = img.size
            ratio = min(max_size / orig_width, max_size / orig_height)
            return ctk.CTkImage(light_image=img, dark_image=img, size=(int(orig_width * ratio), int(orig_height * ratio)))
        except: return None

    def _on_update(self): self.launcher.update_app(self.app_info.id)
    def _on_open_folder(self): self.launcher.open_app_folder(self.app_info.id)


class HardwarePanel(ctk.CTkFrame):
    """Panel displaying hardware information"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.configure(
            corner_radius=12,
            fg_color=Theme.BG_CARD,
            border_width=1,
            border_color=Theme.BORDER
        )
        
        # Header
        ctk.CTkLabel(
            self,
            text="💻 System Information",
            font=("Segoe UI", 14, "bold"),
            text_color=Theme.TEXT_MAIN
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
                text_color=Theme.PRIMARY,
                width=70,
                anchor="w"
            ).pack(side="left")
            
            self.labels[key] = ctk.CTkLabel(
                frame,
                text="Detecting...",
                font=("Segoe UI", 11),
                text_color=Theme.TEXT_DIM,
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
        
        self.configure(
            corner_radius=12,
            fg_color=Theme.BG_CARD,
            border_width=1,
            border_color=Theme.BORDER
        )
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkLabel(
            header_frame,
            text="🐍 Python Environment",
            font=("Segoe UI", 14, "bold"),
            text_color=Theme.TEXT_MAIN
        ).pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            header_frame,
            text="Not configured",
            font=("Segoe UI", 11),
            text_color=Theme.TEXT_DIM
        )
        self.status_label.pack(side="right")
        
        # Progress bar with gradient colors
        self.progress_bar = ctk.CTkProgressBar(self, height=8, corner_radius=4, progress_color=Theme.PRIMARY)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 8))
        self.progress_bar.set(0)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 10),
            text_color=Theme.TEXT_DIM
        )
        self.progress_label.pack(padx=15, pady=(0, 8))
        
        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(0, 12))
        
        self.setup_btn = ctk.CTkButton(
            button_frame,
            text="Setup Environment",
            corner_radius=8,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            command=self._on_setup
        )
        self.setup_btn.pack(side="left", padx=(0, 8))
        
        self.verify_btn = ctk.CTkButton(
            button_frame,
            text="Verify",
            width=80,
            corner_radius=8,
            fg_color=Theme.WARNING,
            hover_color=Theme.WARNING,
            command=self._on_verify
        )
        self.verify_btn.pack(side="left")
    
    def update_status(self, installed: bool, message: str = ""):
        """Update environment status"""
        if installed:
            self.status_label.configure(text="✅ Ready", text_color=Theme.SUCCESS)
            self.setup_btn.configure(text="Reinstall")
            self.progress_bar.set(1.0)  # Full bar when configured
        else:
            self.status_label.configure(text="❌ Not configured", text_color=Theme.DANGER)
            self.setup_btn.configure(text="Setup Environment")
            self.progress_bar.set(0)
        
        if message:
            self.progress_label.configure(text=message)
    
    def update_progress(self, progress: InstallProgress):
        """Update progress bar and label"""
        self.progress_bar.set(progress.percent / 100)
        self.progress_label.configure(
            text=progress.message,
            text_color=Theme.DANGER if progress.is_error else Theme.TEXT_DIM
        )
    
    def _on_setup(self):
        self.launcher.setup_environment()
    
    def _on_verify(self):
        self.launcher.verify_environment()


class PyPotteryLauncher(ctk.CTk):
    """Main launcher application window"""
    
    APP_NAME = "PyPottery Suite Launcher"
    VERSION = "1.0.2"
    
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
        
        # Set appearance - System theme
        ctk.set_appearance_mode("system")
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
        self.configure(fg_color=Theme.BG_MAIN)
        
        # Main container with scrolling
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color=Theme.BG_MAIN)
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
            text_color=Theme.TEXT_MAIN
        ).pack(side="left")
        
        # Check Updates button (right side, styled)
        ctk.CTkButton(
            header_frame,
            text="🔄 Check Updates",
            width=140,
            height=36,
            corner_radius=18,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
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
            text_color=Theme.TEXT_MAIN
        ).pack(side="left")
        
        # Apps container
        self.apps_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.apps_frame.pack(fill="x", pady=(0, 15))
        
        # Console (self-contained with header)
        self.console = ConsoleOutput(self.main_frame, height=200)
        self.console.pack(fill="x", pady=(0, 10))
        
        # Footer
        footer = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer.pack(fill="x")
        
        ctk.CTkLabel(
            footer,
            text=f"PyPottery Suite Launcher v{self.VERSION} | github.com/lrncrd",
            font=("Segoe UI", 10),
            text_color=Theme.TEXT_DIM
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
        
        # Check for driver compatibility
        if not self.hardware_info.cuda_compatible and self.hardware_info.driver_warning:
            self.console.log("Incompatible NVIDIA driver detected", "warning")
            # Show warning after a short delay to ensure window is ready
            self.after(500, lambda: messagebox.showwarning(
                "NVIDIA Driver Update Required",
                self.hardware_info.driver_warning
            ))
        
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
    
    def _update_launcher(self, update_info: UpdateInfo):
        """Update the launcher itself"""
        self.console.log(f"Updating launcher to {update_info.latest_version}...", "progress")
        
        # Create dialog
        dialog = DownloadDialog(self, "Launcher Update", "🚀")
        
        def run_update():
            updater = LauncherUpdater(self.base_path)
            
            def progress(msg, percent):
                if dialog.winfo_exists():
                    dialog.update_progress(DownloadProgress(
                        "launcher", "downloading", msg, 0, 0, percent
                    ))
            
            # Download URL is source zip
            # GitHub releases usually provide 'zipball_url' or we construct it
            download_url = f"https://github.com/lrncrd/PyPottery/archive/refs/tags/{update_info.latest_version}.zip"
            
            success = updater.update(download_url, progress)
            
            if success:
                self.after(0, lambda: messagebox.showinfo("Update Complete", "Launcher will now restart."))
                self.after(1000, updater.restart)
            else:
                self.after(0, lambda: self.console.log("Launcher update failed", "error"))
                self.after(0, dialog.destroy)
        
        threading.Thread(target=run_update, daemon=True).start()

    def _on_app_status(self, app_id: str, message: str):
        """Handle status updates from app manager"""
        self.after(0, lambda: self.console.log(f"[{app_id}] {message}", "info"))
        self.after(0, lambda: self._refresh_app_card(app_id))
    
    def _refresh_app_card(self, app_id: str):
        """Refresh a specific app card"""
        if app_id in self.app_cards:
            self.app_cards[app_id].app_info = self.app_manager.apps[app_id]
            self.app_cards[app_id].update_ui()
    
    def _check_updates(self):
        """Check for updates for all apps and the launcher"""
        if not self.app_manager:
            return
            
        self.console.log("Checking for updates...", "info")
        
        # Check Launcher Update First
        try:
            launcher_update = self.update_checker.check_for_update(
                "lrncrd", "PyPottery", self.VERSION
            )
            
            if launcher_update.update_available:
                self.console.log(f"Launcher update available: {launcher_update.latest_version}", "warning")
                if messagebox.askyesno(
                    "Launcher Update Available",
                    f"A new version of PyPottery Launcher ({launcher_update.latest_version}) is available.\n\n"
                    "Do you want to update and restart now?"
                ):
                    self._update_launcher(launcher_update)
                    return  # Stop other checks if updating
        except Exception as e:
            self.console.log(f"Failed to check launcher updates: {e}", "error")

        # Check Apps
        def check_apps_for_updates():
            apps = {}
            for app_id, app_info in self.app_manager.apps.items():
                apps[app_id] = (
                    app_info.repo_owner,
                    app_info.repo_name,
                    app_info.installed_version
                )
            
            results = self.update_checker.check_all_updates(apps)
            self.after(0, lambda: self._on_updates_checked(results))
        
        threading.Thread(target=check_apps_for_updates, daemon=True).start()
    
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
