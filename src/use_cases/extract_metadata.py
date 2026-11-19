"""Use case for extracting metadata with caching optimization."""

from typing import Dict, Optional, Any
import time
from ..domain.models import MediaItem, AppSettings
from ..domain.url_parser import MediaUrlParser
from ..ports.extractor import IExtractor
from ..adapters.direct_scraper import UniversalDirectScraper


class ExtractMetadataUseCase:
    """Use case to parse and extract metadata for Instagram & YouTube media with memory caching."""

    def __init__(
        self,
        extractor: IExtractor,
        fallback_scraper: Optional[Any] = None,
        cache_ttl_seconds: int = 300,
    ):
        self._extractor = extractor
        self._fallback_scraper = fallback_scraper or UniversalDirectScraper()
        self._cache_ttl = cache_ttl_seconds
        # In-memory cache: canonical_url -> (timestamp, MediaItem)
        self._cache: Dict[str, tuple[float, MediaItem]] = {}

    def execute(self, raw_url: str, settings: Optional[AppSettings] = None, force_refresh: bool = False) -> MediaItem:
        _, _, _, canonical_url = MediaUrlParser.parse(raw_url)

        now = time.time()
        if not force_refresh and canonical_url in self._cache:
            ts, cached_item = self._cache[canonical_url]
            if now - ts < self._cache_ttl:
                return cached_item

        try:
            media_item = self._extractor.extract_info(canonical_url, settings=settings)
            self._cache[canonical_url] = (now, media_item)
            return media_item
        except Exception:
            if self._fallback_scraper:
                try:
                    fallback_item = self._fallback_scraper.quick_preview(canonical_url)
                    if fallback_item and (fallback_item.title or fallback_item.author or fallback_item.thumbnail_url):
                        self._cache[canonical_url] = (now, fallback_item)
                        return fallback_item
                except Exception:
                    pass
            raise

    def get_cached(self, raw_url: str) -> Optional[MediaItem]:
        try:
            _, _, _, canonical_url = MediaUrlParser.parse(raw_url)
            if canonical_url in self._cache:
                return self._cache[canonical_url][1]
        except Exception:
            pass
        return None

    def clear_cache(self) -> None:
        self._cache.clear()
