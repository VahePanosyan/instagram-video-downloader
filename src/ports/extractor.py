"""Extractor port interface."""

from abc import ABC, abstractmethod
from typing import Optional
from ..domain.models import MediaItem, AppSettings


class IExtractor(ABC):
    """Port for extracting media metadata and streams from an Instagram or YouTube URL."""

    @abstractmethod
    def extract_info(self, url: str, settings: Optional[AppSettings] = None) -> MediaItem:
        """
        Extract metadata for the given Instagram or YouTube URL.
        Returns MediaItem on success, raises ExtractionException on failure.
        """
        pass
