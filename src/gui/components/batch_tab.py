"""Batch URL processor component with two-tier mode and quality selection."""

import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from ..design_system import DarkThemeTokens
from ...domain.models import QualityOption, enum_value
from ...domain.url_parser import MediaUrlParser


class BatchTabWidget(QWidget):
    """Widget for inputting and queueing multiple Instagram & YouTube links simultaneously."""
    batch_add_requested = Signal(list, QualityOption)  # list of URLs, quality

    AUDIO_OPTIONS = {
        QualityOption.AUDIO_MP3,
        QualityOption.AUDIO_M4A,
        QualityOption.AUDIO_WAV,
        QualityOption.AUDIO_FLAC,
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_syncing_quality: bool = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("🚀 Batch Video, Reel & Playlist Processor")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        header_row.addWidget(title)
        header_row.addStretch()

        self.lbl_stats = QLabel("0 valid URLs detected")
        self.lbl_stats.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 12px;")
        header_row.addWidget(self.lbl_stats)

        card_layout.addLayout(header_row)

        instruction = QLabel(
            "Paste multiple Instagram or YouTube links below (one per line). Supports Reels, Shorts, Videos, Playlists, Posts, and Stories."
        )
        instruction.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-size: 12px;")
        card_layout.addWidget(instruction)

        # Batch Text Box
        self.txt_urls = QPlainTextEdit()
        self.txt_urls.setPlaceholderText(
            "https://www.instagram.com/reel/C2-7XYZ1234/\n"
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
            "https://www.youtube.com/shorts/3fDkJ2hZ91A\n"
            "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )
        self.txt_urls.textChanged.connect(self._update_counter)
        card_layout.addWidget(self.txt_urls, 1)

        # Bottom Bar: Mode radio + combo + actions
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.btn_load_file = QPushButton("📂 Load .txt File")
        self.btn_load_file.setObjectName("secondaryButton")
        self.btn_load_file.clicked.connect(self._on_load_file)

        self.btn_clear = QPushButton("🧹 Clear")
        self.btn_clear.setObjectName("secondaryButton")
        self.btn_clear.clicked.connect(self.txt_urls.clear)

        bottom_bar.addWidget(self.btn_load_file)
        bottom_bar.addWidget(self.btn_clear)
        bottom_bar.addStretch()

        # Two-Tier Mode Selection in Batch Tab
        mode_lbl = QLabel("Mode:")
        mode_lbl.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        bottom_bar.addWidget(mode_lbl)

        self.mode_group = QButtonGroup(self)
        self.radio_mode_video = QRadioButton("🎬 Video")
        self.radio_mode_audio = QRadioButton("🎵 Audio")
        self.radio_mode_video.setChecked(True)
        self.mode_group.addButton(self.radio_mode_video)
        self.mode_group.addButton(self.radio_mode_audio)
        self.radio_mode_video.toggled.connect(self._on_mode_toggled)

        bottom_bar.addWidget(self.radio_mode_video)
        bottom_bar.addWidget(self.radio_mode_audio)

        quality_lbl = QLabel("Target Quality:")
        quality_lbl.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600; margin-left: 6px;")
        bottom_bar.addWidget(quality_lbl)

        self.combo_quality = QComboBox()
        for opt in QualityOption:
            self.combo_quality.addItem(QualityOption.get_display_name(opt), opt)
        self.combo_quality.currentIndexChanged.connect(self._on_quality_index_changed)

        bottom_bar.addWidget(self.combo_quality)

        self.btn_add_queue = QPushButton("🚀 Add All to Queue")
        self.btn_add_queue.setObjectName("primaryButton")
        self.btn_add_queue.setCursor(Qt.PointingHandCursor)
        self.btn_add_queue.clicked.connect(self._on_add_to_queue)

        bottom_bar.addWidget(self.btn_add_queue)
        card_layout.addLayout(bottom_bar)

        main_layout.addWidget(card)
        self._filter_dropdown_rows(is_audio=False)

    def _filter_dropdown_rows(self, is_audio: bool):
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
        finally:
            self._is_syncing_quality = False

    def get_quality(self) -> QualityOption:
        data = self.combo_quality.currentData() or self.combo_quality.currentText()
        return QualityOption.from_value(data)

    def set_quality(self, quality: QualityOption):
        target_val = enum_value(quality)
        idx = self.combo_quality.findData(quality)
        if idx < 0:
            idx = self.combo_quality.findData(target_val)
        if idx < 0:
            idx = self.combo_quality.findText(QualityOption.get_display_name(quality))
        if idx >= 0:
            self.combo_quality.setCurrentIndex(idx)

    def _get_valid_urls(self) -> List[str]:
        lines = self.txt_urls.toPlainText().splitlines()
        valid = []
        for line in lines:
            line = line.strip()
            if line and MediaUrlParser.is_valid(line):
                valid.append(line)
        return valid

    def _update_counter(self):
        valid = self._get_valid_urls()
        count = len(valid)
        self.lbl_stats.setText(f"{count} valid URL{'s' if count != 1 else ''} detected")

    def _on_load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select URLs Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.txt_urls.setPlainText(content)
            except Exception as e:
                QMessageBox.critical(self, "Read Error", f"Failed to read file:\n{str(e)}")

    def _on_add_to_queue(self):
        valid_urls = self._get_valid_urls()
        if not valid_urls:
            QMessageBox.warning(
                self,
                "No Valid URLs",
                "Please enter at least one valid Instagram or YouTube URL before adding to the queue.",
            )
            return

        quality = self.get_quality()
        self.batch_add_requested.emit(valid_urls, quality)
        self.txt_urls.clear()
