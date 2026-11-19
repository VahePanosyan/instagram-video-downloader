"""In-app media player preview dialog with playback controls and external player fallback."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, QUrl, QTime
from PySide6.QtGui import QIcon
from ..design_system import DarkThemeTokens


class MediaPlayerDialog(QDialog):
    """Dialog for previewing downloaded audio and video files directly in the application."""

    def __init__(self, file_path: str, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Preview: {Path(file_path).name}")
        self.setMinimumSize(540, 320)
        self.resize(600, 360)

        self._player = None
        self._audio_output = None
        self._video_widget = None
        self._is_slider_down = False

        self._setup_ui()
        self._init_player()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header card
        header_card = QFrame()
        header_card.setObjectName("cardFrame")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)

        self.lbl_title = QLabel(Path(self.file_path).name)
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        self.lbl_title.setWordWrap(True)

        size_mb = os.path.getsize(self.file_path) / (1024 * 1024) if os.path.exists(self.file_path) else 0.0
        self.lbl_meta = QLabel(f"Size: {size_mb:.2f} MB • Path: {self.file_path}")
        self.lbl_meta.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")
        self.lbl_meta.setWordWrap(True)

        h_layout.addWidget(self.lbl_title)
        h_layout.addWidget(self.lbl_meta)
        main_layout.addWidget(header_card)

        # Viewport Area Frame
        self.viewport_frame = QFrame()
        self.viewport_frame.setObjectName("previewCard")
        self.viewport_frame.setStyleSheet(
            f"background-color: #0A0D14; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.08);"
        )
        self.viewport_layout = QVBoxLayout(self.viewport_frame)
        self.viewport_layout.setContentsMargins(0, 0, 0, 0)
        self.viewport_layout.setAlignment(Qt.AlignCenter)

        self.lbl_media_icon = QLabel("🎬 Media File Ready")
        self.lbl_media_icon.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-size: 16px; font-weight: 600;")
        self.viewport_layout.addWidget(self.lbl_media_icon)

        main_layout.addWidget(self.viewport_frame, 1)

        # Scrubber / Timeline Slider
        slider_row = QHBoxLayout()
        slider_row.setSpacing(8)

        self.lbl_time_current = QLabel("00:00")
        self.lbl_time_current.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.sliderMoved.connect(self._on_slider_moved)
        self.timeline_slider.sliderPressed.connect(self._on_slider_pressed)
        self.timeline_slider.sliderReleased.connect(self._on_slider_released)

        self.lbl_time_total = QLabel("00:00")
        self.lbl_time_total.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")

        slider_row.addWidget(self.lbl_time_current)
        slider_row.addWidget(self.timeline_slider, 1)
        slider_row.addWidget(self.lbl_time_total)
        main_layout.addLayout(slider_row)

        # Controls Row (Play/Pause, Stop, Volume, Open in External)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(10)

        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_play_pause.setObjectName("primaryButton")
        self.btn_play_pause.setCursor(Qt.PointingHandCursor)
        self.btn_play_pause.clicked.connect(self._toggle_playback)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setObjectName("secondaryButton")
        self.btn_stop.clicked.connect(self._stop_playback)

        self.btn_external = QPushButton("🚀 Open with System Player")
        self.btn_external.setObjectName("secondaryButton")
        self.btn_external.setCursor(Qt.PointingHandCursor)
        self.btn_external.clicked.connect(self._open_in_system_player)

        controls_row.addWidget(self.btn_play_pause)
        controls_row.addWidget(self.btn_stop)
        controls_row.addStretch()
        controls_row.addWidget(self.btn_external)

        main_layout.addLayout(controls_row)

    def _init_player(self):
        """Initializes PySide6 QtMultimedia backend with graceful fallback."""
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtMultimediaWidgets import QVideoWidget

            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)

            # Check if video format
            ext = Path(self.file_path).suffix.lower()
            if ext in [".mp4", ".mkv", ".webm", ".mov", ".avi"]:
                self._video_widget = QVideoWidget(self)
                self._player.setVideoOutput(self._video_widget)
                self.lbl_media_icon.setVisible(False)
                self.viewport_layout.addWidget(self._video_widget)

            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.playbackStateChanged.connect(self._on_state_changed)

            self._player.setSource(QUrl.fromLocalFile(self.file_path))
        except Exception:
            # Fallback if multimedia drivers aren't present on this system
            self._player = None

    def _toggle_playback(self):
        if not self._player:
            self._open_in_system_player()
            return

        from PySide6.QtMultimedia import QMediaPlayer
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _stop_playback(self):
        if self._player:
            self._player.stop()

    def _on_state_changed(self, state):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.btn_play_pause.setText("⏸ Pause")
            else:
                self.btn_play_pause.setText("▶ Play")
        except Exception:
            pass

    def _on_position_changed(self, position_ms: int):
        if not self._is_slider_down:
            duration = self._player.duration() if self._player else 0
            if duration > 0:
                pos = int(position_ms / duration * 1000)
                self.timeline_slider.setValue(pos)
            self.lbl_time_current.setText(self._format_ms(position_ms))

    def _on_duration_changed(self, duration_ms: int):
        self.lbl_time_total.setText(self._format_ms(duration_ms))

    def _on_slider_pressed(self):
        self._is_slider_down = True

    def _on_slider_released(self):
        self._is_slider_down = False
        if self._player and self._player.duration() > 0:
            target_ms = int(self.timeline_slider.value() / 1000.0 * self._player.duration())
            self._player.setPosition(target_ms)

    def _on_slider_moved(self, val: int):
        if self._player and self._player.duration() > 0:
            target_ms = int(val / 1000.0 * self._player.duration())
            self.lbl_time_current.setText(self._format_ms(target_ms))

    def _format_ms(self, ms: int) -> str:
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m:02d}:{s:02d}"

    def _open_in_system_player(self):
        if not os.path.exists(self.file_path):
            QMessageBox.warning(self, "File Not Found", f"Media file not found on disk:\n{self.file_path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(self.file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.file_path])
            else:
                subprocess.Popen(["xdg-open", self.file_path])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open external player:\n{str(e)}")

    def closeEvent(self, event):
        if self._player:
            self._player.stop()
        super().closeEvent(event)
