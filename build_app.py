#!/usr/bin/env python3
"""
SubFarsiPro - Cross-Platform PyInstaller Build Script

This script builds a standalone executable for SubFarsiPro using PyInstaller.
It handles both Windows (.exe) and Linux (binary) builds.

Features:
- Cross-platform path handling
- Proper resource bundling (config.json, assets)
- Hidden imports configuration
- Clean build directories
- OS-specific executable naming

Usage:
    python build_app.py
"""

import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path


# ==========================================
# Configuration
# ==========================================

APP_NAME = "SubFarsiPro"
APP_VERSION = "5.0"
MAIN_SCRIPT = "main_app.py"
ICON_FILE = None  # Set to "assets/subfarsi.ico" if you have an icon

# Files/directories to include in the bundle
DATA_FILES = [
    ("config.json", "."),  # Include config.json template
    # Add more data files here: ("assets/", "assets"),
]

# Hidden imports (modules PyInstaller might miss)
HIDDEN_IMPORTS = [
    "PIL._tkinter_finder",
    "customtkinter",
    "faster_whisper",
    "faster_whisper.model",
    "faster_whisper.audio",
    "utils",
    "utils.path_manager",
    "utils.dependency_manager",
    "google.genai",  # Optional Gemini SDK
    "torch",
    "torch._C",
    "requests",
    "urllib3",
]


# ==========================================
# Utility Functions
# ==========================================

def get_separator():
    """Return OS-specific path separator for --add-data."""
    return ";" if platform.system() == "Windows" else ":"


def clean_build_dirs():
    """Remove previous build artifacts."""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = [f"{APP_NAME}.spec"]
    
    print("🧹 Cleaning previous build artifacts...")
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   ✅ Removed {dir_name}/")
    
    for file_name in files_to_clean:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"   ✅ Removed {file_name}")


def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        print(f"✅ PyInstaller found: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("❌ PyInstaller not found!")
        print("📦 Install with: pip install pyinstaller")
        return False


def build_command():
    """Construct PyInstaller command as a list of strings."""
    sep = get_separator()
    system = platform.system()
    
    # Base command
    cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--onefile",  # Single executable
        "--windowed",  # No console window (GUI app)
        "--clean",  # Clean cache before building
    ]
    
    # Add icon if available
    if ICON_FILE and os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])
        print(f"   📎 Using icon: {ICON_FILE}")
    else:
        print("   ⚠️  No icon file found (skipping --icon)")
    
    # Add data files
    for src, dst in DATA_FILES:
        if os.path.exists(src):
            cmd.extend(["--add-data", f"{src}{sep}{dst}"])
            print(f"   📎 Adding data: {src} -> {dst}")
        else:
            print(f"   ⚠️  Data file not found: {src} (skipping)")
    
    # Add hidden imports
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])
    
    # OS-specific options
    if system == "Windows":
        # Windows-specific options
        cmd.extend([
            "--exclude-module", "matplotlib",  # Reduce size
            "--exclude-module", "numpy.distutils",  # Reduce size
        ])
    elif system == "Linux":
        # Linux-specific options
        cmd.extend([
            "--exclude-module", "matplotlib",  # Reduce size
            "--exclude-module", "numpy.distutils",  # Reduce size
        ])
    
    # Add main script
    cmd.append(MAIN_SCRIPT)
    
    return cmd


def main():
    """Main build function."""
    print("=" * 60)
    print(f"🔨 Building {APP_NAME} v{APP_VERSION}")
    print(f"   Platform: {platform.system()} {platform.machine()}")
    print("=" * 60)
    print()
    
    # Check prerequisites
    if not check_pyinstaller():
        sys.exit(1)
    
    if not os.path.exists(MAIN_SCRIPT):
        print(f"❌ Main script not found: {MAIN_SCRIPT}")
        sys.exit(1)
    
    # Clean previous builds
    clean_build_dirs()
    print()
    
    # Build command
    cmd = build_command()
    
    print()
    print("🚀 Starting PyInstaller build...")
    print(f"   Command: {' '.join(cmd)}")
    print()
    
    # Run PyInstaller
    try:
        result = subprocess.run(cmd, check=True)
        
        print()
        print("=" * 60)
        print("✅ Build completed successfully!")
        print("=" * 60)
        
        # Show output location
        system = platform.system()
        if system == "Windows":
            exe_path = f"dist/{APP_NAME}.exe"
        else:
            exe_path = f"dist/{APP_NAME}"
        
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"📦 Executable: {exe_path}")
            print(f"   Size: {size_mb:.1f} MB")
            print()
            print("💡 Next steps:")
            print("   1. Test the executable: ./dist/SubFarsiPro")
            print("   2. The app will download FFmpeg on first run if needed")
            print("   3. Ensure Ollama is installed and running")
        else:
            print(f"⚠️  Expected executable not found: {exe_path}")
            print("   Check build output above for errors")
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print("❌ Build failed!")
        print("=" * 60)
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("⚠️  Build interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
