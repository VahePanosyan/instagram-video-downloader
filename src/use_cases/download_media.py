"""Use case for downloading a single Instagram media request."""

import os
import datetime
import threading
from typing import Optional, Callable
from pathlib import Path

from ..domain.models import (
    DownloadRequest,
    DownloadStatus,
    DownloadProgress,
    DownloadHistoryItem,
    AppSettings,
    QualityOption,
    enum_value,
)
from ..ports.downloader import IDownloader
from ..ports.repository import IHistoryRepository


class DownloadMediaUseCase:
    """Orchestrates single media download and history persistence."""

    def __init__(self, downloader: IDownloader, history_repo: Optional[IHistoryRepository] = None):
        self._downloader = downloader
        self._history_repo = history_repo

    def execute(
        self,
        request: DownloadRequest,
        settings: AppSettings,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> str:
        request.quality = QualityOption.from_value(request.quality)
        request.status = DownloadStatus.DOWNLOADING
        request.error_message = None

        try:
            saved_path = self._downloader.download(
                request=request,
                settings=settings,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )

            request.status = DownloadStatus.COMPLETED
            request.saved_filepath = saved_path
            request.finished_at = datetime.datetime.now().isoformat()

            # Record into history if repository available
            if self._history_repo and os.path.exists(saved_path):
                file_size = (
                    sum(f.stat().st_size for f in Path(saved_path).rglob("*") if f.is_file())
                    if os.path.isdir(saved_path)
                    else os.path.getsize(saved_path)
                )
                author = request.media_item.author if request.media_item else "Unknown"
                title = request.media_item.display_title if request.media_item else Path(saved_path).stem

                plat = (
                    enum_value(request.media_item.platform)
                    if request.media_item and hasattr(request.media_item, "platform")
                    else "instagram"
                )

                history_item = DownloadHistoryItem(
                    id=request.id,
                    url=request.url,
                    title=title,
                    author=author,
                    file_path=saved_path,
                    file_size_bytes=file_size,
                    quality=enum_value(request.quality),
                    downloaded_at=request.finished_at,
                    platform=plat,
                )
                self._history_repo.add(history_item)

            return saved_path

        except Exception as e:
            if cancel_event and cancel_event.is_set():
                request.status = DownloadStatus.CANCELLED
                request.error_message = "Cancelled by user"
            else:
                request.status = DownloadStatus.FAILED
                request.error_message = str(e)
            raise
