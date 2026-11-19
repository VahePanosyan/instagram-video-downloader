"""PySide6 QThread workers for asynchronous non-blocking GUI execution."""

import re
import time
import threading
import urllib.request
from typing import Optional
from PySide6.QtCore import QThread, Signal, QObject
from ..domain.models import DownloadRequest, DownloadProgress, AppSettings, QualityOption
from ..use_cases.extract_metadata import ExtractMetadataUseCase
from ..use_cases.download_media import DownloadMediaUseCase
from ..use_cases.batch_downloader import BatchDownloaderUseCase


class ThumbnailLoaderWorker(QThread):
    """Asynchronously loads remote thumbnail image bytes without blocking the GUI."""
    loaded = Signal(bytes)
    failed = Signal()

    def __init__(self, url: str, parent: Optional[QObject] = None, proxy: Optional[str] = None):
        if isinstance(parent, str) and proxy is None:
            proxy = parent
            parent = None
        super().__init__(parent)
        self._url = url
        self._proxy = proxy

    def run(self):
        try:
            req = urllib.request.Request(self._url, headers={"User-Agent": "Mozilla/5.0"})
            if self._proxy and self._proxy.strip():
                p = self._proxy.strip()
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', p):
                    p = f"http://{p}"
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({'http': p, 'https': p})
                )
                with opener.open(req, timeout=8) as resp:
                    data = resp.read()
                    self.loaded.emit(data)
            else:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = resp.read()
                    self.loaded.emit(data)
        except Exception:
            self.failed.emit()


class ProxyTestWorker(QThread):
    """Asynchronously tests proxy connectivity against Instagram / YouTube endpoints."""
    result = Signal(bool, str)  # success: bool, message: str

    def __init__(self, proxy: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._proxy = proxy.strip()

    def run(self):
        if not self._proxy:
            self.result.emit(False, "No proxy URL specified.")
            return

        p = self._proxy
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', p):
            p = f"http://{p}"

        start_time = time.time()
        try:
            proxy_handler = urllib.request.ProxyHandler({'http': p, 'https': p})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(
                "https://www.instagram.com",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with opener.open(req, timeout=7) as resp:
                elapsed_ms = int((time.time() - start_time) * 1000)
                status_code = resp.getcode()
                self.result.emit(True, f"Connected ({elapsed_ms}ms, HTTP {status_code})")
        except Exception as exc:
            self.result.emit(False, f"Failed: {type(exc).__name__} ({str(exc)[:45]})")


class MetadataFetchWorker(QThread):
    """Asynchronously fetches metadata and thumbnail preview for an Instagram URL."""
    finished = Signal(object)  # MediaItem
    failed = Signal(str)

    def __init__(self, use_case: ExtractMetadataUseCase, url: str, settings: AppSettings, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._use_case = use_case
        self._url = url
        self._settings = settings

    def run(self):
        try:
            item = self._use_case.execute(self._url, settings=self._settings)
            self.finished.emit(item)
        except Exception as e:
            self.failed.emit(str(e))


class SingleDownloadWorker(QThread):
    """Asynchronously executes download for a single Instagram media request."""
    progress_updated = Signal(object)  # DownloadProgress
    download_finished = Signal(str)     # Filepath
    download_failed = Signal(str)

    def __init__(
        self,
        use_case: DownloadMediaUseCase,
        request: DownloadRequest,
        settings: AppSettings,
        parent: Optional[QObject] = None,
        metadata_use_case: Optional[ExtractMetadataUseCase] = None,
    ):
        super().__init__(parent)
        self._use_case = use_case
        self._request = request
        self._settings = settings
        self._metadata_use_case = metadata_use_case
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            self._request.quality = QualityOption.from_value(self._request.quality)
            # If metadata not yet populated, fetch it to guarantee proper naming and history
            if not self._request.media_item and self._metadata_use_case:
                try:
                    self._request.media_item = self._metadata_use_case.execute(
                        self._request.url, settings=self._settings
                    )
                except Exception:
                    pass

            def on_progress(p: DownloadProgress):
                self.progress_updated.emit(p)

            path = self._use_case.execute(
                request=self._request,
                settings=self._settings,
                progress_callback=on_progress,
                cancel_event=self._cancel_event,
            )
            self.download_finished.emit(path)
        except Exception as e:
            self.download_failed.emit(str(e))


class BatchQueueWorker(QThread):
    """Coordinates batch queue execution in background."""
    item_updated = Signal(object)        # DownloadRequest
    item_progress = Signal(str, object)  # req_id, DownloadProgress
    batch_finished = Signal()

    def __init__(
        self,
        batch_use_case: BatchDownloaderUseCase,
        settings: AppSettings,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._batch_use_case = batch_use_case
        self._settings = settings
        self._done_event = threading.Event()

        # Wire callbacks to Qt signals
        def on_updated(req):
            self.item_updated.emit(req)

        def on_prog(req, prog):
            self.item_progress.emit(req.id, prog)

        def on_done():
            self.batch_finished.emit()
            self._done_event.set()

        self._batch_use_case.on_item_updated = on_updated
        self._batch_use_case.on_item_progress = on_prog
        self._batch_use_case.on_batch_finished = on_done

    def stop(self):
        self._done_event.set()

    def run(self):
        self._done_event.clear()
        self._batch_use_case.start(self._settings)
        # Wait until the batch finishes or is cancelled
        self._done_event.wait()
