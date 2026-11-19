"""Settings panel component with appearance, network proxy tester, and browser cookies."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from ..design_system import DarkThemeTokens
from ..workers import ProxyTestWorker
from ...domain.models import AppSettings, QualityOption, SubtitleMode, enum_value
from ...adapters.engine_updater import EngineUpdaterAdapter


class SettingsTabWidget(QWidget):
    """Component to manage and persist application configuration."""
    settings_saved = Signal(AppSettings)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_settings = AppSettings()
        self._proxy_worker: Optional[ProxyTestWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)

        title = QLabel("⚙️ Application Preferences & Network Engine")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        card_layout.addWidget(title)

        grid = QGridLayout()
        grid.setVerticalSpacing(14)
        grid.setHorizontalSpacing(12)

        # 1. Download Directory
        lbl_dir = QLabel("Download Folder:")
        lbl_dir.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.txt_download_dir = QLineEdit()
        self.btn_browse_dir = QPushButton("Browse...")
        self.btn_browse_dir.setObjectName("secondaryButton")
        self.btn_browse_dir.clicked.connect(self._on_browse_dir)

        grid.addWidget(lbl_dir, 0, 0)
        grid.addWidget(self.txt_download_dir, 0, 1)
        grid.addWidget(self.btn_browse_dir, 0, 2)

        # 2. Concurrency
        lbl_conc = QLabel("Concurrent Downloads:")
        lbl_conc.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 8)
        self.spin_concurrency.setValue(3)
        self.spin_concurrency.setToolTip("Number of simultaneous download threads (1-8)")

        grid.addWidget(lbl_conc, 1, 0)
        grid.addWidget(self.spin_concurrency, 1, 1)

        # 3. Default Quality
        lbl_quality = QLabel("Default Quality:")
        lbl_quality.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.combo_default_quality = QComboBox()
        for opt in QualityOption:
            self.combo_default_quality.addItem(QualityOption.get_display_name(opt), opt)

        grid.addWidget(lbl_quality, 2, 0)
        grid.addWidget(self.combo_default_quality, 2, 1)

        # 4. Filename Template
        lbl_template = QLabel("Filename Pattern:")
        lbl_template.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.combo_template = QComboBox()
        self.combo_template.setEditable(True)
        self.combo_template.addItem("{author}_{shortcode}")
        self.combo_template.addItem("{shortcode}")
        self.combo_template.addItem("{author}_{title}")

        grid.addWidget(lbl_template, 3, 0)
        grid.addWidget(self.combo_template, 3, 1)

        # 5. Appearance Theme
        lbl_theme = QLabel("Appearance Theme:")
        lbl_theme.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("🌙 Dark Theme (Deep Obsidian)", True)
        self.combo_theme.addItem("☀️ Light Theme (Crisp Slate)", False)

        grid.addWidget(lbl_theme, 4, 0)
        grid.addWidget(self.combo_theme, 4, 1)

        # 6. Browser Cookies Extraction
        lbl_browser = QLabel("Browser Cookies:")
        lbl_browser.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.combo_browser_cookies = QComboBox()
        self.combo_browser_cookies.addItem("None (Manual cookies file or Anonymous)", "")
        self.combo_browser_cookies.addItem("Google Chrome", "chrome")
        self.combo_browser_cookies.addItem("Mozilla Firefox", "firefox")
        self.combo_browser_cookies.addItem("Microsoft Edge", "edge")
        self.combo_browser_cookies.addItem("Brave Browser", "brave")
        self.combo_browser_cookies.addItem("Opera", "opera")
        self.combo_browser_cookies.addItem("Vivaldi", "vivaldi")
        self.combo_browser_cookies.addItem("Chromium", "chromium")

        grid.addWidget(lbl_browser, 5, 0)
        grid.addWidget(self.combo_browser_cookies, 5, 1)

        # 7. Cookies File (Fallback / Manual)
        lbl_cookies = QLabel("Cookies File (.txt):")
        lbl_cookies.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        self.txt_cookies = QLineEdit()
        self.txt_cookies.setPlaceholderText("Path to cookies.txt (for private IG posts/stories & YouTube member videos)")
        self.btn_browse_cookies = QPushButton("Browse...")
        self.btn_browse_cookies.setObjectName("secondaryButton")
        self.btn_browse_cookies.clicked.connect(self._on_browse_cookies)

        grid.addWidget(lbl_cookies, 6, 0)
        grid.addWidget(self.txt_cookies, 6, 1)
        grid.addWidget(self.btn_browse_cookies, 6, 2)

        # 8. Proxy & Tester
        lbl_proxy = QLabel("Proxy Configuration:")
        lbl_proxy.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")

        proxy_layout = QVBoxLayout()
        proxy_layout.setSpacing(6)

        proxy_input_row = QHBoxLayout()
        proxy_input_row.setSpacing(8)
        self.txt_proxy = QLineEdit()
        self.txt_proxy.setPlaceholderText("http://127.0.0.1:8080 or socks5://127.0.0.1:1080")

        self.btn_test_proxy = QPushButton("🧪 Test Proxy")
        self.btn_test_proxy.setObjectName("secondaryButton")
        self.btn_test_proxy.setCursor(Qt.PointingHandCursor)
        self.btn_test_proxy.clicked.connect(self._on_test_proxy)

        proxy_input_row.addWidget(self.txt_proxy, 1)
        proxy_input_row.addWidget(self.btn_test_proxy)

        self.lbl_proxy_status = QLabel("● Proxy not tested")
        self.lbl_proxy_status.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")

        proxy_layout.addLayout(proxy_input_row)
        proxy_layout.addWidget(self.lbl_proxy_status)

        grid.addWidget(lbl_proxy, 7, 0, Qt.AlignmentFlag.AlignTop)
        grid.addLayout(proxy_layout, 7, 1, 1, 2)

        # 9. Subtitles
        lbl_subs = QLabel("Subtitles:")
        lbl_subs.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        subs_layout = QHBoxLayout()
        self.chk_subtitles = QCheckBox("Auto-extract subtitles")
        self.combo_sub_mode = QComboBox()
        self.combo_sub_mode.addItem("External SRT (.srt)", SubtitleMode.EXTERNAL_SRT)
        self.combo_sub_mode.addItem("External VTT (.vtt)", SubtitleMode.EXTERNAL_VTT)
        self.combo_sub_mode.addItem("Embed in MP4 Video", SubtitleMode.EMBED)

        self.txt_sub_langs = QLineEdit("en")
        self.txt_sub_langs.setPlaceholderText("Languages: en, es, all")
        self.txt_sub_langs.setFixedWidth(100)

        subs_layout.addWidget(self.chk_subtitles)
        subs_layout.addWidget(self.combo_sub_mode)
        subs_layout.addWidget(self.txt_sub_langs)
        grid.addWidget(lbl_subs, 8, 0)
        grid.addLayout(subs_layout, 8, 1, 1, 2)

        # 10. Metadata & Artwork
        lbl_meta = QLabel("Tags & Artwork:")
        lbl_meta.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        meta_layout = QVBoxLayout()
        self.chk_embed_thumb = QCheckBox("Embed album artwork & cover thumbnail in MP3/M4A/FLAC")
        self.chk_embed_meta = QCheckBox("Embed metadata tags (Artist, Title, Album) & video chapters")
        meta_layout.addWidget(self.chk_embed_thumb)
        meta_layout.addWidget(self.chk_embed_meta)
        grid.addWidget(lbl_meta, 9, 0, Qt.AlignmentFlag.AlignTop)
        grid.addLayout(meta_layout, 9, 1, 1, 2)

        # 11. Engine & Diagnostics
        lbl_engine = QLabel("Engine & Updates:")
        lbl_engine.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")
        engine_layout = QHBoxLayout()
        self.btn_check_updates = QPushButton("🔄 Check yt-dlp Updates")
        self.btn_check_updates.setObjectName("secondaryButton")
        self.btn_check_updates.clicked.connect(self._on_check_updates)

        self.lbl_update_status = QLabel("● Current engine ready")
        self.lbl_update_status.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 11px;")

        engine_layout.addWidget(self.btn_check_updates)
        engine_layout.addWidget(self.lbl_update_status)
        grid.addWidget(lbl_engine, 10, 0)
        grid.addLayout(engine_layout, 10, 1, 1, 2)

        # 12. Automation & System
        self.chk_auto_paste = QCheckBox("Automatically detect media links in clipboard")
        self.chk_sound = QCheckBox("Play sound when batch completes")
        self.chk_aria2c = QCheckBox("Enable aria2c multi-connection download acceleration")
        self.chk_tray = QCheckBox("Minimize to system tray when closed")

        grid.addWidget(self.chk_auto_paste, 11, 1)
        grid.addWidget(self.chk_sound, 12, 1)
        grid.addWidget(self.chk_aria2c, 13, 1)
        grid.addWidget(self.chk_tray, 14, 1)

        card_layout.addLayout(grid)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_reset.setObjectName("secondaryButton")
        self.btn_reset.clicked.connect(self._on_reset_defaults)

        self.btn_save = QPushButton("💾 Save Settings")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save_settings)

        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_save)

        card_layout.addLayout(btn_layout)
        main_layout.addWidget(card)
        main_layout.addStretch()

    def set_settings(self, settings: AppSettings):
        self._current_settings = settings
        self.txt_download_dir.setText(settings.download_dir)
        self.spin_concurrency.setValue(settings.concurrent_downloads)

        quality_opt = QualityOption.from_value(settings.default_quality)
        index = self.combo_default_quality.findData(quality_opt)
        if index < 0:
            index = self.combo_default_quality.findData(settings.default_quality)
        if index < 0:
            index = self.combo_default_quality.findData(enum_value(settings.default_quality))
        if index < 0:
            index = self.combo_default_quality.findText(QualityOption.get_display_name(settings.default_quality))
        if index >= 0:
            self.combo_default_quality.setCurrentIndex(index)

        self.combo_template.setCurrentText(settings.filename_template)
        self.txt_cookies.setText(settings.cookies_file)
        self.txt_proxy.setText(settings.proxy)
        self.chk_auto_paste.setChecked(settings.auto_paste_clipboard)
        self.chk_sound.setChecked(settings.sound_notifications)

        # Set theme selector
        theme_idx = 0 if getattr(settings, "dark_theme", True) else 1
        self.combo_theme.setCurrentIndex(theme_idx)

        # Set browser cookies
        browser_val = (getattr(settings, "cookies_browser", "") or "").lower()
        b_idx = self.combo_browser_cookies.findData(browser_val)
        if b_idx >= 0:
            self.combo_browser_cookies.setCurrentIndex(b_idx)
        else:
            self.combo_browser_cookies.setCurrentIndex(0)

        # Set subtitles & tags
        self.chk_subtitles.setChecked(getattr(settings, "subtitles_enabled", False))
        sub_mode_idx = self.combo_sub_mode.findData(getattr(settings, "subtitles_mode", SubtitleMode.NONE))
        if sub_mode_idx >= 0:
            self.combo_sub_mode.setCurrentIndex(sub_mode_idx)
        self.txt_sub_langs.setText(getattr(settings, "subtitles_languages", "en"))
        self.chk_embed_thumb.setChecked(getattr(settings, "embed_thumbnail", True))
        self.chk_embed_meta.setChecked(getattr(settings, "embed_metadata", True))
        self.chk_aria2c.setChecked(getattr(settings, "use_aria2c", False))
        self.chk_tray.setChecked(getattr(settings, "close_to_tray", False))

    def _on_browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.txt_download_dir.text())
        if folder:
            self.txt_download_dir.setText(folder)

    def _on_browse_cookies(self):
        cookies_file, _ = QFileDialog.getOpenFileName(
            self, "Select Cookies File", "", "Cookies (*.txt);;All Files (*)"
        )
        if cookies_file:
            self.txt_cookies.setText(cookies_file)

    def _on_test_proxy(self):
        proxy = self.txt_proxy.text().strip()
        if not proxy:
            self.lbl_proxy_status.setText("● Direct connection (No proxy entered)")
            self.lbl_proxy_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_INFO}; font-size: 11px;")
            return

        self.lbl_proxy_status.setText("● Testing proxy connection...")
        self.lbl_proxy_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_WARNING}; font-size: 11px;")
        self.btn_test_proxy.setEnabled(False)

        self._proxy_worker = ProxyTestWorker(proxy, self)
        self._proxy_worker.result.connect(self._on_proxy_test_result)
        self._proxy_worker.start()

    def _on_proxy_test_result(self, success: bool, message: str):
        self.btn_test_proxy.setEnabled(True)
        if success:
            self.lbl_proxy_status.setText(f"● {message}")
            self.lbl_proxy_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_SUCCESS}; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_proxy_status.setText(f"● {message}")
            self.lbl_proxy_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_ERROR}; font-size: 11px; font-weight: bold;")

    def _on_check_updates(self):
        self.lbl_update_status.setText("● Checking PyPI releases...")
        self.lbl_update_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_WARNING}; font-size: 11px;")
        self.btn_check_updates.setEnabled(False)

        try:
            adapter = EngineUpdaterAdapter(proxy=self.txt_proxy.text().strip() or None)
            has_update, curr, latest = adapter.check_for_updates()
            self.btn_check_updates.setEnabled(True)
            if has_update:
                self.lbl_update_status.setText(f"● Update available: {curr} ➔ {latest}")
                self.lbl_update_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_SUCCESS}; font-size: 11px; font-weight: bold;")
                reply = QMessageBox.question(
                    self,
                    "Update Available",
                    f"A newer version of yt-dlp is available ({latest}).\nCurrent version is {curr}.\n\nWould you like to update now?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.lbl_update_status.setText("● Updating engine via pip...")
                    res = adapter.perform_update()
                    if res:
                        QMessageBox.information(self, "Updated", "yt-dlp has been updated successfully!")
                        self.lbl_update_status.setText(f"● Successfully updated to {latest}")
                    else:
                        QMessageBox.warning(self, "Update Failed", "Engine update could not be completed.")
                        self.lbl_update_status.setText("● Update failed")
            else:
                self.lbl_update_status.setText(f"● Engine is up-to-date (v{curr})")
                self.lbl_update_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_SUCCESS}; font-size: 11px;")
        except Exception as e:
            self.btn_check_updates.setEnabled(True)
            self.lbl_update_status.setText(f"● Check failed: {str(e)[:25]}")
            self.lbl_update_status.setStyleSheet(f"color: {DarkThemeTokens.STATUS_ERROR}; font-size: 11px;")

    def _on_save_settings(self):
        quality_data = self.combo_default_quality.currentData() or self.combo_default_quality.currentText()
        quality = QualityOption.from_value(quality_data)
        is_dark = self.combo_theme.currentData()
        if is_dark is None:
            is_dark = True
        browser_choice = self.combo_browser_cookies.currentData() or ""

        sub_mode = self.combo_sub_mode.currentData() or SubtitleMode.NONE

        new_settings = AppSettings(
            download_dir=self.txt_download_dir.text().strip(),
            concurrent_downloads=self.spin_concurrency.value(),
            default_quality=quality,
            filename_template=self.combo_template.currentText().strip() or "{author}_{shortcode}",
            cookies_file=self.txt_cookies.text().strip(),
            proxy=self.txt_proxy.text().strip(),
            auto_paste_clipboard=self.chk_auto_paste.isChecked(),
            sound_notifications=self.chk_sound.isChecked(),
            dark_theme=bool(is_dark),
            cookies_browser=str(browser_choice),
            subtitles_enabled=self.chk_subtitles.isChecked(),
            subtitles_mode=sub_mode,
            subtitles_languages=self.txt_sub_langs.text().strip() or "en",
            embed_thumbnail=self.chk_embed_thumb.isChecked(),
            embed_metadata=self.chk_embed_meta.isChecked(),
            use_aria2c=self.chk_aria2c.isChecked(),
            close_to_tray=self.chk_tray.isChecked(),
        )
        self.settings_saved.emit(new_settings)
        QMessageBox.information(self, "Settings Saved", "Your preferences have been saved successfully.")

    def _on_reset_defaults(self):
        defaults = AppSettings()
        self.set_settings(defaults)
