"""Unit tests for use cases with YouTube media (Videos, Shorts, Playlists, Batch)."""

import threading
from pathlib import Path
from typing import Optional, Callable
from src.domain.models import (
    MediaItem,
    MediaType,
    Platform,
    DownloadRequest,
    DownloadStatus,
    DownloadProgress,
    AppSettings,
    QualityOption,
    DownloadHistoryItem,
)
from src.ports.extractor import IExtractor
from src.ports.downloader import IDownloader
from src.ports.repository import IHistoryRepository
from src.use_cases.extract_metadata import ExtractMetadataUseCase
from src.use_cases.download_media import DownloadMediaUseCase
from src.use_cases.batch_downloader import BatchDownloaderUseCase


class MockYouTubeExtractor(IExtractor):
    def __init__(self):
        self.call_count = 0

    def extract_info(self, url: str, settings: Optional[AppSettings] = None) -> MediaItem:
        self.call_count += 1
        if "playlist" in url or "list=" in url:
            return MediaItem(
                url=url,
                shortcode="PL123",
                media_type=MediaType.PLAYLIST,
                platform=Platform.YOUTUBE,
                title="Awesome Synthwave Playlist",
                author="SynthMaster",
                is_playlist=True,
                playlist_urls=[
                    "https://www.youtube.com/watch?v=track_1",
                    "https://www.youtube.com/watch?v=track_2",
                    "https://www.youtube.com/watch?v=track_3",
                ],
            )
        elif "shorts" in url:
            return MediaItem(
                url=url,
                shortcode="short_123",
                media_type=MediaType.SHORT,
                platform=Platform.YOUTUBE,
                title="Funny Cat Short",
                author="CatChannel",
                duration_seconds=30,
            )
        else:
            return MediaItem(
                url=url,
                shortcode="video_123",
                media_type=MediaType.VIDEO,
                platform=Platform.YOUTUBE,
                title="Epic Coding Tutorial",
                author="DevPro",
                duration_seconds=600,
            )


class MockYouTubeDownloader(IDownloader):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.downloaded_count = 0
        self.downloaded_urls: list[str] = []

    def download(
        self,
        request: DownloadRequest,
        settings: AppSettings,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> str:
        if self.should_fail:
            raise RuntimeError("YouTube bot verification simulated error")

        if progress_callback:
            progress_callback(DownloadProgress(percent=50.0, status_message="Downloading"))
            progress_callback(DownloadProgress(percent=100.0, status_message="Finished"))

        self.downloaded_count += 1
        self.downloaded_urls.append(request.url)
        return f"{settings.download_dir}/{request.media_item.shortcode if request.media_item else 'video'}.mp4"


class InMemoryHistoryRepo(IHistoryRepository):
    def __init__(self):
        self.items = []

    def get_all(self):
        return list(self.items)

    def add(self, item: DownloadHistoryItem):
        self.items.insert(0, item)

    def remove(self, item_id: str) -> bool:
        init_len = len(self.items)
        self.items = [it for it in self.items if it.id != item_id]
        return len(self.items) < init_len

    def clear(self):
        self.items.clear()


def test_youtube_extract_metadata_use_case_caching():
    extractor = MockYouTubeExtractor()
    use_case = ExtractMetadataUseCase(extractor, cache_ttl_seconds=60)

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    item1 = use_case.execute(url)
    assert item1.shortcode == "video_123"
    assert item1.platform == Platform.YOUTUBE
    assert extractor.call_count == 1

    # Second call hits cache
    item2 = use_case.execute(url)
    assert item2.title == "Epic Coding Tutorial"
    assert extractor.call_count == 1

    # YouTube Shorts caching
    shorts_url = "https://www.youtube.com/shorts/3fDkJ2hZ91A"
    item_short = use_case.execute(shorts_url)
    assert item_short.media_type == MediaType.SHORT
    assert item_short.author == "CatChannel"
    assert extractor.call_count == 2


def test_youtube_download_media_use_case(tmp_path):
    downloader = MockYouTubeDownloader()
    history_repo = InMemoryHistoryRepo()
    use_case = DownloadMediaUseCase(downloader, history_repo)

    dummy_file = tmp_path / "video_123.mp4"
    dummy_file.write_text("dummy youtube content")

    settings = AppSettings(download_dir=str(tmp_path))
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=video_123",
        media_item=MediaItem(
            url="https://www.youtube.com/watch?v=video_123",
            shortcode="video_123",
            platform=Platform.YOUTUBE,
            title="Epic Coding Tutorial",
            author="DevPro",
        ),
        quality=QualityOption.Q_1080P,
    )

    saved_path = use_case.execute(req, settings)
    assert req.status == DownloadStatus.COMPLETED
    assert Path(saved_path) == dummy_file

    history = history_repo.get_all()
    assert len(history) == 1
    assert history[0].platform == "youtube"
    assert history[0].author == "DevPro"
    assert history[0].title == "Epic Coding Tutorial"


def test_youtube_batch_downloader_mixed_platforms(tmp_path):
    downloader = MockYouTubeDownloader()
    extractor = MockYouTubeExtractor()
    history_repo = InMemoryHistoryRepo()
    meta_use_case = ExtractMetadataUseCase(extractor)

    batch_use_case = BatchDownloaderUseCase(
        downloader=downloader,
        metadata_use_case=meta_use_case,
        history_repo=history_repo,
    )

    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/3fDkJ2hZ91A",
        "https://www.instagram.com/reel/C2-7XYZ1234/",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # duplicate, skip
    ]

    settings = AppSettings(download_dir=str(tmp_path), concurrent_downloads=3)
    added = batch_use_case.add_urls(urls, settings)
    assert len(added) == 3

    done_event = threading.Event()
    batch_use_case.on_batch_finished = lambda: done_event.set()
    batch_use_case.start(settings)

    assert done_event.wait(timeout=5.0)
    assert len(batch_use_case.get_all_requests()) == 3
    assert downloader.downloaded_count == 3


def test_youtube_playlist_expansion_in_batch(tmp_path):
    downloader = MockYouTubeDownloader()
    extractor = MockYouTubeExtractor()
    history_repo = InMemoryHistoryRepo()
    meta_use_case = ExtractMetadataUseCase(extractor)

    batch_use_case = BatchDownloaderUseCase(
        downloader=downloader,
        metadata_use_case=meta_use_case,
        history_repo=history_repo,
    )

    settings = AppSettings(download_dir=str(tmp_path), concurrent_downloads=2)

    # Expand playlist into individual requests
    added = batch_use_case.add_playlist(
        "https://www.youtube.com/playlist?list=PL123",
        settings,
        quality=QualityOption.AUDIO_MP3,
    )
    assert len(added) == 3
    assert all(r.quality == QualityOption.AUDIO_MP3 for r in added)
    assert added[0].url == "https://www.youtube.com/watch?v=track_1"
    assert added[1].url == "https://www.youtube.com/watch?v=track_2"
    assert added[2].url == "https://www.youtube.com/watch?v=track_3"

    done_event = threading.Event()
    batch_use_case.on_batch_finished = lambda: done_event.set()
    batch_use_case.start(settings)

    assert done_event.wait(timeout=5.0)
    assert downloader.downloaded_count == 3
    assert "https://www.youtube.com/watch?v=track_1" in downloader.downloaded_urls
