"""Adapter implementing IEngineUpdater for yt-dlp version checking, pip updates, and FFmpeg diagnostics."""

import sys
import json
import urllib.request
import subprocess
from typing import Tuple, Optional, Callable
from pathlib import Path

from ..ports.updater import IEngineUpdater
from .ffmpeg_adapter import locate_ffmpeg_bin


class EngineUpdaterAdapter(IEngineUpdater):
    """Checks and updates yt-dlp, and verifies FFmpeg/FFprobe binaries."""

    PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"

    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy

    def get_current_version(self) -> str:
        """Returns the currently loaded yt-dlp version."""
        try:
            import yt_dlp.version
            return getattr(yt_dlp.version, "__version__", "unknown")
        except Exception:
            return "unknown"

    def check_for_updates(self) -> Tuple[bool, str, str]:
        """Queries PyPI for the latest yt-dlp version and compares against current version."""
        current_ver = self.get_current_version()
        try:
            req = urllib.request.Request(
                self.PYPI_URL,
                headers={"User-Agent": "MediaDownloaderPro/2.0"}
            )
            if self._proxy and self._proxy.strip():
                p = self._proxy.strip()
                if not (p.startswith("http://") or p.startswith("https://")):
                    p = f"http://{p}"
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({'http': p, 'https': p})
                )
                with opener.open(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            else:
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

            latest_ver = data.get("info", {}).get("version", current_ver)
            has_update = (latest_ver != current_ver and latest_ver != "unknown")
            return has_update, current_ver, latest_ver
        except Exception as e:
            return False, current_ver, f"Error: {str(e)[:40]}"

    def perform_update(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Runs pip upgrade command to update yt-dlp."""
        if progress_callback:
            progress_callback("Starting yt-dlp upgrade via pip...")

        # If frozen PyInstaller binary, pip upgrade of site-packages isn't viable directly
        if getattr(sys, "frozen", False):
            if progress_callback:
                progress_callback("Running standalone binary; please download the latest installer release.")
            return False

        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        try:
            no_window = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=no_window,
                timeout=120,
            )
            if proc.returncode == 0:
                if progress_callback:
                    progress_callback("yt-dlp upgrade completed successfully.")
                return True
            else:
                err = proc.stderr.decode("utf-8", errors="ignore")
                if progress_callback:
                    progress_callback(f"Upgrade failed (code {proc.returncode}): {err[:80]}")
                return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"Upgrade execution error: {str(e)}")
            return False

    def check_ffmpeg_health(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Verifies FFmpeg binary existence, runs version flag, and returns status."""
        bin_path = locate_ffmpeg_bin()
        if not bin_path or not Path(bin_path).exists():
            return False, None, "FFmpeg binary not detected on system."

        try:
            no_window = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            proc = subprocess.run(
                [bin_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=no_window,
                timeout=5,
            )
            if proc.returncode == 0:
                first_line = proc.stdout.decode("utf-8", errors="ignore").splitlines()[0]
                return True, first_line, bin_path
            else:
                return False, None, f"FFmpeg exited with non-zero code {proc.returncode}."
        except Exception as e:
            return False, None, f"Error launching FFmpeg: {str(e)}"
