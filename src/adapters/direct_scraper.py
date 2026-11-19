"""Direct Instagram scraper and oEmbed metadata adapter."""

import json
import re
from typing import Optional, Dict, Any
import urllib.request
import urllib.parse
from ..domain.models import MediaItem, MediaType, Platform
from ..domain.url_parser import InstagramUrlParser, YouTubeUrlParser, MediaUrlParser


class DirectInstagramScraper:
    """Fast lightweight metadata fetcher using Instagram's public oEmbed service."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy

    def fetch_oembed(self, url: str, timeout: int = 8, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetches public metadata from Instagram oEmbed API."""
        try:
            encoded_url = urllib.parse.quote(url)
            endpoint = f"https://www.instagram.com/oembed/?url={encoded_url}"
            req = urllib.request.Request(
                endpoint,
                headers={
                    "User-Agent": self.DEFAULT_USER_AGENT,
                    "Accept": "application/json",
                },
            )
            active_proxy = proxy or self._proxy
            if active_proxy and active_proxy.strip():
                p = active_proxy.strip()
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', p):
                    p = f"http://{p}"
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({'http': p, 'https': p})
                )
                with opener.open(req, timeout=timeout) as response:
                    if response.status == 200:
                        data = response.read().decode("utf-8")
                        return json.loads(data)
            else:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.status == 200:
                        data = response.read().decode("utf-8")
                        return json.loads(data)
        except Exception:
            # oEmbed might fail if account is private or rate-limited; gracefully return None
            return None
        return None

    def quick_preview(self, url: str, proxy: Optional[str] = None) -> MediaItem:
        """Constructs a preliminary MediaItem using URL parser and oEmbed if available."""
        media_type, shortcode, canonical = InstagramUrlParser.parse(url)
        oembed_data = self.fetch_oembed(canonical, proxy=proxy)

        title = ""
        author = ""
        thumbnail_url = None

        if oembed_data:
            title = oembed_data.get("title", "")
            author = oembed_data.get("author_name", "")
            thumbnail_url = oembed_data.get("thumbnail_url")

        return MediaItem(
            url=canonical,
            shortcode=shortcode,
            media_type=media_type,
            title=title,
            author=author,
            thumbnail_url=thumbnail_url,
        )


class DirectYouTubeScraper:
    """Fast lightweight metadata fetcher using YouTube's public oEmbed service."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy

    def fetch_oembed(self, url: str, timeout: int = 8, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetches public metadata from YouTube oEmbed API."""
        try:
            encoded_url = urllib.parse.quote(url)
            endpoint = f"https://www.youtube.com/oembed?url={encoded_url}&format=json"
            req = urllib.request.Request(
                endpoint,
                headers={
                    "User-Agent": self.DEFAULT_USER_AGENT,
                    "Accept": "application/json",
                },
            )
            active_proxy = proxy or self._proxy
            if active_proxy and active_proxy.strip():
                p = active_proxy.strip()
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', p):
                    p = f"http://{p}"
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({'http': p, 'https': p})
                )
                with opener.open(req, timeout=timeout) as response:
                    if response.status == 200:
                        data = response.read().decode("utf-8")
                        return json.loads(data)
            else:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.status == 200:
                        data = response.read().decode("utf-8")
                        return json.loads(data)
        except Exception:
            return None
        return None

    def quick_preview(self, url: str, proxy: Optional[str] = None) -> MediaItem:
        """Constructs a preliminary MediaItem using YouTube URL parser and oEmbed."""
        media_type, video_id, canonical = YouTubeUrlParser.parse(url)
        oembed_data = self.fetch_oembed(canonical, proxy=proxy)

        title = ""
        author = ""
        thumbnail_url = None

        if oembed_data:
            title = oembed_data.get("title", "")
            author = oembed_data.get("author_name", "")
            thumbnail_url = oembed_data.get("thumbnail_url")
        else:
            # Fallback high quality YouTube thumbnail URL
            if video_id and media_type != MediaType.PLAYLIST:
                thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        return MediaItem(
            url=canonical,
            shortcode=video_id,
            media_type=media_type,
            platform=Platform.YOUTUBE,
            title=title,
            author=author,
            thumbnail_url=thumbnail_url,
            is_playlist=(media_type == MediaType.PLAYLIST),
        )


class UniversalDirectScraper:
    """Routes oEmbed metadata preview requests according to detected platform."""

    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy
        self._ig_scraper = DirectInstagramScraper(proxy=proxy)
        self._yt_scraper = DirectYouTubeScraper(proxy=proxy)

    def quick_preview(self, url: str, proxy: Optional[str] = None) -> MediaItem:
        platform = MediaUrlParser.detect_platform(url)
        active_proxy = proxy or self._proxy
        if platform == Platform.YOUTUBE:
            return self._yt_scraper.quick_preview(url, proxy=active_proxy)
        return self._ig_scraper.quick_preview(url, proxy=active_proxy)
