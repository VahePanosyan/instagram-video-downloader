"""JSON file-based persistence for settings and download history."""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..domain.models import AppSettings, DownloadHistoryItem
from ..ports.repository import ISettingsRepository, IHistoryRepository
from ..domain.exceptions import StorageException


def is_dir_writable(path: Path) -> bool:
    """Tests if a directory is actually writable by probing with a temporary file."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_file = path / f".write_probe_{os.getpid()}_{threading.get_ident()}"
        with open(probe_file, "w") as f:
            f.write("probe")
        probe_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def is_path_usable(path_str: str) -> bool:
    """Validates that a path string has a valid, existing drive/anchor on Windows."""
    if not path_str or not isinstance(path_str, str):
        return False
    try:
        p = Path(path_str)
        if sys.platform == "win32" and p.anchor:
            return os.path.exists(p.anchor)
        return True
    except Exception:
        return False


def get_default_config_dir() -> Path:
    """Returns safe persistent configuration directory across dev, portable, and installed setups."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent

        # 1. Explicit portable mode marker: portable.dat next to the executable
        if (exe_dir / "portable.dat").is_file():
            portable_config = exe_dir / "config"
            if is_dir_writable(portable_config):
                return portable_config

        # 2. Installed mode detection (explicit marker, Program Files, or Local Programs)
        is_installed = (exe_dir / "installed.dat").is_file()
        exe_dir_str = str(exe_dir).lower()
        if "program files" in exe_dir_str or "appdata\\local\\programs" in exe_dir_str:
            is_installed = True

        # 3. Check for existing local writable config directory (only if not an installed copy)
        if not is_installed:
            portable_config = exe_dir / "config"
            if portable_config.is_dir() and is_dir_writable(portable_config):
                return portable_config

        # 4. Standard Windows installed mode: %APPDATA%\InstagramVideoDownloader\config
        app_data = os.environ.get("APPDATA")
        if app_data:
            path = Path(app_data) / "InstagramVideoDownloader" / "config"
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except Exception:
                pass

        # Fallback to user home
        user_config = Path.home() / ".instagram_downloader" / "config"
        user_config.mkdir(parents=True, exist_ok=True)
        return user_config

    # Development / test mode: repository root config directory
    repo_config = Path(__file__).resolve().parent.parent.parent / "config"
    repo_config.mkdir(parents=True, exist_ok=True)
    return repo_config


def get_default_downloads_dir() -> Path:
    """Returns safe default downloads directory for newly initialized settings."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        # In portable mode, if a downloads directory exists or can be created next to exe, use it
        if (exe_dir / "portable.dat").is_file():
            portable_dl = exe_dir / "downloads"
            if is_dir_writable(portable_dl):
                return portable_dl

        user_downloads = Path.home() / "Downloads"
        try:
            user_downloads.mkdir(parents=True, exist_ok=True)
            return user_downloads
        except Exception:
            return Path.home()

    dev_downloads = Path(__file__).resolve().parent.parent.parent / "downloads"
    try:
        dev_downloads.mkdir(parents=True, exist_ok=True)
        return dev_downloads
    except Exception:
        return Path.home()


class JsonSettingsRepository(ISettingsRepository):
    """Stores application settings in a JSON file with thread-safe persistence."""

    def __init__(self, file_path: Optional[str] = None):
        self._lock = threading.RLock()
        if file_path:
            self._path = Path(file_path)
        else:
            base_dir = get_default_config_dir()
            self._path = base_dir / "settings.json"

    def load(self) -> AppSettings:
        with self._lock:
            if not self._path.exists():
                default_settings = AppSettings()
                downloads_dir = get_default_downloads_dir()
                default_settings.download_dir = str(downloads_dir)
                self.save(default_settings)
                return default_settings

            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    settings = AppSettings.from_dict(data)
                    # Self-heal invalid or non-existent download directory (e.g. copied from another PC)
                    if not settings.download_dir or not is_path_usable(settings.download_dir):
                        settings.download_dir = str(get_default_downloads_dir())
                    return settings
            except Exception:
                # Fall back to default on parse error
                default_settings = AppSettings()
                default_settings.download_dir = str(get_default_downloads_dir())
                return default_settings

    def save(self, settings: AppSettings) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = settings.to_dict()
            try:
                # Atomic write via temp file
                temp_file = tempfile.NamedTemporaryFile(
                    "w", dir=str(self._path.parent), delete=False, encoding="utf-8"
                )
                with temp_file as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_file.name, str(self._path))
            except Exception as e:
                raise StorageException(f"Failed to save settings: {str(e)}")


class JsonHistoryRepository(IHistoryRepository):
    """Stores download history in a JSON file with thread-safe persistence."""

    def __init__(self, file_path: Optional[str] = None):
        self._lock = threading.RLock()
        if file_path:
            self._path = Path(file_path)
        else:
            base_dir = get_default_config_dir()
            self._path = base_dir / "history.json"

    def _read_data(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._path.exists():
                return []
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []

    def _write_data(self, data: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            try:
                temp_file = tempfile.NamedTemporaryFile(
                    "w", dir=str(self._path.parent), delete=False, encoding="utf-8"
                )
                with temp_file as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_file.name, str(self._path))
            except Exception as e:
                raise StorageException(f"Failed to persist history: {str(e)}")

    def get_all(self) -> List[DownloadHistoryItem]:
        with self._lock:
            raw = self._read_data()
            items = [DownloadHistoryItem.from_dict(d) for d in raw]
            # Most recent first
            return sorted(items, key=lambda x: x.downloaded_at, reverse=True)

    def add(self, item: DownloadHistoryItem) -> None:
        with self._lock:
            raw = self._read_data()
            # Keep maximum 1000 items in history
            raw.insert(0, item.to_dict())
            if len(raw) > 1000:
                raw = raw[:1000]
            self._write_data(raw)

    def remove(self, item_id: str) -> bool:
        with self._lock:
            raw = self._read_data()
            filtered = [x for x in raw if x.get("id") != item_id]
            if len(filtered) != len(raw):
                self._write_data(filtered)
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._write_data([])
