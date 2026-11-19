"""Batch downloader use case managing concurrent download queues."""

import threading
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future

from ..domain.models import (
    DownloadRequest,
    DownloadStatus,
    DownloadProgress,
    AppSettings,
    QualityOption,
    MediaType,
    Platform,
)
from ..domain.url_parser import MediaUrlParser, YouTubeUrlParser
from ..ports.downloader import IDownloader
from ..ports.repository import IHistoryRepository
from .download_media import DownloadMediaUseCase
from .extract_metadata import ExtractMetadataUseCase


class BatchDownloaderUseCase:
    """Manages concurrent download execution queue with worker pool for Instagram & YouTube."""

    def __init__(
        self,
        downloader: IDownloader,
        metadata_use_case: ExtractMetadataUseCase,
        history_repo: Optional[IHistoryRepository] = None,
    ):
        self._downloader = downloader
        self._metadata_use_case = metadata_use_case
        self._history_repo = history_repo
        self._single_download_use_case = DownloadMediaUseCase(downloader, history_repo)

        self._requests: Dict[str, DownloadRequest] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._is_running = False
        self._is_paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._active_futures: Dict[str, Future] = {}

        # Callbacks
        self.on_item_updated: Optional[Callable[[DownloadRequest], None]] = None
        self.on_item_progress: Optional[Callable[[DownloadRequest, DownloadProgress], None]] = None
        self.on_batch_finished: Optional[Callable[[], None]] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._is_paused

    def pause(self) -> None:
        """Pauses execution of queued download tasks."""
        with self._lock:
            self._is_paused = True
            self._pause_event.clear()

    def resume(self) -> None:
        """Resumes execution of queued download tasks."""
        with self._lock:
            self._is_paused = False
            self._pause_event.set()

    def move_item_up(self, request_id: str) -> bool:
        """Moves an item up in the queue order."""
        with self._lock:
            items = list(self._requests.items())
            idx = next((i for i, (k, _) in enumerate(items) if k == request_id), -1)
            if idx <= 0:
                return False
            items[idx - 1], items[idx] = items[idx], items[idx - 1]
            self._requests = dict(items)
            return True

    def move_item_down(self, request_id: str) -> bool:
        """Moves an item down in the queue order."""
        with self._lock:
            items = list(self._requests.items())
            idx = next((i for i, (k, _) in enumerate(items) if k == request_id), -1)
            if idx == -1 or idx >= len(items) - 1:
                return False
            items[idx + 1], items[idx] = items[idx], items[idx + 1]
            self._requests = dict(items)
            return True

    def is_duplicate(self, url: str) -> bool:
        """Checks if a URL has already been downloaded or is currently active in the queue."""
        with self._lock:
            for req in self._requests.values():
                if req.url == url or (req.media_item and req.media_item.url == url):
                    return True
            if self._history_repo:
                try:
                    for h_item in self._history_repo.get_all():
                        if h_item.url == url:
                            return True
                except Exception:
                    pass
            return False

    def add_urls(
        self,
        urls: List[str],
        settings: AppSettings,
        quality: Optional[QualityOption] = None,
        expand_playlists: bool = True,
    ) -> List[DownloadRequest]:
        """Parses a list of URLs and adds valid new requests to queue. If expand_playlists is True, YouTube playlists are expanded into individual video items."""
        added_requests: List[DownloadRequest] = []
        target_quality = QualityOption.from_value(quality or settings.default_quality)

        with self._lock:
            for raw_url in urls:
                if not raw_url or not raw_url.strip():
                    continue
                try:
                    clean_raw = raw_url.strip()
                    extended_flag = getattr(settings, "enable_multi_platform", False)
                    platform, media_type, shortcode, canonical_url = MediaUrlParser.parse(clean_raw, extended=extended_flag)

                    # Check if it's a playlist or watch URL with a playlist ID
                    pl_id = (
                        YouTubeUrlParser.extract_playlist_id(clean_raw)
                        if platform == Platform.YOUTUBE
                        else None
                    )
                    is_pl = (media_type == MediaType.PLAYLIST) or bool(pl_id)

                    # If expand_playlists is requested and it's a playlist:
                    if expand_playlists and is_pl:
                        try:
                            pl_url = (
                                f"https://www.youtube.com/playlist?list={pl_id}"
                                if pl_id and media_type != MediaType.PLAYLIST
                                else canonical_url
                            )
                            meta = self._metadata_use_case.execute(pl_url, settings)
                            if meta and meta.playlist_urls:
                                for child_url in meta.playlist_urls:
                                    try:
                                        _, _, child_sc, child_canonical = MediaUrlParser.parse(child_url)
                                        exists = any(
                                            req.url == child_canonical and req.status in [DownloadStatus.QUEUED, DownloadStatus.FETCHING_INFO, DownloadStatus.DOWNLOADING]
                                            for req in self._requests.values()
                                        )
                                        if not exists:
                                            child_req = DownloadRequest(
                                                url=child_canonical,
                                                quality=target_quality,
                                                output_dir=settings.download_dir,
                                                filename_template=settings.filename_template,
                                            )
                                            self._requests[child_req.id] = child_req
                                            self._cancel_events[child_req.id] = threading.Event()
                                            added_requests.append(child_req)
                                    except Exception:
                                        continue
                                continue
                        except Exception:
                            # Fall through to add the playlist URL itself
                            pass

                    # Standard item or unexpanded playlist
                    exists = any(
                        req.url == canonical_url and req.status in [DownloadStatus.QUEUED, DownloadStatus.FETCHING_INFO, DownloadStatus.DOWNLOADING]
                        for req in self._requests.values()
                    )
                    if exists:
                        continue

                    req = DownloadRequest(
                        url=canonical_url,
                        quality=target_quality,
                        output_dir=settings.download_dir,
                        filename_template=settings.filename_template,
                    )
                    self._requests[req.id] = req
                    self._cancel_events[req.id] = threading.Event()
                    added_requests.append(req)
                except Exception:
                    # Skip invalid URLs in batch mode
                    continue

            # If queue is currently running, submit newly added items immediately
            if self._is_running and self._executor:
                for req in added_requests:
                    self._submit_request(req, settings)

        return added_requests

    def add_playlist(
        self,
        playlist_url: str,
        settings: AppSettings,
        quality: Optional[QualityOption] = None,
    ) -> List[DownloadRequest]:
        """Convenience method to expand and queue all videos from a playlist URL."""
        return self.add_urls([playlist_url], settings, quality=quality, expand_playlists=True)

    def start(self, settings: AppSettings) -> None:
        """Starts worker pool and processes queued items."""
        with self._lock:
            workers = max(1, min(settings.concurrent_downloads, 8))
            if not self._executor:
                self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="MediaWorker")
            self._is_running = True

            # Submit all queued items
            queued = [
                req for req in self._requests.values()
                if req.status == DownloadStatus.QUEUED
            ]
            for req in queued:
                self._submit_request(req, settings)

            if not queued and not self._active_futures:
                self._is_running = False
                if self.on_batch_finished:
                    self.on_batch_finished()

    def _submit_request(self, request: DownloadRequest, settings: AppSettings) -> None:
        if not self._executor or not self._is_running:
            return

        cancel_ev = self._cancel_events.get(request.id) or threading.Event()
        self._cancel_events[request.id] = cancel_ev

        def worker():
            try:
                # Check pre-cancellation before doing any work
                if cancel_ev.is_set() or request.status == DownloadStatus.CANCELLED:
                    request.status = DownloadStatus.CANCELLED
                    return

                # 1. Fetch metadata if not already present
                if not request.media_item:
                    request.status = DownloadStatus.FETCHING_INFO
                    if self.on_item_updated:
                        try:
                            self.on_item_updated(request)
                        except Exception:
                            pass

                    try:
                        request.media_item = self._metadata_use_case.execute(request.url, settings)
                    except Exception:
                        # Log but continue to let yt-dlp attempt direct extraction
                        pass

                if cancel_ev.is_set() or request.status == DownloadStatus.CANCELLED:
                    request.status = DownloadStatus.CANCELLED
                    return

                # Wait if queue is paused
                self._pause_event.wait()
                if cancel_ev.is_set() or request.status == DownloadStatus.CANCELLED:
                    request.status = DownloadStatus.CANCELLED
                    return

                # 2. Progress callback adapter
                def prog_cb(p: DownloadProgress):
                    request.progress = p
                    if self.on_item_progress:
                        try:
                            self.on_item_progress(request, p)
                        except Exception:
                            pass

                # 3. Execute download
                self._single_download_use_case.execute(
                    request=request,
                    settings=settings,
                    progress_callback=prog_cb,
                    cancel_event=cancel_ev,
                )

            except Exception as err:
                if request.status not in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED, DownloadStatus.FAILED]:
                    request.status = DownloadStatus.FAILED
                    request.error_message = str(err)
            finally:
                with self._lock:
                    self._active_futures.pop(request.id, None)
                    if self.on_item_updated:
                        try:
                            self.on_item_updated(request)
                        except Exception:
                            pass
                    self._check_batch_completion()

        future = self._executor.submit(worker)
        self._active_futures[request.id] = future

    def _check_batch_completion(self) -> None:
        # Check if all submitted or queued items have finished
        has_pending = any(
            req.status in [DownloadStatus.QUEUED, DownloadStatus.FETCHING_INFO, DownloadStatus.DOWNLOADING]
            for req in self._requests.values()
        )
        if not has_pending:
            self._is_running = False
            if self.on_batch_finished:
                try:
                    self.on_batch_finished()
                except Exception:
                    pass

    def cancel_item(self, request_id: str) -> None:
        """Cancels a specific download task."""
        with self._lock:
            if request_id in self._cancel_events:
                self._cancel_events[request_id].set()
            req = self._requests.get(request_id)
            if req and req.status in [DownloadStatus.QUEUED, DownloadStatus.FETCHING_INFO]:
                req.status = DownloadStatus.CANCELLED
                if self.on_item_updated:
                    self.on_item_updated(req)
                self._check_batch_completion()

    def cancel_all(self) -> None:
        """Cancels all pending and active download tasks."""
        with self._lock:
            for ev in self._cancel_events.values():
                ev.set()
            for req in self._requests.values():
                if req.status in [DownloadStatus.QUEUED, DownloadStatus.FETCHING_INFO, DownloadStatus.DOWNLOADING]:
                    req.status = DownloadStatus.CANCELLED
                    if self.on_item_updated:
                        self.on_item_updated(req)
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None
            self._is_running = False
            if self.on_batch_finished:
                self.on_batch_finished()

    def get_all_requests(self) -> List[DownloadRequest]:
        with self._lock:
            return list(self._requests.values())

    def clear_finished(self) -> None:
        """Removes completed, cancelled, or failed items from the active queue list."""
        with self._lock:
            to_remove = [
                req_id for req_id, req in self._requests.items()
                if req.status in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED, DownloadStatus.FAILED]
            ]
            for req_id in to_remove:
                self._requests.pop(req_id, None)
                self._cancel_events.pop(req_id, None)
