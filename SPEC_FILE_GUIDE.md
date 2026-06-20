# SubFarsiPro.spec - Usage Guide

## Overview

This PyInstaller spec file provides a declarative, cross-platform build configuration for SubFarsiPro. It handles all the complexities of bundling dependencies, assets, and ensuring compatibility across Windows and Linux.

## Key Features

### ✅ Dynamic CustomTkinter Path Detection
- Automatically detects CustomTkinter installation path
- Bundles CustomTkinter assets correctly
- Handles missing CustomTkinter gracefully

### ✅ Cross-Platform Asset Handling
- Includes `config.json` template
- Includes `assets/` directory (if present)
- Uses `os.path.join` for cross-platform path compatibility

### ✅ Comprehensive Hidden Imports
- All required modules explicitly listed
- Includes utils package and submodules
- Faster-Whisper components
- PIL/Pillow for CustomTkinter
- PyTorch dependencies

### ✅ Smart Exclusions
- Excludes heavy unused frameworks (matplotlib, PyQt, etc.)
- Keeps essential dependencies (torch, faster-whisper)
- Optimizes bundle size without breaking functionality

### ✅ Icon Support
- Automatically detects icons for Windows (.ico) and Linux (.png)
- Falls back gracefully if no icon found
- Supports multiple icon file naming conventions

## Building the Executable

### Basic Build
```bash
pyinstaller SubFarsiPro.spec
```

### Clean Build (Recommended)
```bash
# Remove previous builds
rm -rf build/ dist/

# Build fresh
pyinstaller SubFarsiPro.spec
```

### Windows Build
```bash
pyinstaller SubFarsiPro.spec
# Output: dist/SubFarsiPro.exe
```

### Linux Build
```bash
pyinstaller SubFarsiPro.spec
# Output: dist/SubFarsiPro
```

## Debugging

### Enable Console Window
Edit `SubFarsiPro.spec` and change:
```python
console=False,  # Change to True
```

Then rebuild:
```bash
pyinstaller SubFarsiPro.spec --clean
```

### Verbose Output
```bash
pyinstaller SubFarsiPro.spec --log-level=DEBUG
```

### Check What's Included
```bash
pyinstaller SubFarsiPro.spec --log-level=INFO
```

## Troubleshooting

### Issue: CustomTkinter assets missing
**Solution:** The spec file automatically detects CustomTkinter. If issues persist, verify CustomTkinter is installed:
```bash
pip show customtkinter
```

### Issue: Icon not found
**Solution:** The spec file will use default icon if none found. To add an icon:
- Windows: Place `icon.ico` in `assets/` directory
- Linux: Place `subfarsi.png` in `assets/` directory

### Issue: Missing modules at runtime
**Solution:** Add missing modules to `hiddenimports` list in the spec file, then rebuild.

### Issue: Large executable size
**Solution:** The spec file already excludes heavy unused modules. You can add more exclusions to the `excludes` list if needed.

## File Structure After Build

```
dist/
└── SubFarsiPro (or SubFarsiPro.exe)
    ├── config.json (bundled template)
    ├── assets/ (if included)
    └── [all Python dependencies]
```

## Notes

- **FFmpeg**: Not bundled (handled by DependencyManager at runtime)
- **Ollama**: Not bundled (user must install separately)
- **Config**: Template bundled, user config saved to OS-specific data directory
- **Assets**: Bundled if `assets/` directory exists

## Advanced Configuration

### Disable UPX Compression
If UPX causes issues, edit the spec file:
```python
upx=False,  # Change from True
```

### Add Additional Data Files
Edit the `datas` list:
```python
datas.append(('path/to/file', 'destination/in/bundle'))
```

### Add Additional Hidden Imports
Edit the `hiddenimports` list:
```python
hiddenimports.append('your.module.name')
```
