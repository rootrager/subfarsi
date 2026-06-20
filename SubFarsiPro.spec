# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import platform
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import customtkinter

block_cipher = None

# 1. FIND CUSTOMTKINTER PATH
ctk_path = os.path.dirname(customtkinter.__file__)

# 2. DEFINE DATA FILES
datas = [
    (ctk_path, 'customtkinter'),
    ('config.json', '.'),
    ('assets', 'assets'),
    ('utils', 'utils'),
]

# 3. HIDDEN IMPORTS
hiddenimports = [
    'PIL',
    'PIL._tkinter_finder',
    'babel.numbers',
    'faster_whisper',
    'customtkinter',
    'utils.path_manager',
    'utils.dependency_manager'
]

a = Analysis(
    ['main_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],  # We can exclude heavy unused libs here later if needed
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- CHANGED FOR ONEDIR MODE (More Stable) ---
exe = EXE(
    pyz,
    a.scripts,
    [], # Binaries are excluded from the EXE itself
    exclude_binaries=True,
    name='SubFarsiPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Keep True for now to see errors if it crashes on startup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/subfarsi.png' if os.path.exists('assets/subfarsi.png') else None
)

# This creates a FOLDER in dist/ instead of a single file
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SubFarsiPro',
)