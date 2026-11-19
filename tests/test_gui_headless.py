"""Headless tests for PySide6 GUI components."""

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from src.gui.app import MainWindow
from src.gui.components.url_input import SingleUrlWidget
from src.gui.components.batch_tab import BatchTabWidget
from src.gui.components.queue_table import QueueTableWidget
from src.gui.components.history_tab import HistoryTabWidget
from src.gui.components.settings_tab import SettingsTabWidget
from src.domain.models import (
    AppSettings,
    QualityOption,
    DownloadRequest,
    DownloadStatus,
    DownloadHistoryItem,
    MediaItem,
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


def test_main_window_initialization(qapp):
    window = MainWindow()
    assert window.windowTitle() == "Instagram Video Downloader Pro"
    assert window.tabs.count() == 5
    assert window.tabs.tabText(0) == "📥 Single Downloader"
    assert window.tabs.tabText(1) == "🚀 Batch Processor"
    assert window.tabs.tabText(2) == "⚡ Active Queue"
    assert window.tabs.tabText(3) == "📜 History"
    assert window.tabs.tabText(4) == "⚙️ Settings"


def test_single_url_widget(qapp):
    widget = SingleUrlWidget()
    assert widget.combo_quality.count() == len(QualityOption)

    # Empty URL warning check
    widget.url_input.setText("")

    emitted = []
    widget.download_requested.connect(lambda u, q: emitted.append((u, q)))

    expected_options = [
        (0, QualityOption.BEST, "best"),
        (1, QualityOption.Q_1080P, "1080p"),
        (2, QualityOption.Q_720P, "720p"),
        (3, QualityOption.Q_480P, "480p"),
        (4, QualityOption.AUDIO_MP3, "mp3"),
        (5, QualityOption.AUDIO_M4A, "m4a"),
    ]

    for index, expected_opt, expected_str in expected_options:
        emitted.clear()
        widget.url_input.setText("https://www.instagram.com/reel/C2-7XYZ1234/")
        widget.combo_quality.setCurrentIndex(index)
        widget._on_download_click()

        assert len(emitted) == 1
        assert emitted[0][0] == "https://www.instagram.com/reel/C2-7XYZ1234/"
        assert isinstance(emitted[0][1], QualityOption)
        assert emitted[0][1] == expected_opt
        assert emitted[0][1].value == expected_str

    # Test fallback to currentText when currentData is None
    widget.combo_quality.setItemData(1, None)
    widget.combo_quality.setCurrentIndex(1)
    emitted.clear()
    widget.url_input.setText("https://www.instagram.com/reel/C2-7XYZ1234/")
    widget._on_download_click()
    assert len(emitted) == 1
    assert emitted[0][1] == QualityOption.Q_1080P


def test_batch_tab_widget(qapp):
    widget = BatchTabWidget()
    widget.txt_urls.setPlainText(
        "https://www.instagram.com/reel/C2-7XYZ1234/\n"
        "not_valid_url\n"
        "https://www.instagram.com/p/B123_abcXYZ/\n"
    )
    valid = widget._get_valid_urls()
    assert len(valid) == 2

    emitted = []
    widget.batch_add_requested.connect(lambda urls, q: emitted.append((urls, q)))
    widget._on_add_to_queue()
    assert len(emitted) == 1
    assert len(emitted[0][0]) == 2
    assert isinstance(emitted[0][1], QualityOption)
    assert widget.txt_urls.toPlainText() == ""


def test_queue_table_widget(qapp):
    widget = QueueTableWidget()
    req1 = DownloadRequest(url="https://www.instagram.com/reel/111/", id="r1")
    req2 = DownloadRequest(url="https://www.instagram.com/reel/222/", id="r2", status=DownloadStatus.COMPLETED)
    # req3 has plain strings forced onto quality and status
    req3 = DownloadRequest(url="https://www.instagram.com/reel/333/", id="r3")
    object.__setattr__(req3, "quality", "1080p")
    object.__setattr__(req3, "status", "failed")

    widget.update_requests([req1, req2, req3])
    assert widget.table.rowCount() == 3
    assert "Total: 3" in widget.lbl_queue_stats.text()


def test_history_tab_widget(qapp):
    widget = HistoryTabWidget()
    items = [
        DownloadHistoryItem("h1", "url1", "Sunset in Paris", "traveler", "/path/1.mp4", 1048576, "best", "2026-11-01"),
        DownloadHistoryItem("h2", "url2", "Cute Puppy", "dog_lover", "/path/2.mp4", 2097152, "1080p", "2026-11-01"),
    ]
    widget.load_history(items)
    assert widget.table.rowCount() == 2

    # Search filter
    widget._on_search_text_changed("puppy")
    assert widget.table.rowCount() == 1

    widget._on_search_text_changed("")
    assert widget.table.rowCount() == 2


def test_settings_tab_widget(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)

    widget = SettingsTabWidget()
    settings = AppSettings(
        download_dir="C:/TestDownloads",
        concurrent_downloads=5,
        default_quality=QualityOption.AUDIO_MP3,
    )
    widget.set_settings(settings)
    assert widget.txt_download_dir.text() == "C:/TestDownloads"
    assert widget.spin_concurrency.value() == 5
    assert widget.combo_default_quality.currentData() == QualityOption.AUDIO_MP3

    # Switch to 1080p and verify saving
    saved = []
    widget.settings_saved.connect(lambda s: saved.append(s))
    widget.combo_default_quality.setCurrentIndex(1)  # 1080p
    widget._on_save_settings()
    assert len(saved) == 1
    assert isinstance(saved[0].default_quality, QualityOption)
    assert saved[0].default_quality == QualityOption.Q_1080P


def test_single_url_widget_cancel_handling(qapp):
    widget = SingleUrlWidget()
    widget.on_download_error("Download cancelled by user")
    assert "Cancelled" in widget.lbl_prog_status.text()
    assert widget.btn_download.isEnabled()


def test_user_reported_download_flow(qapp, tmp_path):
    """Reproduces the user flow with the reported URL across multiple quality settings."""

    class FakeDownloader(IDownloader):
        def download(self, request, settings, progress_callback=None, cancel_event=None):
            fake_file = tmp_path / f"saved_reel_{request.quality.value}.mp4"
            fake_file.write_text("reel data")
            return str(fake_file)

    class FakeExtractor(IExtractor):
        def extract_info(self, url, settings=None):
            return MediaItem(url=url, shortcode="DfHVaRRB5Qc", title="Reel Title")

    url = "https://www.instagram.com/reel/DfHVaRRB5Qc/?utm_source=ig_web_copy_link&psln=NTc4MTIwNjQ2YQ=="

    for q_idx, expected_q in [(0, QualityOption.BEST), (1, QualityOption.Q_1080P), (4, QualityOption.AUDIO_MP3)]:
        window = MainWindow()
        window._metadata_use_case = ExtractMetadataUseCase(FakeExtractor())
        window._single_download_use_case = DownloadMediaUseCase(
            downloader=FakeDownloader(),
            history_repo=window._history_repo,
        )

        window.tab_single.url_input.setText(url)
        window.tab_single.combo_quality.setCurrentIndex(q_idx)

        errors = []
        successes = []
        window.tab_single.download_requested.connect(
            lambda u, q: (
                errors.append(f"Invalid quality type: {type(q)}") if not isinstance(q, QualityOption) else None
            )
        )

        window.tab_single._on_download_click()
        assert len(errors) == 0

        worker = window._single_worker
        assert worker is not None
        worker_errors = []
        worker.download_failed.connect(lambda err: worker_errors.append(err))
        worker.download_finished.connect(lambda p: successes.append(p))

        worker.wait(5000)
        qapp.processEvents()
        assert len(worker_errors) == 0, f"Worker failed with errors: {worker_errors}"
        assert len(successes) == 1
        assert f"saved_reel_{expected_q.value}.mp4" in successes[0]
