"""Notification and event port interface."""

from abc import ABC, abstractmethod
from ..domain.models import DownloadRequest, DownloadProgress


class IProgressNotifier(ABC):
    """Port for notifying UI / observer of download lifecycle events."""

    @abstractmethod
    def on_request_started(self, request: DownloadRequest) -> None:
        pass

    @abstractmethod
    def on_progress(self, request: DownloadRequest, progress: DownloadProgress) -> None:
        pass

    @abstractmethod
    def on_request_completed(self, request: DownloadRequest, file_path: str) -> None:
        pass

    @abstractmethod
    def on_request_failed(self, request: DownloadRequest, error_message: str) -> None:
        pass

    @abstractmethod
    def on_request_cancelled(self, request: DownloadRequest) -> None:
        pass
