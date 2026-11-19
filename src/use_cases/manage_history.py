"""Use case for managing download history."""

import os
from typing import List
from ..domain.models import DownloadHistoryItem
from ..ports.repository import IHistoryRepository


class ManageHistoryUseCase:
    """Manages reading, filtering, and deleting downloaded media history."""

    def __init__(self, history_repo: IHistoryRepository):
        self._repo = history_repo

    def get_history(self) -> List[DownloadHistoryItem]:
        return self._repo.get_all()

    def search_history(self, query: str) -> List[DownloadHistoryItem]:
        q = query.lower().strip()
        if not q:
            return self.get_history()

        items = self._repo.get_all()
        return [
            item for item in items
            if q in item.title.lower() or q in item.author.lower() or q in item.url.lower()
        ]

    def remove_item(self, item_id: str, delete_file: bool = False) -> bool:
        if delete_file:
            for item in self._repo.get_all():
                if item.id == item_id:
                    if os.path.exists(item.file_path):
                        try:
                            os.remove(item.file_path)
                        except OSError:
                            pass
                    break
        return self._repo.remove(item_id)

    def clear_history(self) -> None:
        self._repo.clear()
