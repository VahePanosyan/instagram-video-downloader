"""Headless tests for PySide6 GUI components with YouTube support."""

import pytest
from PySide6.QtWidgets import QApplication
from src.gui.app import MainWindow
from src.gui.components.url_input import SingleUrlWidget
from src.gui.components.batch_tab import BatchTabWidget
from src.gui.components.history_tab import HistoryTabWidget
from src.domain.models import (
    QualityOption,
    Platform,
    MediaType,
    MediaItem,
    DownloadHistoryItem,
)
from src.use_cases.download_media import DownloadMediaUseCase
from src.use_cases.extract_metadata import ExtractMetadataUseCase
from src.ports.downloader import IDownloader
from src.ports.extractor import IExtractor


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_single_url_widget_youtube(qapp):
    widget = SingleUrlWidget()
    emitted = []
    widget.download_requested.connect(lambda u, q: emitted.append((u, q)))

    # YouTube standard video
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    widget.url_input.setText(yt_url)
    widget.combo_quality.setCurrentIndex(0)  # Best
    widget._on_download_click()

    assert len(emitted) == 1
    assert emitted[0][0] == yt_url
    assert emitted[0][1] == QualityOption.BEST

    # YouTube Shorts
    emitted.clear()
    shorts_url = "https://www.youtube.com/shorts/3fDkJ2hZ91A"
    widget.url_input.setText(shorts_url)
    widget.combo_quality.setCurrentIndex(1)  # 1080p
    widget._on_download_click()

    assert len(emitted) == 1
    assert emitted[0][0] == shorts_url
    assert emitted[0][1] == QualityOption.Q_1080P


def test_single_url_widget_youtube_preview(qapp):
    widget = SingleUrlWidget()
    widget.show()
    item = MediaItem(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        shortcode="dQw4w9WgXcQ",
        platform=Platform.YOUTUBE,
        media_type=MediaType.VIDEO,
        title="Rick Astley - Never Gonna Give You Up",
        author="RickAstleyVEVO",
        duration_seconds=212,
    )

    widget.display_media_preview(item)
    assert not widget.preview_card.isHidden()
    assert widget.lbl_media_title.text() == "Rick Astley - Never Gonna Give You Up"
    assert "Channel: RickAstleyVEVO" in widget.lbl_media_author.text()
    assert "YOUTUBE" in widget.lbl_media_meta.text()
    assert "3:32" in widget.lbl_media_meta.text()


def test_batch_tab_widget_youtube(qapp):
    widget = BatchTabWidget()
    widget.txt_urls.setPlainText(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
        "https://www.youtube.com/shorts/3fDkJ2hZ91A\n"
        "https://www.instagram.com/reel/C2-7XYZ1234/\n"
        "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf\n"
        "https://invalid-domain.com/video\n"
    )
    valid = widget._get_valid_urls()
    assert len(valid) == 4

    emitted = []
    widget.batch_add_requested.connect(lambda urls, q: emitted.append((urls, q)))
    widget._on_add_to_queue()
    assert len(emitted) == 1
    assert len(emitted[0][0]) == 4


def test_history_tab_widget_youtube_search(qapp):
    widget = HistoryTabWidget()
    items = [
        DownloadHistoryItem("h1", "url1", "Python Crash Course", "TechChannel", "/path/1.mp4", 1000000, "1080p", "2026-11-01", platform="youtube"),
        DownloadHistoryItem("h2", "url2", "Sunset Reel", "travel_insta", "/path/2.mp4", 2000000, "best", "2026-11-01", platform="instagram"),
    ]
    widget.load_history(items)
    assert widget.table.rowCount() == 2

    # Search by platform
    widget._on_search_text_changed("youtube")
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "Python Crash Course"

    # Search by creator
    widget._on_search_text_changed("TechChannel")
    assert widget.table.rowCount() == 1

    # Reset search
    widget._on_search_text_changed("")
    assert widget.table.rowCount() == 2


def test_main_window_playlist_routing_to_batch(qapp, tmp_path):
    class FakeExtractor(IExtractor):
        def extract_info(self, url, settings=None):
            return MediaItem(
                url=url,
                shortcode="PL999",
                platform=Platform.YOUTUBE,
                media_type=MediaType.PLAYLIST,
                is_playlist=True,
                title="Electronic Beats",
                playlist_urls=[
                    "https://www.youtube.com/watch?v=0VH1Lim8gL8",
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                ],
            )

    class FakeDownloader(IDownloader):
        def download(self, request, settings, progress_callback=None, cancel_event=None):
            return str(tmp_path / "track.mp4")

    fake_downloader = FakeDownloader()
    window = MainWindow()
    window._metadata_use_case = ExtractMetadataUseCase(FakeExtractor())
    window._single_download_use_case = DownloadMediaUseCase(fake_downloader, window._history_repo)
    window._batch_use_case._downloader = fake_downloader
    window._batch_use_case._single_download_use_case = DownloadMediaUseCase(fake_downloader, window._history_repo)

    # Set URL in single tab
    pl_url = "https://www.youtube.com/playlist?list=PL999"
    window.tab_single.url_input.setText(pl_url)
    window.tab_single._on_inspect_click()

    # Wait for metadata
    assert window._meta_worker is not None
    window._meta_worker.wait(5000)
    qapp.processEvents()

    # Now click download in Single tab: should detect playlist and route to batch queue tab
    window.tab_single._on_download_click()
    qapp.processEvents()

    # Verify queue now has the 2 tracks from the playlist
    assert window.tabs.currentIndex() == 2  # Active Queue tab
    queue_requests = window._batch_use_case.get_all_requests()
    assert len(queue_requests) == 2
    assert queue_requests[0].url == "https://www.youtube.com/watch?v=0VH1Lim8gL8"
    assert queue_requests[1].url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
