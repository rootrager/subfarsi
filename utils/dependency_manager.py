"""
Dependency management for SubFarsiPro.

This module is responsible for:
- Locating or downloading FFmpeg into the per-user bin directory.
- Checking reachability of local Ollama.

Downloads are always written under the OS-specific user data directory
returned by utils.path_manager, never into the application install directory.
"""

import os
import shutil
import tarfile
import zipfile
import tempfile
from pathlib import Path
from typing import Callable, Optional

import requests

from .path_manager import get_bin_dir, ensure_dirs


ProgressCallback = Optional[Callable[[int], None]]  # percentage 0-100


class DependencyManager:
    """Utility class to manage external runtime dependencies."""

    # Known FFmpeg builds
    FFMPEG_WINDOWS_URL = (
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    )
    FFMPEG_LINUX_URL = (
        "https://www.johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    )

    @staticmethod
    def _ffmpeg_target_path() -> Path:
        bin_dir = get_bin_dir()
        exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        return bin_dir / exe_name

    # -----------------------------
    # Presence / readiness checks
    # -----------------------------

    @classmethod
    def is_ffmpeg_present(cls) -> bool:
        """
        Return True if FFmpeg is available either in our managed bin directory
        OR already installed on the system PATH.

        This prevents false negatives on systems where FFmpeg is already
        installed globally (e.g., via package manager), and we don't need
        to re-download it into the user data directory.
        """
        target = cls._ffmpeg_target_path()
        if target.exists() and os.access(target, os.X_OK):
            return True

        # Fallback: check system PATH
        from shutil import which

        return which("ffmpeg") is not None

    @staticmethod
    def is_ollama_reachable(timeout: float = 2.0) -> bool:
        """Return True if a local Ollama instance appears reachable."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def is_ready(cls) -> bool:
        """
        Overall readiness check for the core app:
        - FFmpeg present in user bin dir
        - Ollama reachable on localhost
        """
        ensure_dirs()
        return cls.is_ffmpeg_present() and cls.is_ollama_reachable()

    @classmethod
    def check_status(cls) -> dict:
        """
        Return a structured status dictionary for the GUI / launcher.

        Example:
        {
            "ffmpeg": True/False,
            "ollama": True/False,
        }
        """
        ensure_dirs()
        return {
            "ffmpeg": cls.is_ffmpeg_present(),
            "ollama": cls.is_ollama_reachable(),
        }

    # -----------------------------
    # Download helpers
    # -----------------------------

    @staticmethod
    def _download_with_progress(
        url: str, dest_path: Path, progress_callback: ProgressCallback = None
    ) -> None:
        """
        Download a file to dest_path, reporting integer percentage via callback.
        """
        if progress_callback:
            progress_callback(0)

        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0

            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    if total > 0:
                        downloaded += len(chunk)
                        if progress_callback:
                            pct = int(downloaded * 100 / total)
                            progress_callback(pct)

        if progress_callback:
            progress_callback(100)

    # -----------------------------
    # FFmpeg installation
    # -----------------------------

    @classmethod
    def ensure_ffmpeg(
        cls, progress_callback: ProgressCallback = None
    ) -> Path:
        """
        Ensure ffmpeg is available in the managed bin dir.
        Returns the path to the ffmpeg binary.
        """
        ensure_dirs()
        target = cls._ffmpeg_target_path()
        if cls.is_ffmpeg_present():
            if progress_callback:
                progress_callback(100)
            return target

        if os.name == "nt":
            cls._install_ffmpeg_windows(target, progress_callback)
        else:
            cls._install_ffmpeg_linux(target, progress_callback)

        return target

    @classmethod
    def install_missing(cls, progress_callback: ProgressCallback = None) -> dict:
        """
        Install any missing dependencies that can be managed automatically.

        Currently:
        - Installs FFmpeg into the user bin directory if missing.
        - Does NOT attempt to install Ollama (user action required).

        Returns the same structure as check_status().
        """
        ensure_dirs()
        if not cls.is_ffmpeg_present():
            cls.ensure_ffmpeg(progress_callback=progress_callback)
        # Re-check everything after installation attempt
        return cls.check_status()

    @classmethod
    def _install_ffmpeg_windows(
        cls, target: Path, progress_callback: ProgressCallback = None
    ) -> None:
        """
        Download and extract ffmpeg-release-essentials.zip on Windows,
        copying ffmpeg.exe into our bin dir.
        """
        if progress_callback:
            progress_callback(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_zip = Path(tmpdir) / "ffmpeg.zip"
            cls._download_with_progress(cls.FFMPEG_WINDOWS_URL, tmp_zip, progress_callback)

            with zipfile.ZipFile(tmp_zip, "r") as zf:
                ffmpeg_member = None
                for name in zf.namelist():
                    # typical path: ffmpeg-YYYYMMDD-...-essentials_build/bin/ffmpeg.exe
                    if name.lower().endswith("/ffmpeg.exe") or name.lower().endswith("ffmpeg.exe"):
                        ffmpeg_member = name
                        break

                if not ffmpeg_member:
                    raise RuntimeError("ffmpeg.exe not found in downloaded archive.")

                extracted_path = Path(tmpdir) / "ffmpeg.exe"
                with zf.open(ffmpeg_member) as src, open(extracted_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(extracted_path), str(target))

        if progress_callback:
            progress_callback(100)

    @classmethod
    def _install_ffmpeg_linux(
        cls, target: Path, progress_callback: ProgressCallback = None
    ) -> None:
        """
        Download and extract static ffmpeg build on Linux, placing the
        ffmpeg binary into our bin dir.
        """
        if progress_callback:
            progress_callback(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_tar = Path(tmpdir) / "ffmpeg.tar.xz"
            cls._download_with_progress(cls.FFMPEG_LINUX_URL, tmp_tar, progress_callback)

            with tarfile.open(tmp_tar, "r:xz") as tf:
                ffmpeg_member = None
                for member in tf.getmembers():
                    name = member.name
                    # typical path: ffmpeg-*-amd64-static/ffmpeg
                    if name.endswith("/ffmpeg") or name == "ffmpeg":
                        ffmpeg_member = member
                        break

                if not ffmpeg_member:
                    raise RuntimeError("ffmpeg binary not found in downloaded archive.")

                tf.extract(ffmpeg_member, path=tmpdir)
                extracted_path = Path(tmpdir) / ffmpeg_member.name

                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(extracted_path), str(target))
                target.chmod(target.stat().st_mode | 0o111)  # ensure executable

        if progress_callback:
            progress_callback(100)

