"""Downloader port interface."""

from abc import ABC, abstractmethod
from typing import Callable, Optional
import threading
from ..domain.models import DownloadRequest, DownloadProgress, AppSettings


class IDownloader(ABC):
    """Port for downloading media from Instagram and YouTube."""

    @abstractmethod
    def download(
        self,
        request: DownloadRequest,
        settings: AppSettings,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> str:
        """
        Executes download of requested media.
        Returns the absolute filepath of the saved file.
        Raises DownloadException on error.
        """
        pass
