"""Integrated Event Log Console component for monitoring background operations and errors."""

import datetime
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QPlainTextEdit,
    QFrame,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCursor
from ..design_system import DarkThemeTokens, LightThemeTokens


class LogSignalBridge(QObject):
    """Thread-safe signal dispatcher for logging events across QThread boundaries."""
    log_emitted = Signal(str, str, str)  # timestamp, level, message


class QtLoggingHandler(logging.Handler):
    """Custom Python logging handler dispatching records to the GUI EventLogWidget."""

    def __init__(self, bridge: LogSignalBridge):
        super().__init__()
        self.bridge = bridge

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            timestamp = datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            level = record.levelname.upper()
            self.bridge.log_emitted.emit(timestamp, level, msg)
        except Exception:
            self.handleError(record)


class EventLogWidget(QWidget):
    """Dockable/collapsible event log console with severity coloring, search, and filtering."""
    log_requested = Signal(str, str)  # level, message

    LEVEL_COLORS = {
        "INFO": DarkThemeTokens.STATUS_INFO,
        "SUCCESS": DarkThemeTokens.STATUS_SUCCESS,
        "WARNING": DarkThemeTokens.STATUS_WARNING,
        "ERROR": DarkThemeTokens.STATUS_ERROR,
        "DEBUG": DarkThemeTokens.TEXT_MUTED,
    }

    def __init__(self, parent: Optional[QWidget] = None, collapsed: bool = True):
        super().__init__(parent)
        self._is_collapsed: bool = collapsed
        self._all_entries: list = []  # list of tuples: (timestamp, level, message, html)
        self._is_dark: bool = True

        self._signal_bridge = LogSignalBridge()
        self._signal_bridge.log_emitted.connect(self._on_log_emitted)
        self.log_requested.connect(self._on_log_requested)

        self._setup_ui()
        self.set_collapsed(self._is_collapsed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Toolbar
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setObjectName("cardFrame")
        self.toolbar_frame.setFixedHeight(40)
        self.toolbar_frame.setStyleSheet("border-radius: 0px; padding: 4px 12px;")
        toolbar_layout = QHBoxLayout(self.toolbar_frame)
        toolbar_layout.setContentsMargins(12, 4, 12, 4)
        toolbar_layout.setSpacing(10)

        self.btn_toggle_collapse = QPushButton("▲ Logs")
        self.btn_toggle_collapse.setObjectName("secondaryButton")
        self.btn_toggle_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_collapse.setFixedHeight(26)
        self.btn_toggle_collapse.clicked.connect(self._toggle_collapse)

        self.lbl_title = QLabel("📋 Event Log Console")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 12px;")

        self.combo_filter = QComboBox()
        self.combo_filter.setFixedHeight(26)
        self.combo_filter.addItems(["All Levels", "INFO", "SUCCESS", "WARNING", "ERROR"])
        self.combo_filter.currentTextChanged.connect(self._apply_filter)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filter logs...")
        self.txt_search.setFixedHeight(26)
        self.txt_search.textChanged.connect(self._apply_filter)

        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)

        self.btn_copy = QPushButton("📋 Copy")
        self.btn_copy.setObjectName("secondaryButton")
        self.btn_copy.setFixedHeight(26)
        self.btn_copy.setToolTip("Copy all logs to clipboard")
        self.btn_copy.clicked.connect(self._on_copy_click)

        self.btn_clear = QPushButton("🧹 Clear")
        self.btn_clear.setObjectName("secondaryButton")
        self.btn_clear.setFixedHeight(26)
        self.btn_clear.setToolTip("Clear log view")
        self.btn_clear.clicked.connect(self.clear_logs)

        toolbar_layout.addWidget(self.btn_toggle_collapse)
        toolbar_layout.addWidget(self.lbl_title)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.combo_filter)
        toolbar_layout.addWidget(self.txt_search)
        toolbar_layout.addWidget(self.chk_autoscroll)
        toolbar_layout.addWidget(self.btn_copy)
        toolbar_layout.addWidget(self.btn_clear)

        main_layout.addWidget(self.toolbar_frame)

        # 2. Text Log Display
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setFixedHeight(130)

        main_layout.addWidget(self.log_view)

    def set_theme(self, is_dark: bool):
        """Updates styling and colors according to active theme."""
        self._is_dark = is_dark
        tokens = DarkThemeTokens if is_dark else LightThemeTokens
        self.LEVEL_COLORS = {
            "INFO": tokens.STATUS_INFO,
            "SUCCESS": tokens.STATUS_SUCCESS,
            "WARNING": tokens.STATUS_WARNING,
            "ERROR": tokens.STATUS_ERROR,
            "DEBUG": tokens.TEXT_MUTED,
        }
        self._refresh_display()

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self.log_view.setVisible(not collapsed)
        if collapsed:
            self.btn_toggle_collapse.setText("▲ Show Logs")
            self.btn_toggle_collapse.setToolTip("Expand Event Log Console")
            self.setFixedHeight(40)
        else:
            self.btn_toggle_collapse.setText("▼ Hide Logs")
            self.btn_toggle_collapse.setToolTip("Collapse Event Log Console")
            self.setFixedHeight(170)

    def _toggle_collapse(self):
        self.set_collapsed(not self._is_collapsed)

    def get_logging_handler(self) -> logging.Handler:
        """Returns a logging handler configured to pipe records into this widget."""
        return QtLoggingHandler(self._signal_bridge)

    def log(self, level: str, message: str):
        """Thread-safe method to append a log message."""
        self.log_requested.emit(level, message)

    def info(self, message: str):
        self.log("INFO", message)

    def success(self, message: str):
        self.log("SUCCESS", message)

    def warning(self, message: str):
        self.log("WARNING", message)

    def error(self, message: str):
        self.log("ERROR", message)

    def _on_log_requested(self, level: str, message: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._on_log_emitted(now, level, message)

    def _on_log_emitted(self, timestamp: str, level: str, message: str):
        level_upper = level.upper()
        tokens = DarkThemeTokens if self._is_dark else LightThemeTokens
        color = self.LEVEL_COLORS.get(level_upper, tokens.TEXT_PRIMARY)
        plain_line = f"[{timestamp}] [{level_upper:<7}] {message}"
        self._all_entries.append((timestamp, level_upper, message, plain_line))

        # Check if current entry matches active filter
        if self._matches_filter(level_upper, message):
            self.log_view.appendPlainText(plain_line)
            if self.chk_autoscroll.isChecked():
                self.log_view.moveCursor(QTextCursor.End)

    def _matches_filter(self, level: str, message: str) -> bool:
        target_level = self.combo_filter.currentText()
        if target_level != "All Levels" and level != target_level:
            return False
        search_query = self.txt_search.text().strip().lower()
        if search_query and search_query not in message.lower():
            return False
        return True

    def _apply_filter(self):
        self._refresh_display()

    def _refresh_display(self):
        self.log_view.clear()
        for ts, lvl, msg, plain_line in self._all_entries:
            if self._matches_filter(lvl, msg):
                self.log_view.appendPlainText(plain_line)
        if self.chk_autoscroll.isChecked():
            self.log_view.moveCursor(QTextCursor.End)

    def _on_copy_click(self):
        text = self.log_view.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def clear_logs(self):
        self._all_entries.clear()
        self.log_view.clear()
