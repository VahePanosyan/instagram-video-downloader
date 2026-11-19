"""Application header component with branding and theme toggle."""

from typing import Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from ..design_system import DarkThemeTokens, LightThemeTokens


class HeaderWidget(QWidget):
    """Header banner with Instagram branding, title, theme toggle, and quick action bar."""
    open_downloads_requested = Signal()
    theme_toggle_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self._is_dark: bool = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Title & Subtitle
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_label = QLabel("⚡ INSTAGRAM & YOUTUBE VIDEO DOWNLOADER")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(f"color: {DarkThemeTokens.TEXT_PRIMARY};")

        self.subtitle_label = QLabel("Reels • Shorts • Videos • Playlists • Posts • Stories • Audio MP3/WAV/FLAC • Batch Engine")
        self.subtitle_label.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout)
        layout.addStretch()

        # Action: Theme Toggle Button
        self.btn_theme_toggle = QPushButton("☀️ Light")
        self.btn_theme_toggle.setObjectName("secondaryButton")
        self.btn_theme_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_theme_toggle.setToolTip("Switch to Light Theme")
        self.btn_theme_toggle.clicked.connect(self.theme_toggle_requested.emit)
        layout.addWidget(self.btn_theme_toggle)

        # Action: Open Downloads Folder
        self.btn_open_folder = QPushButton("📂 Open Downloads Folder")
        self.btn_open_folder.setObjectName("secondaryButton")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self.open_downloads_requested.emit)
        layout.addWidget(self.btn_open_folder)

    def set_theme(self, is_dark: bool):
        """Updates header text and toggle button according to active theme."""
        self._is_dark = is_dark
        tokens = DarkThemeTokens if is_dark else LightThemeTokens
        self.title_label.setStyleSheet(f"color: {tokens.TEXT_PRIMARY}; font-size: 16px; font-weight: bold;")
        self.subtitle_label.setStyleSheet(f"color: {tokens.TEXT_MUTED}; font-size: 11px;")

        if is_dark:
            self.btn_theme_toggle.setText("☀️ Light")
            self.btn_theme_toggle.setToolTip("Switch to Light Theme")
        else:
            self.btn_theme_toggle.setText("🌙 Dark")
            self.btn_theme_toggle.setToolTip("Switch to Dark Theme")

    def update_theme_icon(self, is_dark_or_theme_name):
        """Helper alias supporting either bool or string theme name."""
        if isinstance(is_dark_or_theme_name, str):
            is_dark = is_dark_or_theme_name.lower() == "dark"
        else:
            is_dark = bool(is_dark_or_theme_name)
        self.set_theme(is_dark)
