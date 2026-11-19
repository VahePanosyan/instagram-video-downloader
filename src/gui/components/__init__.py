"""GUI components package initialization."""

from .header import HeaderWidget
from .url_input import SingleUrlWidget
from .batch_tab import BatchTabWidget
from .queue_table import QueueTableWidget
from .history_tab import HistoryTabWidget
from .settings_tab import SettingsTabWidget
from .media_player_dialog import MediaPlayerDialog

__all__ = [
    "HeaderWidget",
    "SingleUrlWidget",
    "BatchTabWidget",
    "QueueTableWidget",
    "HistoryTabWidget",
    "SettingsTabWidget",
    "MediaPlayerDialog",
]
