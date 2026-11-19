"""Single URL input and download component with two-tier mode/quality selector and rich telemetry."""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QLabel,
    QProgressBar,
    QFrame,
    QApplication,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QPixmap, QImage
from ..design_system import DarkThemeTokens
from ..workers import ThumbnailLoaderWorker
from .media_player_dialog import MediaPlayerDialog
from ...domain.models import QualityOption, MediaItem, DownloadProgress, Platform, SubtitleMode, enum_value
from ...domain.url_parser import MediaUrlParser, UniversalMediaUrlParser


class SingleUrlWidget(QWidget):
    """Widget for inspecting and downloading individual Instagram & YouTube URLs."""
    download_requested = Signal(str, QualityOption)  # url, quality
    inspect_requested = Signal(str)                  # url
    cancel_requested = Signal()
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)

    AUDIO_OPTIONS = {
        QualityOption.AUDIO_MP3,
        QualityOption.AUDIO_M4A,
        QualityOption.AUDIO_WAV,
        QualityOption.AUDIO_FLAC,
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_media: Optional[MediaItem] = None
        self._last_downloaded_file: Optional[str] = None
        self._thumb_worker: Optional[ThumbnailLoaderWorker] = None
        self._is_syncing_quality: bool = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 1. URL Input Bar Frame
        input_frame = QFrame()
        input_frame.setObjectName("cardFrame")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setSpacing(12)

        header_box = QHBoxLayout()
        input_title = QLabel("📥 Single Media Downloader")
        input_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")

        self.lbl_platform_badge = QLabel("🌐 Auto Platform")
        self.lbl_platform_badge.setStyleSheet(
            f"background-color: rgba(255, 255, 255, 0.05); color: {DarkThemeTokens.TEXT_MUTED}; "
            "padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;"
        )

        header_box.addWidget(input_title)
        header_box.addStretch()
        header_box.addWidget(self.lbl_platform_badge)
        input_layout.addLayout(header_box)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste Instagram, YouTube, TikTok, X, Reddit, Facebook, Pinterest or web link...")
        self.url_input.returnPressed.connect(self._on_download_click)
        self.url_input.textChanged.connect(self._on_url_text_changed)

        self.btn_paste = QPushButton("📋 Paste")
        self.btn_paste.setObjectName("secondaryButton")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.clicked.connect(self._on_paste_click)

        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.btn_paste)
        input_layout.addLayout(url_row)

        # Options Row: Two-Tier Mode Toggle (Video vs Audio-only) + Format & Quality Selector
        options_row = QHBoxLayout()
        options_row.setSpacing(12)

        # Tier 1: Mode Selectors (Video vs Audio)
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        options_row.addWidget(mode_label)

        self.mode_group = QButtonGroup(self)
        self.radio_mode_video = QRadioButton("🎬 Video (+Audio)")
        self.radio_mode_audio = QRadioButton("🎵 Audio Only")
        self.radio_mode_video.setChecked(True)
        self.mode_group.addButton(self.radio_mode_video)
        self.mode_group.addButton(self.radio_mode_audio)
        self.radio_mode_video.toggled.connect(self._on_mode_toggled)

        options_row.addWidget(self.radio_mode_video)
        options_row.addWidget(self.radio_mode_audio)

        # Tier 2: Dynamic Quality Dropdown (retaining full len(QualityOption) for backwards compatibility)
        quality_label = QLabel("Quality / Format:")
        quality_label.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600; margin-left: 8px;")
        options_row.addWidget(quality_label)

        self.combo_quality = QComboBox()
        for opt in QualityOption:
            self.combo_quality.addItem(QualityOption.get_display_name(opt), opt)
        self.combo_quality.currentIndexChanged.connect(self._on_quality_index_changed)
        options_row.addWidget(self.combo_quality)

        self.lbl_format_badge = QLabel("MP4 Container")
        self.lbl_format_badge.setStyleSheet(
            f"background-color: {DarkThemeTokens.SURFACE_CARD}; color: {DarkThemeTokens.IG_PINK}; "
            "padding: 4px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;"
        )
        options_row.addWidget(self.lbl_format_badge)

        options_row.addStretch()

        self.btn_inspect = QPushButton("🔍 Inspect Info")
        self.btn_inspect.setObjectName("secondaryButton")
        self.btn_inspect.setCursor(Qt.PointingHandCursor)
        self.btn_inspect.clicked.connect(self._on_inspect_click)

        self.btn_download = QPushButton("⬇ Download Now")
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.clicked.connect(self._on_download_click)

        options_row.addWidget(self.btn_inspect)
        options_row.addWidget(self.btn_download)
        input_layout.addLayout(options_row)

        # Advanced Row: Subtitles & Video Trimming
        advanced_row = QHBoxLayout()
        advanced_row.setSpacing(12)

        lbl_subs = QLabel("Subtitles:")
        lbl_subs.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.combo_subs = QComboBox()
        self.combo_subs.addItem("None", SubtitleMode.NONE)
        self.combo_subs.addItem("Download SRT", SubtitleMode.EXTERNAL_SRT)
        self.combo_subs.addItem("Embed in MP4", SubtitleMode.EMBED)

        advanced_row.addWidget(lbl_subs)
        advanced_row.addWidget(self.combo_subs)

        self.chk_time_slice = QCheckBox("✂️ Clip Range:")
        self.chk_time_slice.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600; margin-left: 8px;")
        self.txt_time_start = QLineEdit("00:00:00")
        self.txt_time_start.setFixedWidth(70)
        self.txt_time_start.setEnabled(False)
        lbl_to = QLabel("to")
        lbl_to.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")
        self.txt_time_end = QLineEdit("00:01:00")
        self.txt_time_end.setFixedWidth(70)
        self.txt_time_end.setEnabled(False)

        self.chk_time_slice.toggled.connect(lambda checked: self.txt_time_start.setEnabled(checked))
        self.chk_time_slice.toggled.connect(lambda checked: self.txt_time_end.setEnabled(checked))

        advanced_row.addWidget(self.chk_time_slice)
        advanced_row.addWidget(self.txt_time_start)
        advanced_row.addWidget(lbl_to)
        advanced_row.addWidget(self.txt_time_end)
        advanced_row.addStretch()

        input_layout.addLayout(advanced_row)

        main_layout.addWidget(input_frame)

        # Initial view filtering for video mode
        self._filter_dropdown_rows(is_audio=False)

        # 2. Media Preview Card
        self.preview_card = QFrame()
        self.preview_card.setObjectName("previewCard")
        self.preview_card.setVisible(False)
        preview_layout = QHBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(16)

        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setFixedSize(140, 140)
        self.lbl_thumbnail.setStyleSheet(f"background-color: {DarkThemeTokens.SURFACE_CARD}; border-radius: 8px;")
        self.lbl_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumbnail.setText("No Preview")

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        self.lbl_media_title = QLabel("Title")
        self.lbl_media_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        self.lbl_media_title.setWordWrap(True)

        self.lbl_media_author = QLabel("Author: @handle")
        self.lbl_media_author.setStyleSheet(f"color: {DarkThemeTokens.IG_PINK}; font-weight: 600;")

        self.lbl_media_meta = QLabel("Duration: 0:00 • Type: Reel")
        self.lbl_media_meta.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 12px;")

        info_layout.addWidget(self.lbl_media_title)
        info_layout.addWidget(self.lbl_media_author)
        info_layout.addWidget(self.lbl_media_meta)
        info_layout.addStretch()

        preview_layout.addWidget(self.lbl_thumbnail)
        preview_layout.addLayout(info_layout, 1)

        main_layout.addWidget(self.preview_card)

        # 3. Dynamic Telemetry & Progress Card
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("cardFrame")
        self.progress_frame.setVisible(False)
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setSpacing(10)

        # Stage Badge & Status Row
        badge_row = QHBoxLayout()
        self.lbl_stage_badge = QLabel("● Ready")
        self.lbl_stage_badge.setStyleSheet(
            f"background-color: rgba(59, 130, 246, 0.2); color: {DarkThemeTokens.STATUS_INFO}; "
            "padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px;"
        )
        self.lbl_prog_status = QLabel("Ready")
        self.lbl_prog_status.setStyleSheet("font-weight: 600; color: #FFFFFF;")

        badge_row.addWidget(self.lbl_stage_badge)
        badge_row.addWidget(self.lbl_prog_status)
        badge_row.addStretch()
        prog_layout.addLayout(badge_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        # Telemetry Metrics Grid (Speed, ETA, Size)
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(16)

        self.lbl_telemetry_speed = QLabel("⚡ 0.0 MB/s")
        self.lbl_telemetry_speed.setStyleSheet(f"color: {DarkThemeTokens.STATUS_SUCCESS}; font-weight: bold; font-size: 12px;")

        self.lbl_telemetry_eta = QLabel("⏱️ ETA: --:--")
        self.lbl_telemetry_eta.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-size: 12px;")

        self.lbl_telemetry_size = QLabel("💾 0.0 MB / 0.0 MB")
        self.lbl_telemetry_size.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 12px;")

        self.lbl_prog_details = QLabel("0.0 KB/s • ETA: --:--")
        self.lbl_prog_details.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-size: 12px;")

        metrics_row.addWidget(self.lbl_telemetry_speed)
        metrics_row.addWidget(self.lbl_telemetry_eta)
        metrics_row.addWidget(self.lbl_telemetry_size)
        metrics_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("dangerButton")
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)

        self.btn_play = QPushButton("▶ Play Video")
        self.btn_play.setObjectName("secondaryButton")
        self.btn_play.setVisible(False)
        self.btn_play.clicked.connect(self._on_play_click)

        self.btn_preview_in_app = QPushButton("🎬 Preview In-App")
        self.btn_preview_in_app.setObjectName("secondaryButton")
        self.btn_preview_in_app.setVisible(False)
        self.btn_preview_in_app.clicked.connect(self._on_preview_in_app_click)

        self.btn_open_file = QPushButton("📁 Show in Folder")
        self.btn_open_file.setObjectName("secondaryButton")
        self.btn_open_file.setVisible(False)
        self.btn_open_file.clicked.connect(self._on_open_folder_click)

        metrics_row.addWidget(self.btn_cancel)
        metrics_row.addWidget(self.btn_preview_in_app)
        metrics_row.addWidget(self.btn_play)
        metrics_row.addWidget(self.btn_open_file)

        prog_layout.addLayout(metrics_row)
        main_layout.addWidget(self.progress_frame)
        main_layout.addStretch()

    # --- Mode & Quality Two-Tier Synchronization ---
    def _filter_dropdown_rows(self, is_audio: bool):
        """Hides or reveals rows in combo_quality popup depending on selected mode."""
        view = self.combo_quality.view()
        if not view:
            return
        for i in range(self.combo_quality.count()):
            opt = self.combo_quality.itemData(i)
            if opt is None:
                txt = self.combo_quality.itemText(i)
                opt = QualityOption.from_value(txt)
            is_opt_audio = opt in self.AUDIO_OPTIONS
            view.setRowHidden(i, is_opt_audio != is_audio)

    def _on_mode_toggled(self, video_checked: bool):
        if self._is_syncing_quality:
            return
        self._is_syncing_quality = True
        try:
            is_audio = not video_checked
            self._filter_dropdown_rows(is_audio)
            cur_opt = self.get_quality()
            is_cur_audio = cur_opt in self.AUDIO_OPTIONS

            if is_audio and not is_cur_audio:
                self.set_quality(QualityOption.AUDIO_MP3)
            elif not is_audio and is_cur_audio:
                self.set_quality(QualityOption.BEST)

            self._update_format_badge()
        finally:
            self._is_syncing_quality = False

    def _on_quality_index_changed(self, index: int):
        if self._is_syncing_quality or index < 0:
            return
        self._is_syncing_quality = True
        try:
            cur_opt = self.get_quality()
            is_audio = cur_opt in self.AUDIO_OPTIONS
            if is_audio and not self.radio_mode_audio.isChecked():
                self.radio_mode_audio.setChecked(True)
                self._filter_dropdown_rows(is_audio=True)
            elif not is_audio and not self.radio_mode_video.isChecked():
                self.radio_mode_video.setChecked(True)
                self._filter_dropdown_rows(is_audio=False)
            self._update_format_badge()
        finally:
            self._is_syncing_quality = False

    def _update_format_badge(self):
        opt = self.get_quality()
        if opt in self.AUDIO_OPTIONS:
            codec = enum_value(opt).upper()
            self.lbl_format_badge.setText(f"{codec} Audio Track")
        elif opt == QualityOption.Q_2160P:
            self.lbl_format_badge.setText("4K Ultra HD MP4")
        elif opt == QualityOption.Q_1080P:
            self.lbl_format_badge.setText("1080p Full HD MP4")
        else:
            self.lbl_format_badge.setText("MP4 Video + Audio")

    def get_quality(self) -> QualityOption:
        """Returns the currently selected QualityOption."""
        data = self.combo_quality.currentData() or self.combo_quality.currentText()
        return QualityOption.from_value(data)

    def set_quality(self, quality: QualityOption):
        """Programmatically sets the active quality option."""
        target_val = enum_value(quality)
        idx = self.combo_quality.findData(quality)
        if idx < 0:
            idx = self.combo_quality.findData(target_val)
        if idx < 0:
            idx = self.combo_quality.findText(QualityOption.get_display_name(quality))
        if idx >= 0:
            self.combo_quality.setCurrentIndex(idx)

    # --- Actions ---
    def _on_paste_click(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.url_input.setText(text)
            if MediaUrlParser.is_valid(text):
                self._on_inspect_click()

    def _on_inspect_click(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Required", "Please enter an Instagram or YouTube URL.")
            return
        if not MediaUrlParser.is_valid(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid Instagram or YouTube link.")
            return

        self.inspect_requested.emit(url)

    def _on_download_click(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Required", "Please enter an Instagram or YouTube URL.")
            return
        if not MediaUrlParser.is_valid(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid Instagram or YouTube link.")
            return

        quality = self.get_quality()
        self.progress_frame.setVisible(True)
        self._set_stage_badge("🔍 Connecting...", DarkThemeTokens.STATUS_INFO)
        self.lbl_prog_status.setText("Initializing download...")
        self.lbl_prog_details.setText("Connecting...")
        self.lbl_telemetry_speed.setText("⚡ 0.0 MB/s")
        self.lbl_telemetry_eta.setText("⏱️ ETA: --:--")
        self.lbl_telemetry_size.setText("💾 0.0 MB / 0.0 MB")
        self.progress_bar.setValue(0)
        self.btn_cancel.setVisible(True)
        self.btn_play.setVisible(False)
        self.btn_open_file.setVisible(False)
        self.btn_download.setEnabled(False)

        self.download_requested.emit(url, quality)

    def display_media_preview(self, item: MediaItem):
        self._current_media = item
        self.preview_card.setVisible(True)
        self.lbl_media_title.setText(item.display_title)

        if item.platform == Platform.YOUTUBE:
            author_text = f"Channel: {item.author}" if item.author else "YouTube Channel"
            self.lbl_media_author.setStyleSheet(f"color: {DarkThemeTokens.YT_RED}; font-weight: 600;")
        else:
            author_text = f"@{item.author}" if item.author else "Instagram Creator"
            self.lbl_media_author.setStyleSheet(f"color: {DarkThemeTokens.IG_PINK}; font-weight: 600;")
        self.lbl_media_author.setText(author_text)

        plat_str = enum_value(item.platform).upper()
        media_type_str = enum_value(item.media_type).upper()
        if item.is_playlist:
            count = len(item.playlist_urls)
            meta_str = f"Platform: {plat_str} • Type: PLAYLIST ({count} videos)" if count else f"Platform: {plat_str} • Type: PLAYLIST"
            self.btn_download.setText(f"⬇ Download Playlist ({count} videos)" if count else "⬇ Download Playlist")
        else:
            meta_str = f"Platform: {plat_str} • Type: {media_type_str} • Duration: {item.formatted_duration}"
            self.btn_download.setText("⬇ Download Now")
        self.lbl_media_meta.setText(meta_str)

        # Load thumbnail asynchronously if available
        if item.thumbnail_url:
            self._load_thumbnail(item.thumbnail_url)
        else:
            self.lbl_thumbnail.setText("No Preview")

    def _load_thumbnail(self, url: str):
        self.lbl_thumbnail.setText("Loading\npreview...")
        self._thumb_worker = ThumbnailLoaderWorker(url, self)
        self._thumb_worker.loaded.connect(self._on_thumbnail_data_loaded)
        plat_label = "YouTube" if self._current_media and self._current_media.platform == Platform.YOUTUBE else "Instagram"
        self._thumb_worker.failed.connect(lambda: self.lbl_thumbnail.setText(f"{plat_label}\nMedia"))
        self._thumb_worker.start()

    def _on_thumbnail_data_loaded(self, data: bytes):
        image = QImage()
        if image.loadFromData(QByteArray(data)):
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.lbl_thumbnail.setPixmap(scaled)
        else:
            plat_label = "YouTube" if self._current_media and self._current_media.platform == Platform.YOUTUBE else "Instagram"
            self.lbl_thumbnail.setText(f"{plat_label}\nMedia")

    def _set_stage_badge(self, text: str, color_hex: str):
        self.lbl_stage_badge.setText(f"● {text}")
        self.lbl_stage_badge.setStyleSheet(
            f"background-color: rgba(30, 41, 59, 0.8); color: {color_hex}; "
            f"border: 1px solid {color_hex}; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px;"
        )

    def update_progress(self, progress: DownloadProgress):
        self.progress_bar.setValue(int(progress.percent))
        self.lbl_prog_status.setText(progress.status_message)
        details = f"{progress.formatted_size} • Speed: {progress.speed_str} • ETA: {progress.eta_str}"
        self.lbl_prog_details.setText(details)

        self.lbl_telemetry_speed.setText(f"⚡ {progress.speed_str}")
        self.lbl_telemetry_eta.setText(f"⏱️ ETA: {progress.eta_str}")
        self.lbl_telemetry_size.setText(f"💾 {progress.formatted_size}")

        # Update stage badge based on progress metrics
        msg_lower = progress.status_message.lower()
        if "converting" in msg_lower or "transcoding" in msg_lower or "extracting audio" in msg_lower:
            self._set_stage_badge("Transcoding/Converting", DarkThemeTokens.STATUS_WARNING)
        elif progress.percent >= 100:
            self._set_stage_badge("Processing Final File", DarkThemeTokens.STATUS_SUCCESS)
        elif progress.percent > 0:
            self._set_stage_badge(f"Downloading ({int(progress.percent)}%)", DarkThemeTokens.IG_PINK)
        else:
            self._set_stage_badge("Connecting...", DarkThemeTokens.STATUS_INFO)

    def on_download_success(self, file_path: str):
        self._last_downloaded_file = file_path
        self.progress_bar.setValue(100)
        self._set_stage_badge("Ready", DarkThemeTokens.STATUS_SUCCESS)
        self.lbl_prog_status.setText("✅ Download Completed!")
        self.lbl_prog_details.setText(f"Saved: {os.path.basename(file_path)}")
        self.lbl_telemetry_speed.setText("⚡ Finished")
        self.lbl_telemetry_eta.setText("⏱️ Ready")
        self.btn_cancel.setVisible(False)
        self.btn_preview_in_app.setVisible(True)
        self.btn_play.setVisible(True)
        self.btn_open_file.setVisible(True)
        self.btn_download.setEnabled(True)

    def on_download_error(self, error_message: str):
        self.btn_cancel.setVisible(False)
        self.btn_download.setEnabled(True)
        if "cancelled" in error_message.lower():
            self._set_stage_badge("Cancelled", DarkThemeTokens.TEXT_MUTED)
            self.lbl_prog_status.setText("⏹ Download Cancelled")
            self.lbl_prog_details.setText("Operation cancelled by user.")
            return

        self._set_stage_badge("Failed", DarkThemeTokens.STATUS_ERROR)
        self.lbl_prog_status.setText("❌ Download Failed")
        self.lbl_prog_details.setText(error_message)
        QMessageBox.critical(self, "Download Error", f"Failed to download media:\n{error_message}")

    def _on_url_text_changed(self, text: str):
        if not text or not text.strip():
            self.lbl_platform_badge.setText("🌐 Auto Platform")
            self.lbl_platform_badge.setStyleSheet(
                f"background-color: rgba(255, 255, 255, 0.05); color: {DarkThemeTokens.TEXT_MUTED}; "
                "padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;"
            )
            return

        plat = UniversalMediaUrlParser.detect_platform(text)
        configs = {
            Platform.INSTAGRAM: ("📸 Instagram", DarkThemeTokens.IG_PINK, "rgba(225, 48, 108, 0.15)"),
            Platform.YOUTUBE: ("▶️ YouTube", DarkThemeTokens.YT_RED, "rgba(255, 0, 0, 0.15)"),
            Platform.TIKTOK: ("🎵 TikTok", "#00F2FE", "rgba(0, 242, 254, 0.15)"),
            Platform.TWITTER: ("🐦 Twitter / X", "#1DA1F2", "rgba(29, 161, 242, 0.15)"),
            Platform.REDDIT: ("👽 Reddit", "#FF4500", "rgba(255, 69, 0, 0.15)"),
            Platform.FACEBOOK: ("👥 Facebook", "#1877F2", "rgba(24, 119, 242, 0.15)"),
            Platform.PINTEREST: ("📌 Pinterest", "#E60023", "rgba(230, 0, 35, 0.15)"),
            Platform.TWITCH: ("🟣 Twitch", "#9146FF", "rgba(145, 70, 255, 0.15)"),
            Platform.SOUNDCLOUD: ("🟠 SoundCloud", "#FF5500", "rgba(255, 85, 0, 0.15)"),
            Platform.UNIVERSAL: ("🌐 Web Media", DarkThemeTokens.STATUS_INFO, "rgba(59, 130, 246, 0.15)"),
        }
        if plat in configs:
            label, color, bg = configs[plat]
            self.lbl_platform_badge.setText(label)
            self.lbl_platform_badge.setStyleSheet(
                f"background-color: {bg}; color: {color}; border: 1px solid {color}; "
                "padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;"
            )
        else:
            self.lbl_platform_badge.setText("🌐 Auto Platform")
            self.lbl_platform_badge.setStyleSheet(
                f"background-color: rgba(255, 255, 255, 0.05); color: {DarkThemeTokens.TEXT_MUTED}; "
                "padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;"
            )

    def get_subtitles_mode(self) -> SubtitleMode:
        data = self.combo_subs.currentData()
        return SubtitleMode.from_value(data) if data else SubtitleMode.NONE

    def get_time_range(self) -> tuple[Optional[str], Optional[str]]:
        if self.chk_time_slice.isChecked():
            start = self.txt_time_start.text().strip() or None
            end = self.txt_time_end.text().strip() or None
            return start, end
        return None, None

    def _on_preview_in_app_click(self):
        if self._last_downloaded_file and os.path.exists(self._last_downloaded_file):
            dialog = MediaPlayerDialog(self._last_downloaded_file, self)
            dialog.exec()
        else:
            QMessageBox.warning(self, "File Not Found", "No downloaded media available to preview.")

    def _on_play_click(self):
        if self._last_downloaded_file and os.path.exists(self._last_downloaded_file):
            self.open_file_requested.emit(self._last_downloaded_file)

    def _on_open_folder_click(self):
        if self._last_downloaded_file and os.path.exists(self._last_downloaded_file):
            self.open_folder_requested.emit(self._last_downloaded_file)
