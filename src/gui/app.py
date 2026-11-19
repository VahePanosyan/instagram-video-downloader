"""Main GUI Application Window integrating hexagonal ports, use cases, and Qt components."""

import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QStatusBar,
    QApplication,
    QMessageBox,
)
from .design_system import get_stylesheet, DARK_STYLESHEET
from .components import (
    HeaderWidget,
    SingleUrlWidget,
    BatchTabWidget,
    QueueTableWidget,
    HistoryTabWidget,
    SettingsTabWidget,
)
from .components.log_panel import EventLogWidget
from .workers import MetadataFetchWorker, SingleDownloadWorker, BatchQueueWorker
from ..domain.models import (
    AppSettings,
    QualityOption,
    MediaItem,
    DownloadRequest,
    Platform,
)
from ..domain.url_parser import MediaUrlParser, YouTubeUrlParser
from ..adapters.yt_dlp_adapter import YtDlpAdapter
from ..adapters.json_repository import JsonSettingsRepository, JsonHistoryRepository
from ..use_cases.extract_metadata import ExtractMetadataUseCase
from ..use_cases.download_media import DownloadMediaUseCase
from ..use_cases.batch_downloader import BatchDownloaderUseCase
from ..use_cases.manage_settings import ManageSettingsUseCase
from ..use_cases.manage_history import ManageHistoryUseCase


logger = logging.getLogger("instagram_downloader")


class MainWindow(QMainWindow):
    """Main window of the Instagram & YouTube Video Downloader application."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instagram Video Downloader Pro")
        self.setMinimumSize(1000, 720)
        self.resize(1080, 760)
        self._set_window_icon()

        # 1. Initialize Hexagonal Services & Repositories
        self._init_services()

        # 2. Setup UI & Design System
        is_dark = getattr(self._current_settings, "dark_theme", True)
        self.setStyleSheet(get_stylesheet(is_dark))
        self._setup_ui()

        # 3. Setup Clipboard Monitoring
        self._setup_clipboard_monitor()

        # 4. Active Background Workers
        self._meta_worker: Optional[MetadataFetchWorker] = None
        self._single_worker: Optional[SingleDownloadWorker] = None
        self._batch_worker: Optional[BatchQueueWorker] = None

        # 5. Initial Data Load & Logging Hook
        self._load_initial_data()
        self._setup_logging()

        # 6. Drag and Drop & System Tray Setup
        self.setAcceptDrops(True)
        self._setup_system_tray()

    def _init_services(self):
        self._adapter = YtDlpAdapter()
        self._settings_repo = JsonSettingsRepository()
        self._history_repo = JsonHistoryRepository()

        self._settings_use_case = ManageSettingsUseCase(self._settings_repo)
        self._history_use_case = ManageHistoryUseCase(self._history_repo)
        self._metadata_use_case = ExtractMetadataUseCase(self._adapter)
        self._single_download_use_case = DownloadMediaUseCase(self._adapter, self._history_repo)
        self._batch_use_case = BatchDownloaderUseCase(
            downloader=self._adapter,
            metadata_use_case=self._metadata_use_case,
            history_repo=self._history_repo,
        )

        self._current_settings = self._settings_use_case.get_settings()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header with Theme Toggle
        is_dark = getattr(self._current_settings, "dark_theme", True)
        self.header = HeaderWidget()
        self.header.set_theme(is_dark)
        self.header.open_downloads_requested.connect(self._open_downloads_directory)
        self.header.theme_toggle_requested.connect(self._on_theme_toggle_clicked)
        main_layout.addWidget(self.header)

        # Tabs Container (Preserving exactly 5 tabs required by tests)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Tab 1: Single Download
        self.tab_single = SingleUrlWidget()
        self.tab_single.inspect_requested.connect(self._on_single_inspect)
        self.tab_single.download_requested.connect(self._on_single_download)
        self.tab_single.cancel_requested.connect(self._on_single_cancel)
        self.tab_single.open_file_requested.connect(self._open_file_external)
        self.tab_single.open_folder_requested.connect(self._open_folder_external)
        self.tabs.addTab(self.tab_single, "📥 Single Downloader")

        # Tab 2: Batch Download
        self.tab_batch = BatchTabWidget()
        self.tab_batch.batch_add_requested.connect(self._on_batch_add)
        self.tabs.addTab(self.tab_batch, "🚀 Batch Processor")

        # Tab 3: Active Queue
        self.tab_queue = QueueTableWidget()
        self.tab_queue.start_queue_requested.connect(self._start_batch_queue)
        self.tab_queue.pause_queue_requested.connect(self._pause_batch_queue)
        self.tab_queue.resume_queue_requested.connect(self._resume_batch_queue)
        self.tab_queue.move_item_up_requested.connect(self._move_queue_item_up)
        self.tab_queue.move_item_down_requested.connect(self._move_queue_item_down)
        self.tab_queue.cancel_all_requested.connect(self._cancel_all_queue)
        self.tab_queue.clear_completed_requested.connect(self._clear_completed_queue)
        self.tab_queue.cancel_item_requested.connect(self._cancel_queue_item)
        self.tab_queue.open_file_requested.connect(self._open_file_external)
        self.tabs.addTab(self.tab_queue, "⚡ Active Queue")

        # Tab 4: History
        self.tab_history = HistoryTabWidget()
        self.tab_history.open_file_requested.connect(self._open_file_external)
        self.tab_history.open_folder_requested.connect(self._open_folder_external)
        self.tab_history.delete_item_requested.connect(self._delete_history_item)
        self.tab_history.clear_all_requested.connect(self._clear_all_history)
        self.tabs.addTab(self.tab_history, "📜 History")

        # Tab 5: Settings
        self.tab_settings = SettingsTabWidget()
        self.tab_settings.settings_saved.connect(self._on_settings_saved)
        self.tabs.addTab(self.tab_settings, "⚙️ Settings")

        main_layout.addWidget(self.tabs, 1)

        # Integrated Collapsible Event Log Panel (At bottom above status bar)
        self.log_panel = EventLogWidget(self, collapsed=True)
        self.log_panel.set_theme(is_dark)
        main_layout.addWidget(self.log_panel)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready • Engine active • Instagram & YouTube supported • Dual themes loaded")

    def _setup_logging(self):
        root_logger = logging.getLogger()
        handler = self.log_panel.get_logging_handler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(handler)
        self.log_panel.info("Engine initialized: Instagram & YouTube Downloader Pro ready.")

    def _load_initial_data(self):
        self.tab_settings.set_settings(self._current_settings)
        self._refresh_history_tab()

    # --- Dynamic Dual-Theme Management ---
    def apply_theme(self, dark: bool):
        """Dynamically applies dark or light stylesheet across all widgets without restart."""
        self._current_settings.dark_theme = dark
        stylesheet = get_stylesheet(dark)
        self.setStyleSheet(stylesheet)
        self.header.set_theme(dark)
        self.log_panel.set_theme(dark)
        self.tab_settings.set_settings(self._current_settings)
        self._settings_use_case.update_settings(self._current_settings)

        theme_name = "Dark" if dark else "Light"
        self.status_bar.showMessage(f"Theme switched to {theme_name} mode", 3000)
        self.log_panel.info(f"Appearance theme switched to {theme_name} mode.")

    def _on_theme_toggle_clicked(self):
        current_dark = getattr(self._current_settings, "dark_theme", True)
        self.apply_theme(not current_dark)

    # --- Clipboard Monitoring ---
    def _setup_clipboard_monitor(self):
        clipboard = QApplication.clipboard()
        self._last_clipboard_text = ""
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        if not self._current_settings.auto_paste_clipboard:
            return
        try:
            text = QApplication.clipboard().text().strip()
            if text and text != self._last_clipboard_text:
                self._last_clipboard_text = text
                if MediaUrlParser.is_valid(text):
                    if self.tabs.currentIndex() == 0:  # Single URL tab
                        if not self.tab_single.url_input.text():
                            self.tab_single.url_input.setText(text)
                            plat = MediaUrlParser.detect_platform(text)
                            plat_name = "YouTube" if plat == Platform.YOUTUBE else "Instagram"
                            self.status_bar.showMessage(f"📋 {plat_name} link detected from clipboard: {text[:45]}...", 4000)
                            self.log_panel.info(f"Detected valid {plat_name} URL in clipboard.")
        except Exception:
            pass

    # --- Single Download Handlers ---
    def _on_single_inspect(self, url: str):
        plat = MediaUrlParser.detect_platform(url)
        plat_name = "YouTube" if plat == Platform.YOUTUBE else "Instagram"
        self.status_bar.showMessage(f"Fetching {plat_name} media metadata...")
        self.log_panel.info(f"Fetching metadata for {url[:50]}...")

        # Terminate any dangling worker cleanly
        if self._meta_worker and self._meta_worker.isRunning():
            self._meta_worker.wait(500)

        self._meta_worker = MetadataFetchWorker(
            use_case=self._metadata_use_case,
            url=url,
            settings=self._current_settings,
        )
        self._meta_worker.finished.connect(self._on_single_meta_loaded)
        self._meta_worker.failed.connect(self._on_single_meta_error)
        self._meta_worker.start()

    def _on_single_meta_loaded(self, item: MediaItem):
        self.tab_single.display_media_preview(item)
        if item.is_playlist and item.playlist_urls:
            msg = f"Playlist ready: {item.display_title} ({len(item.playlist_urls)} videos)"
            self.status_bar.showMessage(msg, 6000)
            self.log_panel.success(msg)
        else:
            msg = f"Ready to download: {item.display_title}"
            self.status_bar.showMessage(msg, 5000)
            self.log_panel.success(f"Metadata loaded: '{item.display_title}' by {item.author}")

    def _on_single_meta_error(self, err_msg: str):
        self.status_bar.showMessage(f"Metadata fetch warning: {err_msg[:60]}", 4000)
        self.log_panel.warning(f"Metadata fetch error: {err_msg}")

    def _on_single_download(self, url: str, quality: QualityOption):
        target_quality = QualityOption.from_value(quality)
        media_item = (
            self.tab_single._current_media
            if self.tab_single._current_media and self.tab_single._current_media.url == url
            else self._metadata_use_case.get_cached(url)
        )

        # If user initiates download of a playlist from Single tab, queue it into batch
        if media_item and media_item.is_playlist and media_item.playlist_urls:
            self._on_batch_add(media_item.playlist_urls, target_quality)
            return

        if not media_item and MediaUrlParser.detect_platform(url) == Platform.YOUTUBE and YouTubeUrlParser.is_playlist(url):
            self.status_bar.showMessage("Detected YouTube playlist, routing to batch queue...")
            self.log_panel.info("Detected YouTube playlist link. Routing to batch queue.")
            self._on_batch_add([url], target_quality)
            return

        sub_mode = self.tab_single.get_subtitles_mode()
        t_start, t_end = self.tab_single.get_time_range()

        req = DownloadRequest(
            url=url,
            media_item=media_item,
            quality=target_quality,
            output_dir=self._current_settings.download_dir,
            filename_template=self._current_settings.filename_template,
            subtitles_mode=sub_mode,
            subtitles_languages=self._current_settings.subtitles_languages,
            time_range_start=t_start,
            time_range_end=t_end,
        )
        self.status_bar.showMessage(f"Downloading {url[:45]}...")
        self.log_panel.info(f"Starting single download ({target_quality.value}): {url[:50]}...")

        if self._single_worker and self._single_worker.isRunning():
            self._single_worker.cancel()
            self._single_worker.wait(500)

        self._single_worker = SingleDownloadWorker(
            use_case=self._single_download_use_case,
            request=req,
            settings=self._current_settings,
            metadata_use_case=self._metadata_use_case,
        )
        self._single_worker.progress_updated.connect(self.tab_single.update_progress)
        self._single_worker.download_finished.connect(self._on_single_download_done)
        self._single_worker.download_failed.connect(self._on_single_download_failed)
        self._single_worker.start()

    def _on_single_download_done(self, file_path: str):
        self.tab_single.on_download_success(file_path)
        self._refresh_history_tab()
        filename = os.path.basename(file_path)
        self.status_bar.showMessage(f"Saved: {filename}", 5000)
        self.log_panel.success(f"Download finished successfully: {filename}")
        self._play_notification_sound()

    def _on_single_download_failed(self, error_message: str):
        self.tab_single.on_download_error(error_message)
        if "cancelled" in error_message.lower():
            self.log_panel.warning("Download cancelled by user.")
        else:
            self.log_panel.error(f"Download failed: {error_message}")

    def _on_single_cancel(self):
        if self._single_worker:
            self._single_worker.cancel()
            self.status_bar.showMessage("Download cancelled", 3000)
            self.log_panel.warning("Cancelling single download...")

    # --- Batch Handlers ---
    def _on_batch_add(self, urls: List[str], quality: QualityOption):
        target_quality = QualityOption.from_value(quality)
        added = self._batch_use_case.add_urls(urls, self._current_settings, target_quality, expand_playlists=True)
        self.tab_queue.update_requests(self._batch_use_case.get_all_requests())
        # Switch to Queue tab
        self.tabs.setCurrentIndex(2)
        msg = f"Added {len(added)} links to queue. Starting download pool..."
        self.status_bar.showMessage(msg, 4000)
        self.log_panel.info(msg)
        self._start_batch_queue()

    def _start_batch_queue(self):
        if self._batch_use_case.is_running:
            return
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.wait(500)

        self._batch_worker = BatchQueueWorker(self._batch_use_case, self._current_settings)
        self._batch_worker.item_updated.connect(self._on_batch_item_updated)
        self._batch_worker.item_progress.connect(self.tab_queue.update_item_progress)
        self._batch_worker.batch_finished.connect(self._on_batch_all_finished)
        self._batch_worker.start()
        self.status_bar.showMessage("Batch download queue running...")
        self.log_panel.info("Batch download worker pool started.")

    def _on_batch_item_updated(self, req: DownloadRequest):
        self.tab_queue.update_requests(self._batch_use_case.get_all_requests())
        self._refresh_history_tab()

    def _on_batch_all_finished(self):
        self.tab_queue.update_requests(self._batch_use_case.get_all_requests())
        self._refresh_history_tab()
        self.status_bar.showMessage("All batch downloads completed!", 5000)
        self.log_panel.success("All queue batch download tasks completed.")
        self._play_notification_sound()

    def _pause_batch_queue(self):
        self._batch_use_case.pause()
        self.tab_queue.set_paused(True)
        self.status_bar.showMessage("Download queue paused", 3000)
        self.log_panel.warning("Batch queue paused by user.")

    def _resume_batch_queue(self):
        self._batch_use_case.resume()
        self.tab_queue.set_paused(False)
        self.status_bar.showMessage("Download queue resumed", 3000)
        self.log_panel.info("Batch queue resumed.")

    def _move_queue_item_up(self, req_id: str):
        if self._batch_use_case.move_item_up(req_id):
            self.tab_queue.update_requests(self._batch_use_case.get_all_requests())

    def _move_queue_item_down(self, req_id: str):
        if self._batch_use_case.move_item_down(req_id):
            self.tab_queue.update_requests(self._batch_use_case.get_all_requests())

    def _cancel_all_queue(self):
        self._batch_use_case.cancel_all()
        if self._batch_worker:
            self._batch_worker.stop()
        self.tab_queue.update_requests(self._batch_use_case.get_all_requests())
        self.status_bar.showMessage("All queue tasks cancelled", 3000)
        self.log_panel.warning("All active queue downloads cancelled.")

    def _clear_completed_queue(self):
        self._batch_use_case.clear_finished()
        self.tab_queue.update_requests(self._batch_use_case.get_all_requests())

    def _cancel_queue_item(self, req_id: str):
        self._batch_use_case.cancel_item(req_id)
        self.tab_queue.update_requests(self._batch_use_case.get_all_requests())

    # --- History Handlers ---
    def _refresh_history_tab(self):
        items = self._history_use_case.get_history()
        self.tab_history.load_history(items)

    def _delete_history_item(self, item_id: str, delete_disk_file: bool):
        self._history_use_case.remove_item(item_id, delete_file=delete_disk_file)
        self._refresh_history_tab()
        self.log_panel.info(f"History item removed (delete file: {delete_disk_file}).")

    def _clear_all_history(self):
        self._history_use_case.clear_history()
        self._refresh_history_tab()
        self.log_panel.info("History database cleared.")

    # --- Settings Handlers ---
    def _on_settings_saved(self, new_settings: AppSettings):
        theme_changed = new_settings.dark_theme != self._current_settings.dark_theme
        self._current_settings = self._settings_use_case.update_settings(new_settings)
        if theme_changed:
            self.apply_theme(new_settings.dark_theme)
        else:
            self.status_bar.showMessage("Preferences saved successfully", 3000)
        self.log_panel.info("Application settings saved.")

    # --- System Utilities ---
    def _open_downloads_directory(self):
        folder = self._current_settings.download_dir or "./downloads"
        Path(folder).mkdir(parents=True, exist_ok=True)
        self._open_folder_external(str(Path(folder).resolve()))

    def _open_file_external(self, filepath: str):
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "File Not Found", f"The media file does not exist on disk:\n{filepath}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", filepath])
            else:
                subprocess.Popen(["xdg-open", filepath])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def _set_window_icon(self):
        """Loads and sets the window icon from assets if available."""
        from PySide6.QtGui import QIcon
        candidates = [
            Path(sys.executable).parent / "assets" / "app_icon.ico" if getattr(sys, "frozen", False) else None,
            Path(sys.executable).parent / "_internal" / "assets" / "app_icon.ico" if getattr(sys, "frozen", False) else None,
            Path(getattr(sys, "_MEIPASS", "")) / "assets" / "app_icon.ico" if getattr(sys, "frozen", False) else None,
            Path(__file__).resolve().parent.parent.parent / "assets" / "app_icon.ico",
            Path(__file__).resolve().parent.parent.parent / "assets" / "app_icon.png",
        ]
        for c in candidates:
            if c and c.is_file():
                self.setWindowIcon(QIcon(str(c)))
                break

    def _open_folder_external(self, filepath: str):
        if not filepath:
            return
        try:
            p = Path(filepath).resolve()
            if sys.platform == "win32":
                if p.is_file():
                    no_window = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                    subprocess.Popen(["explorer", f"/select,{p}"], creationflags=no_window)
                else:
                    os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R" if p.is_file() else "", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p.parent if p.is_file() else p)])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open directory:\n{str(e)}")

    def _play_notification_sound(self):
        if self._current_settings.sound_notifications:
            try:
                if sys.platform == "win32":
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    # --- Drag & Drop Support ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            txt_files = [f for f in urls if f.endswith(".txt")]
            if txt_files:
                self.tabs.setCurrentIndex(1)
                self.tab_batch._load_from_filepath(txt_files[0])
                event.acceptProposedAction()
                return
        text = event.mimeData().text().strip()
        if text:
            if "\n" in text or len(text.split()) > 1:
                self.tabs.setCurrentIndex(1)
                self.tab_batch.txt_urls.setPlainText(text)
            else:
                self.tabs.setCurrentIndex(0)
                self.tab_single.url_input.setText(text)
            event.acceptProposedAction()

    # --- System Tray Integration ---
    def _setup_system_tray(self):
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        from PySide6.QtGui import QAction
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return

        self._tray_icon = QSystemTrayIcon(self.windowIcon(), self)
        tray_menu = QMenu()
        show_action = QAction("Open Downloader", self)
        show_action.triggered.connect(self.showNormal)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def closeEvent(self, event):
        from PySide6.QtWidgets import QSystemTrayIcon
        if getattr(self._current_settings, "close_to_tray", False) and getattr(self, "_tray_icon", None):
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                "Media Downloader Pro",
                "Application minimized to system tray. Active downloads continue in background.",
                QSystemTrayIcon.Information,
                2000,
            )
        else:
            super().closeEvent(event)
