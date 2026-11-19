"""Port interface for engine self-updater and binary dependency verification."""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Callable


class IEngineUpdater(ABC):
    """Abstract port for checking and updating yt-dlp and binary dependencies."""

    @abstractmethod
    def check_for_updates(self) -> Tuple[bool, str, str]:
        """
        Checks whether a newer version of yt-dlp is available.
        Returns:
            Tuple of (has_update: bool, current_version: str, latest_version: str)
        """
        pass

    @abstractmethod
    def perform_update(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Updates yt-dlp to the latest release in the current Python environment.
        Returns:
            True if upgrade succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def check_ffmpeg_health(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Checks if FFmpeg and FFprobe binaries are operational.
        Returns:
            Tuple of (is_healthy: bool, ffmpeg_version: Optional[str], details: Optional[str])
        """
        pass
