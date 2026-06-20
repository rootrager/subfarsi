"""
Path management utilities for SubFarsiPro.

This module is intentionally restricted to Python's standard library so it can
be imported very early in the bootstrap process (including in PyInstaller
frozen environments) without extra dependencies.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional


APP_NAME = "SubFarsiPro"
APP_NAME_LOWER = "subfarsipro"


def _expand_user(path: str) -> Path:
    """Return a Path with user (~) expanded in a cross-platform-safe way."""
    return Path(os.path.expanduser(path)).resolve()


def get_app_data_dir() -> Path:
    """
    Return the OS-specific per-user data directory for SubFarsiPro.

    - Windows: %LOCALAPPDATA%/SubFarsiPro/
    - Linux:   ~/.local/share/subfarsipro/
    - macOS:   ~/Library/Application Support/SubFarsiPro/
    """
    system = platform.system()

    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not base:
            # Fallback to home directory if env var is missing
            base = str(_expand_user("~"))
        return Path(base) / APP_NAME

    if system == "Darwin":
        # macOS Application Support
        return _expand_user(f"~/Library/Application Support/{APP_NAME}")

    # Default: Linux / Unix
    # Follow XDG spec if possible, otherwise ~/.local/share/subfarsipro
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_NAME_LOWER
    return _expand_user(f"~/.local/share/{APP_NAME_LOWER}")


def get_bin_dir() -> Path:
    """
    Return the directory where helper binaries (like ffmpeg) should live.

    This is ALWAYS inside the user data directory, never inside the
    application install / read-only bundle.
    """
    return get_app_data_dir() / "bin"


def ensure_dirs() -> None:
    """
    Ensure that the core application data directories exist.

    This does NOT create any files; it only ensures that the directory
    structure is present.
    """
    app_dir = get_app_data_dir()
    bin_dir = get_bin_dir()

    app_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

