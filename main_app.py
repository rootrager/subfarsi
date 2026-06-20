"""
SubFarsiPro - Modern GUI Application v5.0
Professional CustomTkinter interface for subtitle generation.

Features:
- v5 Engine: Gemini 2.5 Support (RPD Tracking)
- OpenRouter "Free-Only" Shield
- Smart Advanced Retry System (429/500/503)
- Modern dark theme with blue accents
- Success frame with video playback
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image
import threading
import queue
import os
import subprocess
import platform
from datetime import datetime
from typing import Optional
import webbrowser

from core_v4 import SubFarsiCore, ConfigManager, resource_path
from utils.dependency_manager import DependencyManager
from utils.path_manager import get_app_data_dir


class SubFarsiProApp(ctk.CTk):
    """
    Main application window for SubFarsiPro.
    """
    
    def __init__(self):
        super().__init__()
        
        # Configure appearance
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        
        # Window configuration
        self.title("SubFarsiPro v5.0")
        self.geometry("1400x850")
        self.minsize(1200, 700)
        
        # Initialize Config Manager
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Application state
        self.video_path: Optional[str] = None
        self.output_srt_path: Optional[str] = None
        self.core: Optional[SubFarsiCore] = None
        self.processing_thread: Optional[threading.Thread] = None
        self.is_processing = False
        self.setup_frame: Optional[ctk.CTkFrame] = None
        self.install_thread: Optional[threading.Thread] = None
        self.installing_dependencies: bool = False
        
        # Cancellation token for background tasks
        self.cancel_event = threading.Event()
        
        # Queue for thread-safe UI updates
        self.update_queue = queue.Queue()
        
        # Success frame reference
        self.success_frame: Optional[ctk.CTkFrame] = None
        
        # Decide between Setup Wizard and Main UI
        self._init_startup_flow()

    def _center_window(self):
        """Center the window on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def build_main_ui(self):
        """Build the main dashboard UI and start background tasks."""
        self._create_widgets()
        self._process_queue()
        self._center_window()
        
        # Perform startup tasks
        self.after(100, lambda: self._fetch_models(self.provider_var.get()))
        self.after(200, self._update_vram_info)
        self.after(300, self._check_dependencies_on_startup)

    # ==========================
    # Setup Wizard Flow
    # ==========================

    def _init_startup_flow(self):
        """Determine whether to show Setup Wizard or main app."""
        status = DependencyManager.check_status()
        if status.get("ffmpeg") and status.get("ollama"):
            # All good – go directly to main UI
            self.build_main_ui()
        else:
            # Show setup wizard instead of main dashboard
            self._build_setup_frame(status)
            self._process_queue()
            self._center_window()

    def _build_setup_frame(self, status: dict):
        """Create a full-window Setup Wizard for dependencies."""
        self.setup_frame = ctk.CTkFrame(self)
        self.setup_frame.grid(row=0, column=0, rowspan=2, columnspan=3, sticky="nsew", padx=20, pady=20)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self.setup_frame,
            text="SubFarsiPro Setup",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title.grid(row=0, column=0, columnspan=3, pady=(20, 10), padx=30, sticky="n")

        info = ctk.CTkLabel(
            self.setup_frame,
            text="We need to verify and install required components before launching the app.",
            font=ctk.CTkFont(size=13),
            wraplength=600,
            justify="center"
        )
        info.grid(row=1, column=0, columnspan=3, pady=(0, 20), padx=30)

        status_frame = ctk.CTkFrame(self.setup_frame)
        status_frame.grid(row=2, column=0, columnspan=3, pady=(0, 20), padx=40, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self.ffmpeg_status_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=14)
        )
        self.ffmpeg_status_label.grid(row=0, column=0, pady=(10, 5), sticky="w")

        self.ollama_status_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=14)
        )
        self.ollama_status_label.grid(row=1, column=0, pady=(5, 10), sticky="w")

        # Ollama download hint
        ollama_link = ctk.CTkLabel(
            status_frame,
            text="Download Ollama: https://ollama.com",
            font=ctk.CTkFont(size=12, underline=True),
            text_color="lightblue",
            cursor="hand2"
        )
        ollama_link.grid(row=2, column=0, pady=(5, 10), sticky="w")
        ollama_link.bind("<Button-1>", lambda _e: webbrowser.open("https://ollama.com"))

        # Progress bar (hidden until install starts)
        self.setup_progress = ctk.CTkProgressBar(self.setup_frame)
        self.setup_progress.grid(row=3, column=0, columnspan=3, pady=(10, 10), padx=60, sticky="ew")
        self.setup_progress.set(0)
        self.setup_progress.grid_remove()

        # Action buttons frame
        btn_frame = ctk.CTkFrame(self.setup_frame, fg_color="transparent")
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(10, 20))

        self.install_btn = ctk.CTkButton(
            btn_frame,
            text="Install Dependencies",
            command=self.start_installation,
            corner_radius=10,
            fg_color=("#3B8ED0", "#1F6AA5")
        )
        self.install_btn.grid(row=0, column=0, padx=10)

        self.launch_btn = ctk.CTkButton(
            btn_frame,
            text="Launch App",
            command=self._launch_main_ui_from_setup,
            corner_radius=10,
            fg_color=("green", "darkgreen"),
            state="disabled"
        )
        self.launch_btn.grid(row=0, column=1, padx=10)

        self._update_setup_status_labels(status)

    def _update_setup_status_labels(self, status: dict):
        ffmpeg_ok = status.get("ffmpeg", False)
        ollama_ok = status.get("ollama", False)

        self.ffmpeg_status_label.configure(
            text=f"FFmpeg: {'✅ Installed' if ffmpeg_ok else '❌ Missing'}",
            text_color="lightgreen" if ffmpeg_ok else "red"
        )
        self.ollama_status_label.configure(
            text=f"Ollama: {'✅ Ready (localhost:11434)' if ollama_ok else '❌ Not Running on localhost:11434'}",
            text_color="lightgreen" if ollama_ok else "orange"
        )

        # Enable Launch button only when both are OK
        self.launch_btn.configure(state="normal" if (ffmpeg_ok and ollama_ok) else "disabled")

        # Disable Install button if ffmpeg is already present
        if ffmpeg_ok:
            self.install_btn.configure(state="disabled", text="FFmpeg Installed")

    def start_installation(self):
        """Start installing missing dependencies in a background thread."""
        if self.installing_dependencies:
            return
        self.installing_dependencies = True
        self.install_btn.configure(state="disabled")
        self.setup_progress.set(0)
        self.setup_progress.grid()

        self._log_message("🔧 Starting dependency installation...")
        self.install_thread = threading.Thread(
            target=self._install_dependencies_thread,
            daemon=True
        )
        self.install_thread.start()

    def _install_dependencies_thread(self):
        try:
            status = DependencyManager.install_missing(
                progress_callback=self._setup_progress_callback
            )
            self.update_queue.put(("setup_complete", {"status": status}))
        except Exception as e:
            self.update_queue.put(("log", {"message": f"❌ Setup failed: {e}"}))
        finally:
            self.installing_dependencies = False

    def _setup_progress_callback(self, percent: int):
        self.update_queue.put(("setup_progress", {"percent": percent}))

    def _update_setup_progress(self, percent: int):
        # Map 0–100 to 0.0–1.0
        self.setup_progress.set(max(0.0, min(1.0, percent / 100.0)))
        self._update_status(f"Installing FFmpeg... {percent}%", None)

    def _on_setup_complete(self, status: dict):
        self._log_message("✅ Dependency installation finished.")
        self._update_setup_status_labels(status)
        # Hide progress bar once done
        self.setup_progress.grid_remove()

    def _launch_main_ui_from_setup(self):
        """Destroy setup frame and build the main dashboard UI."""
        if self.setup_frame is not None:
            self.setup_frame.destroy()
            self.setup_frame = None
        self.build_main_ui()

    def _create_widgets(self):
        """Create and layout all UI widgets (3-Column Layout)."""
        self.configure(fg_color="#1A1B26")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._create_left_panel()
        self._create_center_panel()
        self._create_right_panel()

    def _create_left_panel(self):
        left_frame = ctk.CTkFrame(self, fg_color="#24283B", corner_radius=12)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Guide label
        guide_label = ctk.CTkLabel(
            left_frame, 
            text="Nexplore Studio Engine.\nSelect a video, configure AI parameters, and monitor processing.",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=14),
            justify="center",
            wraplength=250
        )
        guide_label.grid(row=0, column=0, pady=20, padx=15)
        
        # Log box
        self.log_textbox = ctk.CTkTextbox(
            left_frame, 
            fg_color="#0F0F14", 
            text_color="#00FF00", 
            corner_radius=12,
            font=ctk.CTkFont(size=12, family="monospace")
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        self.log_textbox.configure(state="disabled")
        
        # Log copy button
        copy_btn = ctk.CTkButton(
            left_frame,
            text="Copy Logs",
            command=self._copy_logs_to_clipboard,
            fg_color="#00E5FF",
            text_color="#000000",
            corner_radius=12
        )
        copy_btn.grid(row=2, column=0, pady=(0, 15), padx=15, sticky="ew")

    def _create_center_panel(self):
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        center_frame.grid_columnconfigure(0, weight=1)
        center_frame.grid_rowconfigure(0, weight=1)
        
        # Thumbnail placeholder
        thumb_frame = ctk.CTkFrame(center_frame, fg_color="#24283B", corner_radius=12, height=200)
        thumb_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 15))
        thumb_frame.grid_propagate(False)
        thumb_frame.grid_rowconfigure(0, weight=1)
        thumb_frame.grid_columnconfigure(0, weight=1)
        
        self.video_path_label = ctk.CTkLabel(
            thumb_frame, 
            text="No Video Selected", 
            text_color="#E0E0E0",
            font=ctk.CTkFont(size=16)
        )
        self.video_path_label.grid(row=0, column=0)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            center_frame, 
            progress_color="#00E5FF",
            fg_color="#24283B",
            corner_radius=12,
            height=15
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        self.status_label = ctk.CTkLabel(
            center_frame, 
            text="Ready", 
            text_color="#00E5FF",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.grid(row=2, column=0, pady=(0, 15))
        
        # Buttons
        self.select_video_btn = ctk.CTkButton(
            center_frame,
            text="Select Video File",
            command=self._select_video,
            fg_color="#00E5FF",
            text_color="#000000",
            corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50
        )
        self.select_video_btn.grid(row=3, column=0, sticky="ew", pady=(0, 15))
        
        self.start_btn = ctk.CTkButton(
            center_frame,
            text="Start Processing",
            command=self._start_processing,
            fg_color="#00E5FF",
            text_color="#000000",
            corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            state="disabled"
        )
        self.start_btn.grid(row=4, column=0, sticky="ew", pady=(0, 15))
        
        self.stop_btn = ctk.CTkButton(
            center_frame,
            text="Stop",
            command=self._stop_processing,
            fg_color="#FF6B6B",
            text_color="#000000",
            corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            state="disabled"
        )
        self.stop_btn.grid(row=5, column=0, sticky="ew", pady=(0, 15))
        
        self._create_success_frame(center_frame)

    def _create_success_frame(self, parent):
        self.success_frame = ctk.CTkFrame(parent, fg_color=("#1a4d2e", "#0f2818"), corner_radius=12)
        self.success_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        success_icon = ctk.CTkLabel(self.success_frame, text="✅", font=ctk.CTkFont(size=48))
        success_icon.grid(row=0, column=0, columnspan=3, pady=(20, 10), padx=30)
        
        success_label = ctk.CTkLabel(
            self.success_frame, text="Processing Complete!", font=ctk.CTkFont(size=18, weight="bold"), text_color="lightgreen"
        )
        success_label.grid(row=1, column=0, columnspan=3, pady=(0, 20), padx=30)
        
        play_btn = ctk.CTkButton(
            self.success_frame, text="▶️ Play Video", command=self._play_video,
            fg_color=("#28a745", "#1e7e34"), hover_color=("#218838", "#155724"), corner_radius=12
        )
        play_btn.grid(row=2, column=0, padx=8, pady=(0, 20), sticky="ew")
        
        new_task_btn = ctk.CTkButton(
            self.success_frame, text="🔄 New Task", command=self._new_task,
            fg_color=("#007bff", "#0056b3"), hover_color=("#0069d9", "#004085"), corner_radius=12
        )
        new_task_btn.grid(row=2, column=1, padx=8, pady=(0, 20), sticky="ew")
        
        exit_btn = ctk.CTkButton(
            self.success_frame, text="❌ Exit", command=self._exit_app,
            fg_color=("#dc3545", "#bd2130"), hover_color=("#c82333", "#a71d2a"), corner_radius=12
        )
        exit_btn.grid(row=2, column=2, padx=8, pady=(0, 20), sticky="ew")

    def _create_right_panel(self):
        right_frame = ctk.CTkFrame(self, fg_color="#24283B", corner_radius=12)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=15, pady=15)
        right_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            right_frame, 
            text="AI Configuration", 
            text_color="#00E5FF",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=20, padx=15)
        
        # Whisper Model
        whisper_label = ctk.CTkLabel(right_frame, text="Whisper Model:", text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"))
        whisper_label.grid(row=1, column=0, sticky="w", padx=15)
        
        whisper_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        whisper_frame.grid(row=2, column=0, sticky="ew", padx=15)
        whisper_frame.grid_columnconfigure(0, weight=1)
        
        self.whisper_model_var = ctk.StringVar(value=self._get_config_value("provider_settings", "whisper_model", "small"))
        self.whisper_menu = ctk.CTkOptionMenu(
            whisper_frame,
            values=["tiny", "base", "small", "medium", "large"],
            variable=self.whisper_model_var,
            corner_radius=12,
            fg_color="#1A1B26",
            button_color="#00E5FF",
            button_hover_color="#00B3CC",
            text_color="#FFFFFF",
            command=self._save_whisper_config
        )
        self.whisper_menu.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        auto_select_btn = ctk.CTkButton(
            whisper_frame, text="✨", width=40,
            command=self._auto_select_whisper_model, corner_radius=12,
            fg_color="#00E5FF", text_color="#000000"
        )
        auto_select_btn.grid(row=0, column=1)
        
        whisper_hint = ctk.CTkLabel(right_frame, text="Whisper: Base is recommended for speed", text_color="#E0E0E0", font=ctk.CTkFont(size=11))
        whisper_hint.grid(row=3, column=0, sticky="w", padx=15, pady=(0, 15))
        
        self.vram_info_label = ctk.CTkLabel(right_frame, text="", font=ctk.CTkFont(size=11), text_color="#E0E0E0")
        self.vram_info_label.grid(row=4, column=0, sticky="w", padx=15, pady=(0, 15))
        
        # Translation Provider
        provider_label = ctk.CTkLabel(right_frame, text="Translation Provider:", text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"))
        provider_label.grid(row=5, column=0, sticky="w", padx=15)
        
        self.provider_var = ctk.StringVar(value=self._get_config_value("provider_settings", "last_provider", "ollama"))
        provider_menu = ctk.CTkOptionMenu(
            right_frame,
            values=["ollama", "gemini", "groq", "openrouter", "nvidia"],
            variable=self.provider_var,
            corner_radius=12,
            fg_color="#1A1B26",
            button_color="#00E5FF",
            button_hover_color="#00B3CC",
            text_color="#FFFFFF",
            command=self._on_provider_change
        )
        provider_menu.grid(row=6, column=0, sticky="ew", padx=15)
        
        provider_hint = ctk.CTkLabel(right_frame, text="Select your translation engine", text_color="#E0E0E0", font=ctk.CTkFont(size=11))
        provider_hint.grid(row=7, column=0, sticky="w", padx=15, pady=(0, 15))
        
        # Generic Model Selector
        self.model_label = ctk.CTkLabel(right_frame, text="Model:", text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"))
        self.model_label.grid(row=8, column=0, sticky="w", padx=15)
        
        self.model_var = ctk.StringVar(value="")
        self.model_menu = ctk.CTkOptionMenu(
            right_frame,
            values=["Loading..."],
            variable=self.model_var,
            corner_radius=12,
            fg_color="#1A1B26",
            button_color="#00E5FF",
            button_hover_color="#00B3CC",
            text_color="#FFFFFF",
            state="disabled"
        )
        self.model_menu.grid(row=9, column=0, sticky="ew", padx=15)
        
        model_hint = ctk.CTkLabel(right_frame, text="Select the specific AI model", text_color="#E0E0E0", font=ctk.CTkFont(size=11))
        model_hint.grid(row=10, column=0, sticky="w", padx=15, pady=(0, 15))
        
        # Language Selector
        lang_label = ctk.CTkLabel(right_frame, text="Target Language:", text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"))
        lang_label.grid(row=11, column=0, sticky="w", padx=15)
        
        self.lang_var = ctk.StringVar(value="Persian (Informal Tehrani)")
        lang_menu = ctk.CTkOptionMenu(
            right_frame,
            values=["Persian (Informal Tehrani)"],
            variable=self.lang_var,
            corner_radius=12,
            fg_color="#1A1B26",
            button_color="#00E5FF",
            button_hover_color="#00B3CC",
            text_color="#FFFFFF"
        )
        lang_menu.grid(row=12, column=0, sticky="ew", padx=15)
        
        lang_hint = ctk.CTkLabel(right_frame, text="Currently locked to Persian", text_color="#E0E0E0", font=ctk.CTkFont(size=11))
        lang_hint.grid(row=13, column=0, sticky="w", padx=15, pady=(0, 15))
        
        # Batch Size
        batch_label = ctk.CTkLabel(right_frame, text="Batch Size:", text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"))
        batch_label.grid(row=14, column=0, sticky="w", padx=15)
        
        self.batch_var = ctk.StringVar(value="4")
        batch_menu = ctk.CTkOptionMenu(
            right_frame,
            values=["1", "2", "4", "8", "16"],
            variable=self.batch_var,
            corner_radius=12,
            fg_color="#1A1B26",
            button_color="#00E5FF",
            button_hover_color="#00B3CC",
            text_color="#FFFFFF"
        )
        batch_menu.grid(row=15, column=0, sticky="ew", padx=15)
        
        batch_hint = ctk.CTkLabel(right_frame, text="Batch Size: Optimal is 4-8", text_color="#E0E0E0", font=ctk.CTkFont(size=11))
        batch_hint.grid(row=16, column=0, sticky="w", padx=15, pady=(0, 15))
        
        # Spacer
        right_frame.grid_rowconfigure(17, weight=1)
        
        # Settings Button
        settings_btn = ctk.CTkButton(
            right_frame,
            text="⚙️ Settings & API Keys",
            command=self._open_settings,
            corner_radius=12,
            fg_color="transparent",
            text_color="#FFFFFF",
            border_width=1,
            border_color="#00E5FF",
            hover_color="#24283B"
        )
        settings_btn.grid(row=18, column=0, pady=20, padx=15, sticky="ew")
        
        self._on_provider_change(self.provider_var.get())

    # ==========================
    # Logic & Event Handlers
    # ==========================

    def _get_config_value(self, section, key, default):
        """Helper to safely get config values."""
        return self.config.get(section, {}).get(key, default)

    def _save_whisper_config(self, value):
        """Save Whisper model selection to config."""
        if "provider_settings" not in self.config:
            self.config["provider_settings"] = {}
        self.config["provider_settings"]["whisper_model"] = value
        self.config_manager.save_config()

    def _on_provider_change(self, provider):
        """Handle provider change event."""
        # Save selection
        if "provider_settings" not in self.config:
            self.config["provider_settings"] = {}
        self.config["provider_settings"]["last_provider"] = provider
        self.config_manager.save_config()
        
        # Always show model menu, trigger fetch
        self.model_label.grid()
        self.model_menu.grid()
        
        # Trigger fetch in background
        self._fetch_models(provider)

    def _fetch_models(self, provider):
        """Start background thread to fetch models."""
        # Show loading state
        self.model_menu.configure(state="disabled", values=["Loading..."])
        self.model_var.set("Loading...")
        
        # Start thread
        threading.Thread(target=self._fetch_models_thread, args=(provider,), daemon=True).start()

    def _fetch_models_thread(self, provider):
        """Background thread logic."""
        try:
            api_key = self.config_manager.get_api_key(provider)
            
            # If provider needs key but it's missing
            if provider in ["gemini", "groq", "openrouter", "nvidia"] and not api_key:
                self.update_queue.put(("log", {"message": f"⚠️ Missing API Key for {provider}. Please set in Settings."}))
                self.update_queue.put(("models_update", []))
                return

            models = SubFarsiCore.get_available_models(provider, api_key)
            self.update_queue.put(("models_update", models))
            
        except Exception as e:
            msg = f"❌ Failed to fetch models: {e}"
            if provider == "groq" and ("401" in str(e) or "400" in str(e)):
                msg += "\n💡 Tip: Check if your Groq API key is active."
            self.update_queue.put(("log", {"message": msg}))
            self.update_queue.put(("models_update", []))

    def _open_settings(self):
        """Open Settings dialog for API keys."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("500x450")
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (500 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (450 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        ctk.CTkLabel(dialog, text="API Keys Configuration", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        
        # Form Container
        form = ctk.CTkFrame(dialog)
        form.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        entries = {}
        
        def add_field(label_text, key_name):
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=10)
            ctk.CTkLabel(row, text=label_text, width=120, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, show="*", placeholder_text="sk-...", width=250)
            entry.pack(side="left", fill="x", expand=True)
            # Pre-fill
            current_val = self.config_manager.get_api_key(key_name)
            if current_val:
                entry.insert(0, current_val)
            entries[key_name] = entry

        add_field("Gemini API Key:", "gemini")
        add_field("Groq API Key:", "groq")
        add_field("OpenRouter Key:", "openrouter")
        add_field("NVIDIA API Key:", "nvidia")
        # OpenAI/DeepSeek generically
        add_field("OpenAI/Other Key:", "openai")
        
        def save():
            for key, entry in entries.items():
                val = entry.get().strip()
                self.config_manager.set_api_key(key, val)
            messagebox.showinfo("Settings", "API Keys saved successfully!")
            dialog.destroy()
            
        ctk.CTkButton(dialog, text="Save Settings", command=save, fg_color="green").pack(pady=20)

    def _update_models_list(self, models):
        """Update model dropdown with fetched models and categorization labels."""
        provider = self.provider_var.get()
        
        # Mapping for UI categorization labels
        labels = {
            "groq": "Groq (Lightning Fast)",
            "openrouter": "OpenRouter (Free-Only Shield)",
            "nvidia": "NVIDIA (Experimental)",
            "gemini": "Gemini (v2.5 Standards)",
            "ollama": "Ollama (Local AI)"
        }
        
        category_label = labels.get(provider, provider.capitalize())
        
        if models:
            # Flatten or format models? 
            # We'll keep the model name but maybe prefix it for visual clarity in the list?
            # Actually, per user request, we categorize the selection. 
            # If the user wants the label IN the dropdown vs as a header.
            # We will use "Category: Model" format for maximum clarity.
            display_models = [f"{category_label}: {m}" for m in models]
            
            self.model_menu.configure(values=display_models, state="normal")
            self.model_var.set(display_models[0])
            self._log_message(f"✅ Loaded {len(models)} models for {provider.upper()}")
        else:
            self.model_menu.configure(values=[f"No {provider} models found"], state="disabled")
            self.model_var.set("")

    def _check_dependencies_on_startup(self):
        """Check system dependencies."""
        try:
            deps = SubFarsiCore.check_system_dependencies()
            # Log statuses
            if deps['ffmpeg']['available']: self._log_message(deps['ffmpeg']['message'])
            else: self._log_message(deps['ffmpeg']['message'].split('\n')[0])
            
            if deps['ollama']['available']: self._log_message(deps['ollama']['message'])
            else: self._log_message(deps['ollama']['message'].split('\n')[0])
            
            # Gemini SDK Check
            from core_v4 import GEMINI_SDK_AVAILABLE
            if not GEMINI_SDK_AVAILABLE:
                self._log_message("⚠️ Native Gemini SDK (google-genai) not found. REST fallback active.")
                self._log_message("💡 Run: pip install -q -U google-genai")
                
        except Exception as e:
            self._log_message(f"⚠️ Dependency check failed: {e}")

    def _start_processing(self):
        """Start the video processing in a separate thread."""
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showerror("Error", "Please select a valid video file.")
            return
        
        if self.is_processing:
            self._stop_processing()
            return
        
        # Disable controls
        self.is_processing = True
        self.select_video_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self._update_status("Initializing...")
        
        # Clear log
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        # Get settings
        provider = self.provider_var.get()
        model_name = self.model_var.get()
        
        # Handle categorized model names (e.g., "Groq: model-id")
        if ": " in model_name:
            model_name = model_name.split(": ", 1)[1]
            
        if hasattr(self, 'cancel_event'):
            self.cancel_event.clear()
        
        # Initialize core engine with new Strategy Pattern
        try:
            batch_size = int(getattr(self, "batch_var", ctk.StringVar(value="4")).get())
            self.core = SubFarsiCore(
                ollama_model=model_name,
                whisper_model_size=self.whisper_model_var.get(),
                batch_size=batch_size,
                translation_provider=provider
            )
            
            # Start processing thread
            self.processing_thread = threading.Thread(target=self._process_video_thread, daemon=True)
            self.processing_thread.start()
            
        except Exception as e:
            self._log_message(f"❌ Initialization failed: {e}")
            self._reset_ui()

    # ... [Standard Methods: _stop_processing, _process_video_thread, _process_queue, _progress_callback, _on_processing_complete, _reset_ui, _select_video, _log_message, _update_status, _toggle_cloud_section (removed), _load_ollama_models, _update_vram_info, _auto_select_whisper_model] ...
    # Re-implementing simplified versions for completeness of the artifact
    
    def _stop_processing(self):
        self.is_processing = False
        if hasattr(self, 'cancel_event'):
            self.cancel_event.set()
        self._update_status("Stopped")
        self._log_message("⚠️ Processing stopped by user")
        self._reset_ui()

    def _process_video_thread(self):
        try:
            self.update_queue.put(("log", {"message": "🚀 Starting SubFarsiPro processing..."}))
            output_path = self.core.process_video(
                video_path=self.video_path,
                progress_callback=self._progress_callback,
                cancel_event=self.cancel_event if hasattr(self, 'cancel_event') else None
            )
            self.update_queue.put(("complete", {
                "success": True, "message": f"✅ Processing complete! Saved to: {os.path.basename(output_path)}", "output_path": output_path
            }))
        except Exception as e:
            if "cancelled by user" in str(e).lower():
                self.update_queue.put(("log", {"message": "✅ Task successfully cancelled."}))
                self.update_queue.put(("status", {"text": "Cancelled", "progress": 0.0}))
                return
            self.update_queue.put(("complete", {
                "success": False, "message": f"❌ Error: {str(e)}", "output_path": None
            }))

    def _progress_callback(self, status: str):
        progress = None
        if "Extracting" in status: progress = 0.1
        elif "Transcribing" in status: progress = 0.3
        elif "Translating" in status: progress = 0.6
        elif "Writing" in status: progress = 0.9
        elif "Complete" in status: progress = 1.0
        self.update_queue.put(("status", {"text": status, "progress": progress}))
        self.update_queue.put(("log", {"message": status}))

    def _process_queue(self):
        try:
            while True:
                type, data = self.update_queue.get_nowait()
                if type == "status": self._update_status(data["text"], data.get("progress"))
                elif type == "log": self._log_message(data["message"])
                elif type == "complete": self._on_processing_complete(data.get("success"), data.get("message"), data.get("output_path"))
                elif type == "models_update": self._update_models_list(data)
                elif type == "setup_progress": self._update_setup_progress(data["percent"])
                elif type == "setup_complete": self._on_setup_complete(data["status"])
        except queue.Empty: pass
        self.after(100, self._process_queue)

    def _on_processing_complete(self, success, message, output_path):
        if success:
            self.output_srt_path = output_path
            self._log_message(message)
            self._update_status("Complete!", 1.0)
            self.is_processing = False
            self._show_success_frame()
        else:
            self._log_message(message)
            self._update_status("Error", 0.0)
            messagebox.showerror("Error", message)
            self._reset_ui()

    def _show_success_frame(self):
        if self.success_frame:
            self.start_btn.grid_remove()
            self.stop_btn.grid_remove()
            self.success_frame.grid(row=4, column=0, rowspan=2, pady=(0, 15), sticky="ew")

    def _reset_ui(self):
        self.is_processing = False
        self.select_video_btn.configure(state="normal")
        if self.success_frame: self.success_frame.grid_remove()
        self.start_btn.grid(row=4, column=0, sticky="ew", pady=(0, 15))
        self.stop_btn.grid(row=5, column=0, sticky="ew", pady=(0, 15))
        self.start_btn.configure(text="Start Processing", fg_color="#00E5FF", text_color="#000000", state="normal" if self.video_path else "disabled")
        self.stop_btn.configure(state="disabled")
        self.progress_bar.set(0)

    def _play_video(self):
        if not self.video_path or not os.path.exists(self.video_path): return
        try:
            if platform.system() == "Windows": os.startfile(self.video_path)
            elif platform.system() == "Darwin": subprocess.run(["open", self.video_path], check=True)
            else: subprocess.run(["xdg-open", self.video_path], check=True)
        except Exception as e: self._log_message(f"❌ Failed to play: {e}")

    def _new_task(self):
        self._reset_ui()
        self.video_path = None
        self.video_path_label.configure(image="", text="No video selected", text_color="gray")
        self.video_path_label.image = None
        self.log_textbox.configure(state="normal"); self.log_textbox.delete("1.0", "end"); self.log_textbox.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self._log_message("🔄 Ready for new task")

    def _exit_app(self):
        if self.is_processing:
            if not messagebox.askyesno("Exit", "Processing active. Exit anyway?"): return
        self.destroy()

    def _select_video(self):
        f = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.avi"), ("All", "*.*")])
        if f:
            self.video_path = f
            self._update_video_thumbnail(f)
            self.start_btn.configure(state="normal")
            self._log_message(f"📹 Selected: {os.path.basename(f)}")

    def _update_video_thumbnail(self, filepath):
        try:
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                raise Exception("Cannot open video file")
            
            # Read a frame at 1-second mark (or 0 if shorter)
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps))
                
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                
            cap.release()
            
            if not ret or frame is None:
                raise Exception("Failed to read a valid frame")
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((400, 250), Image.Resampling.LANCZOS)
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.video_path_label.configure(image=ctk_img, text="")
            self.video_path_label.image = ctk_img
            
        except Exception as e:
            self._log_message(f"⚠️ Thumbnail extraction failed: {e}")
            self.video_path_label.configure(image="", text=f"Selected: {os.path.basename(filepath)}", text_color="#00E5FF")

    def _log_message(self, msg):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _copy_logs_to_clipboard(self):
        """
        Copy the latest SubFarsiPro log file contents to the clipboard.
        This is useful for bug reports. If no log file is found, show a
        friendly message instead of raising errors.
        """
        try:
            logs_dir = get_app_data_dir() / "logs"
            if not logs_dir.exists():
                messagebox.showinfo("Copy Logs", "No log directory found yet. Run a task first.")
                return

            # Find the latest *.log file
            log_files = sorted(
                [p for p in logs_dir.glob("*.log") if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not log_files:
                messagebox.showinfo("Copy Logs", "No log files found. Run a task first.")
                return

            latest = log_files[0]
            content = latest.read_text(encoding="utf-8", errors="replace")

            # Copy to clipboard
            self.clipboard_clear()
            self.clipboard_append(content)
            self.update()  # ensure clipboard is updated on some platforms

            messagebox.showinfo("Copy Logs", f"Logs copied to clipboard from:\n{latest}")
        except Exception as e:
            messagebox.showerror("Copy Logs", f"Failed to copy logs: {e}")

    def _update_status(self, status, progress=None):
        self.status_label.configure(text=status)
        if progress is not None: self.progress_bar.set(progress)

    def _load_ollama_models(self):
        self._fetch_models("ollama")

    def _update_vram_info(self):
        vram = SubFarsiCore.get_vram_gb()
        self.vram_info_label.configure(text=f"VRAM: {vram:.1f}GB" if vram else "No GPU", text_color="lightblue" if vram else "gray")

    def _auto_select_whisper_model(self):
        m, r = SubFarsiCore.auto_select_whisper_model()
        self.whisper_model_var.set(m)
        self.vram_info_label.configure(text=r, text_color="lightgreen")
        self._log_message(f"✨ Auto-selected: {m}")

def main():
    app = SubFarsiProApp()
    app.mainloop()

if __name__ == "__main__":
    main()
