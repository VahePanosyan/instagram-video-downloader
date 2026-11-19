"""Active download queue table component with stage badges and telemetry metrics."""

from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QLabel,
    QFrame,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from ..design_system import DarkThemeTokens
from ...domain.models import DownloadRequest, DownloadStatus, DownloadProgress, Platform, enum_value


class QueueTableWidget(QWidget):
    """Table widget presenting live download tasks, stage badges, progress bars, and controls."""
    start_queue_requested = Signal()
    pause_queue_requested = Signal()
    resume_queue_requested = Signal()
    cancel_all_requested = Signal()
    clear_completed_requested = Signal()
    cancel_item_requested = Signal(str)  # req_id
    move_item_up_requested = Signal(str)    # req_id
    move_item_down_requested = Signal(str)  # req_id
    open_file_requested = Signal(str)    # filepath

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._row_map: Dict[str, int] = {}  # req_id -> row_index
        self._is_paused = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Control Toolbar
        toolbar_card = QFrame()
        toolbar_card.setObjectName("cardFrame")
        toolbar_layout = QHBoxLayout(toolbar_card)
        toolbar_layout.setContentsMargins(12, 10, 12, 10)
        toolbar_layout.setSpacing(10)

        self.btn_start = QPushButton("▶ Start Queue")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.clicked.connect(self.start_queue_requested.emit)

        self.btn_pause_resume = QPushButton("⏸ Pause Queue")
        self.btn_pause_resume.setObjectName("secondaryButton")
        self.btn_pause_resume.clicked.connect(self._toggle_pause_resume)

        self.btn_cancel_all = QPushButton("⏹ Cancel All")
        self.btn_cancel_all.setObjectName("dangerButton")
        self.btn_cancel_all.clicked.connect(self.cancel_all_requested.emit)

        self.btn_clear_done = QPushButton("🧹 Clear Completed")
        self.btn_clear_done.setObjectName("secondaryButton")
        self.btn_clear_done.clicked.connect(self.clear_completed_requested.emit)

        self.lbl_queue_stats = QLabel("Queue: 0 tasks")
        self.lbl_queue_stats.setStyleSheet(f"color: {DarkThemeTokens.TEXT_SECONDARY}; font-weight: 600;")

        toolbar_layout.addWidget(self.btn_start)
        toolbar_layout.addWidget(self.btn_pause_resume)
        toolbar_layout.addWidget(self.btn_cancel_all)
        toolbar_layout.addWidget(self.btn_clear_done)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.lbl_queue_stats)

        main_layout.addWidget(toolbar_card)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Stage Status", "Title / Shortcode", "Quality", "Progress", "Telemetry (Speed / ETA)", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 180)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        main_layout.addWidget(self.table, 1)

    def _toggle_pause_resume(self):
        if self._is_paused:
            self._is_paused = False
            self.btn_pause_resume.setText("⏸ Pause Queue")
            self.resume_queue_requested.emit()
        else:
            self._is_paused = True
            self.btn_pause_resume.setText("▶ Resume Queue")
            self.pause_queue_requested.emit()

    def set_paused(self, paused: bool):
        self._is_paused = paused
        if paused:
            self.btn_pause_resume.setText("▶ Resume Queue")
        else:
            self.btn_pause_resume.setText("⏸ Pause Queue")

    def _get_status_badge(self, status: DownloadStatus) -> str:
        color_map = {
            DownloadStatus.QUEUED: (DarkThemeTokens.TEXT_MUTED, "Queued"),
            DownloadStatus.FETCHING_INFO: (DarkThemeTokens.STATUS_INFO, "🔍 Connecting..."),
            DownloadStatus.DOWNLOADING: (DarkThemeTokens.IG_PINK, "⬇️ Downloading"),
            DownloadStatus.PROCESSING: (DarkThemeTokens.STATUS_WARNING, "⚙️ Transcoding"),
            DownloadStatus.COMPLETED: (DarkThemeTokens.STATUS_SUCCESS, "✅ Ready"),
            DownloadStatus.FAILED: (DarkThemeTokens.STATUS_ERROR, "❌ Failed"),
            DownloadStatus.CANCELLED: (DarkThemeTokens.TEXT_MUTED, "⏹ Cancelled"),
        }
        status_enum = DownloadStatus.from_value(status)
        status_str = enum_value(status)
        color, label = color_map.get(status_enum, (DarkThemeTokens.TEXT_MUTED, status_str))
        return f'<span style="color: {color}; font-weight: bold;">● {label}</span>'

    def update_requests(self, requests: List[DownloadRequest]):
        """Refreshes or populates the table with current requests."""
        self.table.setRowCount(len(requests))
        self._row_map.clear()

        for row, req in enumerate(requests):
            self._row_map[req.id] = row

            # 0. Status Stage Badge
            status_lbl = QLabel(self._get_status_badge(req.status))
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 0, status_lbl)

            # 1. Title
            plat = req.media_item.platform if req.media_item else None
            plat_badge = "[YT] " if plat == "youtube" or plat == Platform.YOUTUBE else ("[IG] " if plat == "instagram" or plat == Platform.INSTAGRAM else "")
            title_text = f"{plat_badge}{req.media_item.display_title}" if req.media_item else f"{plat_badge}{req.url}"
            title_item = QTableWidgetItem(title_text)
            self.table.setItem(row, 1, title_item)

            # 2. Quality
            quality_str = enum_value(req.quality)
            quality_item = QTableWidgetItem(quality_str.upper())
            quality_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, quality_item)

            # 3. Progress Bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(req.progress.percent) if req.status != DownloadStatus.COMPLETED else 100)
            self.table.setCellWidget(row, 3, pbar)

            # 4. Telemetry Metrics: Speed / ETA / Size
            if req.status == DownloadStatus.DOWNLOADING:
                details = f"⚡ {req.progress.speed_str} • ⏱️ {req.progress.eta_str}"
            elif req.status == DownloadStatus.COMPLETED:
                details = f"✅ {req.progress.formatted_size}" if req.progress.total_bytes else "✅ Ready"
            elif req.status == DownloadStatus.FAILED:
                details = "❌ Error"
            elif req.status == DownloadStatus.CANCELLED:
                details = "⏹ Cancelled"
            elif req.status == DownloadStatus.PROCESSING:
                details = "⚙️ Transcoding"
            else:
                details = "--"

            details_item = QTableWidgetItem(details)
            details_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, details_item)

            # 5. Action
            action_btn = QPushButton()
            action_btn.setObjectName("secondaryButton")
            action_btn.setFixedSize(70, 26)

            if req.status == DownloadStatus.COMPLETED and req.saved_filepath:
                action_btn.setText("Open")
                filepath = req.saved_filepath
                action_btn.clicked.connect(lambda _, fp=filepath: self.open_file_requested.emit(fp))
            else:
                action_btn.setText("Cancel")
                action_btn.setObjectName("dangerButton")
                action_btn.clicked.connect(lambda _, rid=req.id: self.cancel_item_requested.emit(rid))
                if req.status in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED, DownloadStatus.FAILED]:
                    action_btn.setEnabled(False)

            self.table.setCellWidget(row, 5, action_btn)

        self._update_stats_label(requests)

    def update_item_progress(self, req_id: str, progress: DownloadProgress):
        row = self._row_map.get(req_id)
        if row is not None and row < self.table.rowCount():
            pbar = self.table.cellWidget(row, 3)
            if isinstance(pbar, QProgressBar):
                pbar.setValue(int(progress.percent))
            details_item = self.table.item(row, 4)
            if details_item:
                details_item.setText(f"⚡ {progress.speed_str} • ⏱️ {progress.eta_str}")

    def _update_stats_label(self, requests: List[DownloadRequest]):
        total = len(requests)
        active = sum(1 for r in requests if r.status in [DownloadStatus.DOWNLOADING, DownloadStatus.FETCHING_INFO])
        completed = sum(1 for r in requests if r.status == DownloadStatus.COMPLETED)
        self.lbl_queue_stats.setText(f"Total: {total} | Active: {active} | Done: {completed}")
