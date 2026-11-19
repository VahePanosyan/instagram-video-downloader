"""Repository ports for settings and download history."""

from abc import ABC, abstractmethod
from typing import List
from ..domain.models import AppSettings, DownloadHistoryItem


class ISettingsRepository(ABC):
    """Port for loading and saving application settings."""

    @abstractmethod
    def load(self) -> AppSettings:
        """Loads settings from persistent storage or returns defaults."""
        pass

    @abstractmethod
    def save(self, settings: AppSettings) -> None:
        """Persists settings to storage."""
        pass


class IHistoryRepository(ABC):
    """Port for managing downloaded media history."""

    @abstractmethod
    def get_all(self) -> List[DownloadHistoryItem]:
        """Returns all history items ordered by download date descending."""
        pass

    @abstractmethod
    def add(self, item: DownloadHistoryItem) -> None:
        """Appends a new history item."""
        pass

    @abstractmethod
    def remove(self, item_id: str) -> bool:
        """Removes a history item by ID."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all history items."""
        pass
