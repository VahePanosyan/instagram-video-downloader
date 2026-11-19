"""Unit tests for application use cases."""

import threading
import time
from pathlib import Path
from typing import Optional, Callable
from src.domain.models import (
    MediaItem,
    MediaType,
    DownloadRequest,
    DownloadStatus,
    DownloadProgress,
    AppSettings,
    QualityOption,
    DownloadHistoryItem,
)
from src.ports.extractor import IExtractor
from src.ports.downloader import IDownloader
from src.ports.repository import IHistoryRepository, ISettingsRepository
from src.use_cases.extract_metadata import ExtractMetadataUseCase
from src.use_cases.download_media import DownloadMediaUseCase
from src.use_cases.batch_downloader import BatchDownloaderUseCase
from src.use_cases.manage_history import ManageHistoryUseCase
from src.use_cases.manage_settings import ManageSettingsUseCase


class MockExtractor(IExtractor):
    def __init__(self):
        self.call_count = 0

    def extract_info(self, url: str, settings: Optional[AppSettings] = None) -> MediaItem:
        self.call_count += 1
        return MediaItem(
            url=url,
            shortcode="test_code",
            media_type=MediaType.REEL,
            title="Sample Reel Title",
            author="tester",
            duration_seconds=30,
        )


class MockDownloader(IDownloader):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.downloaded_count = 0

    def download(
        self,
        request: DownloadRequest,
        settings: AppSettings,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> str:
        if self.should_fail:
            raise RuntimeError("Network simulated failure")

        if progress_callback:
            progress_callback(DownloadProgress(percent=50.0, status_message="Halfway"))
            progress_callback(DownloadProgress(percent=100.0, status_message="Done"))

        self.downloaded_count += 1
        return f"{settings.download_dir}/tester_test_code.mp4"


class InMemoryHistoryRepository(IHistoryRepository):
    def __init__(self):
        self.items = []

    def get_all(self):
        return list(self.items)

    def add(self, item: DownloadHistoryItem):
        self.items.insert(0, item)

    def remove(self, item_id: str) -> bool:
        initial = len(self.items)
        self.items = [x for x in self.items if x.id != item_id]
        return len(self.items) < initial

    def clear(self):
        self.items.clear()


class InMemorySettingsRepository(ISettingsRepository):
    def __init__(self):
        self.settings = AppSettings()

    def load(self) -> AppSettings:
        return self.settings

    def save(self, settings: AppSettings) -> None:
        self.settings = settings


def test_extract_metadata_use_case_caching():
    extractor = MockExtractor()
    use_case = ExtractMetadataUseCase(extractor, cache_ttl_seconds=60)

    url = "https://www.instagram.com/reel/C2-7XYZ1234/"
    item1 = use_case.execute(url)
    assert item1.shortcode == "test_code"
    assert extractor.call_count == 1

    # Second call should hit cache and not call extractor again
    item2 = use_case.execute(url)
    assert item2.shortcode == "test_code"
    assert extractor.call_count == 1

    # Force refresh bypasses cache
    item3 = use_case.execute(url, force_refresh=True)
    assert item3.shortcode == "test_code"
    assert extractor.call_count == 2


def test_download_media_use_case_success(tmp_path):
    downloader = MockDownloader()
    history_repo = InMemoryHistoryRepository()
    use_case = DownloadMediaUseCase(downloader, history_repo)

    # Create dummy file to simulate downloaded file for size calculation
    dummy_file = tmp_path / "tester_test_code.mp4"
    dummy_file.write_text("dummy video content")

    settings = AppSettings(download_dir=str(tmp_path))
    req = DownloadRequest(
        url="https://www.instagram.com/reel/test_code/",
        media_item=MediaItem(
            url="https://www.instagram.com/reel/test_code/",
            shortcode="test_code",
            title="Video 1",
            author="tester",
        ),
    )

    saved_path = use_case.execute(req, settings)
    assert req.status == DownloadStatus.COMPLETED
    assert Path(saved_path) == dummy_file
    assert len(history_repo.get_all()) == 1


def test_batch_downloader_use_case(tmp_path):
    downloader = MockDownloader()
    extractor = MockExtractor()
    history_repo = InMemoryHistoryRepository()
    meta_use_case = ExtractMetadataUseCase(extractor)

    batch_use_case = BatchDownloaderUseCase(
        downloader=downloader,
        metadata_use_case=meta_use_case,
        history_repo=history_repo,
    )

    urls = [
        "https://www.instagram.com/reel/ABC111/",
        "https://www.instagram.com/reel/ABC222/",
        "https://www.instagram.com/reel/ABC111/",  # duplicate, should be skipped
        "invalid_not_a_url",                     # invalid, should be skipped
    ]

    settings = AppSettings(download_dir=str(tmp_path), concurrent_downloads=2)
    added = batch_use_case.add_urls(urls, settings)
    assert len(added) == 2

    done_event = threading.Event()
    batch_use_case.on_batch_finished = lambda: done_event.set()

    batch_use_case.start(settings)
    assert done_event.wait(timeout=5.0)

    requests = batch_use_case.get_all_requests()
    assert all(r.status == DownloadStatus.COMPLETED for r in requests)
    assert downloader.downloaded_count == 2


def test_manage_history_use_case():
    repo = InMemoryHistoryRepository()
    use_case = ManageHistoryUseCase(repo)

    repo.add(DownloadHistoryItem(
        id="1", url="url1", title="Funny Cats", author="cat_lover",
        file_path="/cat.mp4", file_size_bytes=1000, quality="best", downloaded_at="2026-11-01"
    ))
    repo.add(DownloadHistoryItem(
        id="2", url="url2", title="Cooking Pizza", author="chef_mario",
        file_path="/pizza.mp4", file_size_bytes=2000, quality="1080p", downloaded_at="2026-11-01"
    ))

    assert len(use_case.get_history()) == 2
    assert len(use_case.search_history("cats")) == 1
    assert len(use_case.search_history("mario")) == 1
    assert len(use_case.search_history("nonexistent")) == 0

    assert use_case.remove_item("1") is True
    assert len(use_case.get_history()) == 1

    use_case.clear_history()
    assert len(use_case.get_history()) == 0


def test_manage_settings_use_case():
    repo = InMemorySettingsRepository()
    use_case = ManageSettingsUseCase(repo)

    current = use_case.get_settings()
    assert current.concurrent_downloads == 3

    new_settings = AppSettings(concurrent_downloads=6, default_quality=QualityOption.AUDIO_MP3)
    updated = use_case.update_settings(new_settings)
    assert updated.concurrent_downloads == 6
    assert updated.default_quality == QualityOption.AUDIO_MP3


def test_batch_downloader_subsequent_run_and_dynamic_add(tmp_path):
    class SlowMockDownloader(MockDownloader):
        def download(self, *args, **kwargs):
            time.sleep(0.05)
            return super().download(*args, **kwargs)

    downloader = SlowMockDownloader()
    extractor = MockExtractor()
    history_repo = InMemoryHistoryRepository()
    meta_use_case = ExtractMetadataUseCase(extractor)

    batch_use_case = BatchDownloaderUseCase(
        downloader=downloader,
        metadata_use_case=meta_use_case,
        history_repo=history_repo,
    )
    settings = AppSettings(download_dir=str(tmp_path), concurrent_downloads=2)

    # Batch 1
    batch_use_case.add_urls(["https://www.instagram.com/reel/BATCH1_A/"], settings)
    ev1 = threading.Event()
    batch_use_case.on_batch_finished = lambda: ev1.set()
    batch_use_case.start(settings)

    # Dynamic add while Batch 1 is running
    batch_use_case.add_urls(["https://www.instagram.com/reel/BATCH1_B/"], settings)

    assert ev1.wait(timeout=5.0)
    assert not batch_use_case.is_running
    assert len(batch_use_case.get_all_requests()) == 2
    assert all(r.status == DownloadStatus.COMPLETED for r in batch_use_case.get_all_requests())

    # Batch 2 (subsequent run after completion)
    batch_use_case.add_urls(["https://www.instagram.com/reel/BATCH2_A/"], settings)
    ev2 = threading.Event()
    batch_use_case.on_batch_finished = lambda: ev2.set()
    batch_use_case.start(settings)

    assert ev2.wait(timeout=5.0)
    assert not batch_use_case.is_running
    assert len(batch_use_case.get_all_requests()) == 3
    assert all(r.status == DownloadStatus.COMPLETED for r in batch_use_case.get_all_requests())


def test_extract_metadata_fallback_scraper():
    class FailingExtractor(IExtractor):
        def extract_info(self, url: str, settings: Optional[AppSettings] = None) -> MediaItem:
            raise RuntimeError("Rate limited / blocked")

    class MockFallbackScraper:
        def quick_preview(self, url: str) -> MediaItem:
            return MediaItem(
                url=url,
                shortcode="fallback_code",
                title="Fallback Scraped Title",
                author="fallback_user",
            )

    use_case = ExtractMetadataUseCase(
        extractor=FailingExtractor(),
        fallback_scraper=MockFallbackScraper(),
    )

    url = "https://www.instagram.com/reel/XYZ999/"
    item = use_case.execute(url)
    assert item.title == "Fallback Scraped Title"
    assert item.author == "fallback_user"
    assert use_case.get_cached(url) is not None


def test_batch_downloader_pre_cancelled_item_skips_fetch(tmp_path):
    class TrackingExtractor(MockExtractor):
        def __init__(self):
            super().__init__()
            self.extracted_urls = []

        def extract_info(self, url: str, settings: Optional[AppSettings] = None) -> MediaItem:
            self.extracted_urls.append(url)
            return super().extract_info(url, settings)

    extractor = TrackingExtractor()
    downloader = MockDownloader()
    history_repo = InMemoryHistoryRepository()
    meta_use_case = ExtractMetadataUseCase(extractor)

    batch_use_case = BatchDownloaderUseCase(
        downloader=downloader,
        metadata_use_case=meta_use_case,
        history_repo=history_repo,
    )
    settings = AppSettings(download_dir=str(tmp_path), concurrent_downloads=1)

    urls = [
        "https://www.instagram.com/reel/ITEM_TO_CANCEL/",
    ]
    added = batch_use_case.add_urls(urls, settings)
    assert len(added) == 1
    req_id = added[0].id

    # Pre-cancel item before worker runs
    batch_use_case.cancel_item(req_id)
    assert added[0].status == DownloadStatus.CANCELLED

    done_event = threading.Event()
    batch_use_case.on_batch_finished = lambda: done_event.set()
    batch_use_case.start(settings)

    assert done_event.wait(timeout=5.0)
    # The pre-cancelled item should NOT have its metadata extracted
    assert "https://www.instagram.com/reel/ITEM_TO_CANCEL/" not in extractor.extracted_urls
    assert added[0].status == DownloadStatus.CANCELLED


def test_batch_downloader_item_failure_handling(tmp_path):
    downloader = MockDownloader(should_fail=True)
    extractor = MockExtractor()
    history_repo = InMemoryHistoryRepository()
    meta_use_case = ExtractMetadataUseCase(extractor)

    batch_use_case = BatchDownloaderUseCase(
        downloader=downloader,
        metadata_use_case=meta_use_case,
        history_repo=history_repo,
    )
    settings = AppSettings(download_dir=str(tmp_path), concurrent_downloads=2)

    added = batch_use_case.add_urls(["https://www.instagram.com/reel/FAIL_ITEM/"], settings)
    assert len(added) == 1

    done_event = threading.Event()
    batch_use_case.on_batch_finished = lambda: done_event.set()
    batch_use_case.start(settings)

    assert done_event.wait(timeout=5.0)
    req = added[0]
    assert req.status == DownloadStatus.FAILED
    assert "Network simulated failure" in (req.error_message or "")


def test_download_media_use_case_with_string_quality(tmp_path):
    downloader = MockDownloader()
    history_repo = InMemoryHistoryRepository()
    use_case = DownloadMediaUseCase(downloader, history_repo)

    dummy_file = tmp_path / "tester_test_code.mp4"
    dummy_file.write_text("dummy video content")

    settings = AppSettings(download_dir=str(tmp_path))
    req = DownloadRequest(
        url="https://www.instagram.com/reel/test_code/",
        media_item=MediaItem(
            url="https://www.instagram.com/reel/test_code/",
            shortcode="test_code",
            title="Video 1",
            author="tester",
        ),
    )
    # Simulate quality being set as a plain str (e.g. from UI or untyped caller)
    object.__setattr__(req, "quality", "best")

    saved_path = use_case.execute(req, settings)
    assert req.status == DownloadStatus.COMPLETED
    assert Path(saved_path) == dummy_file
    items = history_repo.get_all()
    assert len(items) == 1
    assert items[0].quality == "best"
