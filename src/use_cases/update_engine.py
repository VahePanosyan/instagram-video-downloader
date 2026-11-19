"""Use case coordinating yt-dlp version checks and engine updates."""

from typing import Tuple, Optional, Callable
from ..ports.updater import IEngineUpdater


class UpdateEngineUseCase:
    """Interacts with engine updater port to provide check and update services."""

    def __init__(self, updater: IEngineUpdater):
        self._updater = updater

    def check_update(self) -> Tuple[bool, str, str]:
        """Returns (has_update, current_version, latest_version)."""
        return self._updater.check_for_updates()

    def update(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Executes update and returns True if successful."""
        return self._updater.perform_update(progress_callback=progress_callback)

    def check_ffmpeg(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Returns (is_healthy, version_str, path_or_details)."""
        return self._updater.check_ffmpeg_health()
