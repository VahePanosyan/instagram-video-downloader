"""Tests for Queue 2.0: Pause, Resume, Reordering, and Duplicate checking."""

from unittest.mock import MagicMock
from src.use_cases.batch_downloader import BatchDownloaderUseCase
from src.domain.models import AppSettings, DownloadRequest, QualityOption, DownloadHistoryItem


def test_queue_pause_and_resume():
    mock_downloader = MagicMock()
    mock_meta = MagicMock()
    use_case = BatchDownloaderUseCase(mock_downloader, mock_meta)

    assert not use_case.is_paused
    use_case.pause()
    assert use_case.is_paused
    assert not use_case._pause_event.is_set()

    use_case.resume()
    assert not use_case.is_paused
    assert use_case._pause_event.is_set()


def test_queue_reorder_items():
    mock_downloader = MagicMock()
    mock_meta = MagicMock()
    use_case = BatchDownloaderUseCase(mock_downloader, mock_meta)
    settings = AppSettings()

    r1 = DownloadRequest(url="https://www.youtube.com/watch?v=11111111111", id="r1")
    r2 = DownloadRequest(url="https://www.youtube.com/watch?v=22222222222", id="r2")
    r3 = DownloadRequest(url="https://www.youtube.com/watch?v=33333333333", id="r3")

    use_case._requests = {"r1": r1, "r2": r2, "r3": r3}

    # Move r2 up
    assert use_case.move_item_up("r2") is True
    assert [r.id for r in use_case.get_all_requests()] == ["r2", "r1", "r3"]

    # Moving top item up should return False
    assert use_case.move_item_up("r2") is False

    # Move r2 down
    assert use_case.move_item_down("r2") is True
    assert [r.id for r in use_case.get_all_requests()] == ["r1", "r2", "r3"]

    # Move r3 down (already at bottom) should return False
    assert use_case.move_item_down("r3") is False


def test_queue_duplicate_detection():
    mock_downloader = MagicMock()
    mock_meta = MagicMock()
    mock_history = MagicMock()
    mock_history.get_all.return_value = [
        DownloadHistoryItem(
            id="h1",
            url="https://www.youtube.com/watch?v=HIST1234567",
            title="Old Video",
            author="Author",
            file_path="video.mp4",
            file_size_bytes=1000,
            quality="1080p",
            downloaded_at="2026-01-01",
        )
    ]

    use_case = BatchDownloaderUseCase(mock_downloader, mock_meta, history_repo=mock_history)
    r1 = DownloadRequest(url="https://www.youtube.com/watch?v=QUEUE123456", id="q1")
    use_case._requests = {"q1": r1}

    # Active queue duplicate
    assert use_case.is_duplicate("https://www.youtube.com/watch?v=QUEUE123456") is True
    # History duplicate
    assert use_case.is_duplicate("https://www.youtube.com/watch?v=HIST1234567") is True
    # Non duplicate
    assert use_case.is_duplicate("https://www.youtube.com/watch?v=NEW_VIDEO99") is False
