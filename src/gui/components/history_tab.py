"""Download history management component with search, platform badges, and file actions."""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QFrame,
    QHeaderView,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from ..design_system import DarkThemeTokens
from ...domain.models import DownloadHistoryItem


class HistoryTabWidget(QWidget):
    """Component to browse, search, filter, open, and manage downloaded video and audio history."""
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)
    delete_item_requested = Signal(str, bool)  # item_id, delete_disk_file
    clear_all_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_items: List[DownloadHistoryItem] = []
        self._active_platform_filter: str = "all"
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Top Bar: Search & Quick Filter Pills & Clear
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search history by title, creator, URL, or platform...")
        self.search_input.textChanged.connect(self._on_search_text_changed)

        self.lbl_stats = QLabel("0 downloads")
        self.lbl_stats.setStyleSheet(f"color: {DarkThemeTokens.TEXT_MUTED}; font-size: 12px; font-weight: 600;")

        self.btn_clear_all = QPushButton("🧹 Clear All")
        self.btn_clear_all.setObjectName("dangerButton")
        self.btn_clear_all.clicked.connect(self._on_clear_click)

        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.lbl_stats)
        search_row.addWidget(self.btn_clear_all)
        card_layout.addLayout(search_row)

        # Filter Pills Row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        lbl_filter = QLabel("Filter:")
        lbl_filter.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600; font-size: 12px;")
        filter_row.addWidget(lbl_filter)

        self.btn_filter_all = QPushButton("All")
        self.btn_filter_all.setObjectName("secondaryButton")
        self.btn_filter_all.setFixedHeight(26)
        self.btn_filter_all.clicked.connect(lambda: self._set_platform_filter("all"))

        self.btn_filter_ig = QPushButton("📸 Instagram")
        self.btn_filter_ig.setObjectName("secondaryButton")
        self.btn_filter_ig.setFixedHeight(26)
        self.btn_filter_ig.clicked.connect(lambda: self._set_platform_filter("instagram"))

        self.btn_filter_yt = QPushButton("▶️ YouTube")
        self.btn_filter_yt.setObjectName("secondaryButton")
        self.btn_filter_yt.setFixedHeight(26)
        self.btn_filter_yt.clicked.connect(lambda: self._set_platform_filter("youtube"))

        self.btn_filter_audio = QPushButton("🎵 Audio Only")
        self.btn_filter_audio.setObjectName("secondaryButton")
        self.btn_filter_audio.setFixedHeight(26)
        self.btn_filter_audio.clicked.connect(lambda: self._set_platform_filter("audio"))

        filter_row.addWidget(self.btn_filter_all)
        filter_row.addWidget(self.btn_filter_ig)
        filter_row.addWidget(self.btn_filter_yt)
        filter_row.addWidget(self.btn_filter_audio)
        filter_row.addStretch()

        card_layout.addLayout(filter_row)
        main_layout.addWidget(card)

        # History Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Title", "Platform & Creator", "Format", "Size", "Date", "Quick Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        main_layout.addWidget(self.table, 1)

    def load_history(self, items: List[DownloadHistoryItem]):
        self._current_items = items
        self._filter_and_populate()

    def _set_platform_filter(self, filter_name: str):
        self._active_platform_filter = filter_name.lower()
        self._filter_and_populate()

    def _on_search_text_changed(self, query: str = ""):
        self._filter_and_populate(query)

    def _filter_and_populate(self, query: Optional[str] = None):
        if query is None or not isinstance(query, str):
            q = self.search_input.text().strip().lower()
        else:
            q = query.strip().lower()
        p_filter = self._active_platform_filter

        def matches(it: DownloadHistoryItem) -> bool:
            # Platform category filter
            plat = str(getattr(it, "platform", "")).lower()
            quality = str(getattr(it, "quality", "")).lower()
            if p_filter == "instagram" and "instagram" not in plat:
                return False
            if p_filter == "youtube" and "youtube" not in plat:
                return False
            if p_filter == "audio" and quality not in ["mp3", "m4a", "wav", "flac"]:
                return False

            # Search text match
            if not q:
                return True
            title = (it.title or "").lower()
            author = (it.author or "").lower()
            url = (it.url or "").lower()
            return q in title or q in author or q in url or q in plat

        filtered = [it for it in self._current_items if matches(it)]
        self._populate_table(filtered)

    def _populate_table(self, items: List[DownloadHistoryItem]):
        self.table.setRowCount(len(items))
        total_bytes = 0

        for row, it in enumerate(items):
            total_bytes += it.file_size_bytes
            plat = getattr(it, "platform", "")

            # 0. Title (kept pure title so table.item(0, 0).text() matches tests)
            default_title = "YouTube Video" if plat == "youtube" else "Instagram Video"
            title_text = it.title or default_title
            title_item = QTableWidgetItem(title_text)
            self.table.setItem(row, 0, title_item)

            # 1. Platform & Creator
            plat_badge = "[YT] " if plat == "youtube" else "[IG] "
            if plat == "youtube":
                creator_str = f"{plat_badge}{it.author}" if it.author else f"{plat_badge}YouTube Channel"
            else:
                author_handle = f"@{it.author}" if it.author and not it.author.startswith("@") else (it.author or "Unknown")
                creator_str = f"{plat_badge}{author_handle}"
            author_item = QTableWidgetItem(creator_str)
            self.table.setItem(row, 1, author_item)

            # 2. Format
            quality_str = it.quality.upper() if it.quality else "BEST"
            quality_item = QTableWidgetItem(quality_str)
            quality_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, quality_item)

            # 3. Size
            size_item = QTableWidgetItem(it.formatted_size)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, size_item)

            # 4. Date
            date_str = it.downloaded_at.replace("T", " ")[:16] if it.downloaded_at else "--"
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, date_item)

            # 5. Quick Actions: Open File, Open Folder, Delete
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            btn_open_file = QPushButton("📂 Open")
            btn_open_file.setObjectName("secondaryButton")
            btn_open_file.setToolTip("Open media file in default player")
            btn_open_file.setFixedSize(65, 26)
            btn_open_file.clicked.connect(lambda _, p=it.file_path: self.open_file_requested.emit(p))

            btn_open_folder = QPushButton("📁 Folder")
            btn_open_folder.setObjectName("secondaryButton")
            btn_open_folder.setToolTip("Show file in folder")
            btn_open_folder.setFixedSize(65, 26)
            btn_open_folder.clicked.connect(lambda _, p=it.file_path: self.open_folder_requested.emit(p))

            btn_del = QPushButton("🗑")
            btn_del.setObjectName("dangerButton")
            btn_del.setToolTip("Remove from history")
            btn_del.setFixedSize(30, 26)
            btn_del.clicked.connect(lambda _, i=it.id: self._on_delete_click(i))

            actions_layout.addWidget(btn_open_file)
            actions_layout.addWidget(btn_open_folder)
            actions_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 5, actions_widget)

        total_mb = total_bytes / (1024 * 1024)
        count = len(items)
        self.lbl_stats.setText(f"{count} file{'s' if count != 1 else ''} • {total_mb:.1f} MB")

    def _on_delete_click(self, item_id: str):
        reply = QMessageBox.question(
            self,
            "Remove Item",
            "Do you also want to delete the file from your computer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return
        delete_disk_file = (reply == QMessageBox.StandardButton.Yes)
        self.delete_item_requested.emit(item_id, delete_disk_file)

    def _on_clear_click(self):
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to clear your download history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_all_requested.emit()
