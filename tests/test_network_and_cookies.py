"""Tests for network settings, proxy normalization, cookie files, and browser cookies."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.adapters.direct_scraper import (
    DirectInstagramScraper,
    DirectYouTubeScraper,
    UniversalDirectScraper,
)
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.domain.models import AppSettings, Platform
from src.gui.workers import ThumbnailLoaderWorker


# ---------------------------------------------------------------------------
# 1. YtDlpAdapter Proxy Normalization Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_proxy,expected_normalized",
    [
        ("127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("proxy.corporate.net:3128", "http://proxy.corporate.net:3128"),
        ("  192.168.1.50:8888  ", "http://192.168.1.50:8888"),
        ("http://proxy.local:8080", "http://proxy.local:8080"),
        ("https://secure-proxy.com:8443", "https://secure-proxy.com:8443"),
        ("socks5://127.0.0.1:1080", "socks5://127.0.0.1:1080"),
        ("socks5h://user:secret@10.0.0.1:1080", "socks5h://user:secret@10.0.0.1:1080"),
        ("socks4://127.0.0.1:1080", "socks4://127.0.0.1:1080"),
    ],
)
def test_ytdlp_proxy_normalization(raw_proxy, expected_normalized):
    """Verify schemeless proxies gain http:// scheme and explicit schemes are preserved."""
    adapter = YtDlpAdapter()
    settings = AppSettings(proxy=raw_proxy)
    opts = adapter._build_base_options(settings)

    assert "proxy" in opts
    assert opts["proxy"] == expected_normalized


@pytest.mark.parametrize("empty_proxy", ["", "   ", None])
def test_ytdlp_empty_proxy_not_set_in_options(empty_proxy):
    """Verify empty or whitespace-only proxy does not inject proxy key into yt-dlp options."""
    adapter = YtDlpAdapter()
    settings = AppSettings(proxy=empty_proxy or "")
    opts = adapter._build_base_options(settings)

    assert "proxy" not in opts


# ---------------------------------------------------------------------------
# 2. Cookies File and Browser Cookies Tests
# ---------------------------------------------------------------------------

def test_app_settings_cookies_browser_serialization():
    """Verify cookies_browser field serialization and deserialization in AppSettings."""
    settings = AppSettings(cookies_browser="Chrome", proxy="http://127.0.0.1:8080")
    data = settings.to_dict()
    assert data["cookies_browser"] == "Chrome"
    assert data["proxy"] == "http://127.0.0.1:8080"

    restored = AppSettings.from_dict(data)
    assert restored.cookies_browser == "Chrome"
    assert restored.proxy == "http://127.0.0.1:8080"


@pytest.mark.parametrize(
    "browser_input,expected_browser",
    [
        ("Chrome", "chrome"),
        ("FIREFOX", "firefox"),
        ("  Edge  ", "edge"),
        ("Brave", "brave"),
        ("Opera", "opera"),
        ("Vivaldi", "vivaldi"),
    ],
)
def test_ytdlp_cookies_from_browser_injection(browser_input, expected_browser):
    """Verify cookiesfrombrowser option is lowercased and formatted as a single-element tuple."""
    adapter = YtDlpAdapter()
    settings = AppSettings(cookies_browser=browser_input)
    opts = adapter._build_base_options(settings)

    assert "cookiesfrombrowser" in opts
    assert opts["cookiesfrombrowser"] == (expected_browser,)


@pytest.mark.parametrize("empty_browser", ["", "   ", None])
def test_ytdlp_empty_cookies_from_browser_ignored(empty_browser):
    """Verify blank cookies_browser setting does not add cookiesfrombrowser option."""
    adapter = YtDlpAdapter()
    settings = AppSettings(cookies_browser=empty_browser or "")
    opts = adapter._build_base_options(settings)

    assert "cookiesfrombrowser" not in opts


def test_ytdlp_cookies_file_existing(tmp_path):
    """Verify existing cookiefile path is injected into yt-dlp options."""
    cookie_file = tmp_path / "instagram_cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n")

    adapter = YtDlpAdapter()
    settings = AppSettings(cookies_file=str(cookie_file))
    opts = adapter._build_base_options(settings)

    assert "cookiefile" in opts
    assert opts["cookiefile"] == str(cookie_file)


def test_ytdlp_cookies_file_non_existent(tmp_path):
    """Verify non-existent cookies_file path is omitted to prevent yt-dlp initialization error."""
    missing_file = tmp_path / "does_not_exist.txt"

    adapter = YtDlpAdapter()
    settings = AppSettings(cookies_file=str(missing_file))
    opts = adapter._build_base_options(settings)

    assert "cookiefile" not in opts


# ---------------------------------------------------------------------------
# 3. Direct Scrapers Proxy Support Tests
# ---------------------------------------------------------------------------

def test_direct_instagram_scraper_proxy_initialization():
    """Verify DirectInstagramScraper stores proxy attribute."""
    scraper = DirectInstagramScraper(proxy="127.0.0.1:8080")
    assert scraper._proxy == "127.0.0.1:8080"


def test_direct_instagram_scraper_fetch_oembed_with_proxy():
    """Verify fetch_oembed builds opener with ProxyHandler when proxy is configured."""
    scraper = DirectInstagramScraper(proxy="127.0.0.1:8080")

    with patch("urllib.request.build_opener") as mock_build_opener, \
         patch("urllib.request.ProxyHandler") as mock_proxy_handler:

        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"title": "Test Title", "author_name": "test_user"}'
        mock_opener.open.return_value.__enter__.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        result = scraper.fetch_oembed("https://www.instagram.com/reel/C123abc/")

        assert result is not None
        assert result["title"] == "Test Title"
        mock_proxy_handler.assert_called_once_with({
            "http": "http://127.0.0.1:8080",
            "https": "http://127.0.0.1:8080",
        })
        mock_build_opener.assert_called_once()


def test_direct_instagram_scraper_fetch_oembed_proxy_parameter_override():
    """Verify fetch_oembed proxy parameter overrides instance proxy."""
    scraper = DirectInstagramScraper(proxy="127.0.0.1:8080")

    with patch("urllib.request.build_opener") as mock_build_opener, \
         patch("urllib.request.ProxyHandler") as mock_proxy_handler:

        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"title": "Custom Proxy Title"}'
        mock_opener.open.return_value.__enter__.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        result = scraper.fetch_oembed(
            "https://www.instagram.com/reel/C123abc/",
            proxy="socks5://localhost:1080",
        )

        assert result is not None
        mock_proxy_handler.assert_called_once_with({
            "http": "socks5://localhost:1080",
            "https": "socks5://localhost:1080",
        })


def test_direct_instagram_scraper_fetch_oembed_without_proxy():
    """Verify fetch_oembed uses standard urlopen when no proxy is configured."""
    scraper = DirectInstagramScraper(proxy=None)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"title": "Direct", "author_name": "direct_user"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = scraper.fetch_oembed("https://www.instagram.com/reel/C123abc/")
        assert result is not None
        assert result["title"] == "Direct"
        mock_urlopen.assert_called_once()


def test_direct_youtube_scraper_proxy_initialization():
    """Verify DirectYouTubeScraper stores proxy attribute."""
    scraper = DirectYouTubeScraper(proxy="http://10.0.0.1:8080")
    assert scraper._proxy == "http://10.0.0.1:8080"


def test_direct_youtube_scraper_fetch_oembed_with_proxy():
    """Verify DirectYouTubeScraper builds ProxyHandler and opener."""
    scraper = DirectYouTubeScraper(proxy="10.0.0.1:8080")

    with patch("urllib.request.build_opener") as mock_build_opener, \
         patch("urllib.request.ProxyHandler") as mock_proxy_handler:

        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"title": "YT Video", "author_name": "yt_creator"}'
        mock_opener.open.return_value.__enter__.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        result = scraper.fetch_oembed("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result is not None
        assert result["author_name"] == "yt_creator"
        mock_proxy_handler.assert_called_once_with({
            "http": "http://10.0.0.1:8080",
            "https": "http://10.0.0.1:8080",
        })


def test_universal_direct_scraper_forwards_proxy():
    """Verify UniversalDirectScraper configures child scrapers with proxy and forwards calls."""
    universal = UniversalDirectScraper(proxy="127.0.0.1:9050")
    assert universal._proxy == "127.0.0.1:9050"
    assert universal._ig_scraper._proxy == "127.0.0.1:9050"
    assert universal._yt_scraper._proxy == "127.0.0.1:9050"

    with patch.object(universal._ig_scraper, "quick_preview") as mock_ig_preview:
        universal.quick_preview("https://www.instagram.com/reel/C123/")
        mock_ig_preview.assert_called_once_with(
            "https://www.instagram.com/reel/C123/",
            proxy="127.0.0.1:9050",
        )

    with patch.object(universal._yt_scraper, "quick_preview") as mock_yt_preview:
        universal.quick_preview("https://www.youtube.com/watch?v=abc123")
        mock_yt_preview.assert_called_once_with(
            "https://www.youtube.com/watch?v=abc123",
            proxy="127.0.0.1:9050",
        )


# ---------------------------------------------------------------------------
# 4. ThumbnailLoaderWorker Proxy Support Tests
# ---------------------------------------------------------------------------

def test_thumbnail_loader_worker_init_and_backward_compatibility():
    """Verify ThumbnailLoaderWorker proxy parameter and parent fallback parameter."""
    # Explicit proxy keyword argument
    w1 = ThumbnailLoaderWorker("https://example.com/thumb.jpg", proxy="127.0.0.1:8080")
    assert w1._proxy == "127.0.0.1:8080"

    # Positional string argument backward compatibility
    w2 = ThumbnailLoaderWorker("https://example.com/thumb.jpg", "127.0.0.1:8080")
    assert w2._proxy == "127.0.0.1:8080"


def test_thumbnail_loader_worker_run_with_proxy():
    """Verify ThumbnailLoaderWorker uses ProxyHandler when proxy is configured."""
    worker = ThumbnailLoaderWorker("https://example.com/thumb.jpg", proxy="127.0.0.1:8080")

    loaded_data = []
    worker.loaded.connect(lambda data: loaded_data.append(data))

    with patch("urllib.request.build_opener") as mock_build_opener, \
         patch("urllib.request.ProxyHandler") as mock_proxy_handler:

        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # JPEG header bytes
        mock_opener.open.return_value.__enter__.return_value = mock_resp
        mock_build_opener.return_value = mock_opener

        worker.run()

        mock_proxy_handler.assert_called_once_with({
            "http": "http://127.0.0.1:8080",
            "https": "http://127.0.0.1:8080",
        })
        assert len(loaded_data) == 1
        assert loaded_data[0].startswith(b"\xff\xd8\xff")


def test_thumbnail_loader_worker_run_without_proxy():
    """Verify ThumbnailLoaderWorker uses urlopen when proxy is None."""
    worker = ThumbnailLoaderWorker("https://example.com/thumb.jpg", proxy=None)

    loaded_data = []
    worker.loaded.connect(lambda data: loaded_data.append(data))

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"raw image bytes"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        worker.run()

        mock_urlopen.assert_called_once()
        assert loaded_data == [b"raw image bytes"]


def test_thumbnail_loader_worker_run_failure_emits_failed():
    """Verify ThumbnailLoaderWorker catches network errors and emits failed signal."""
    worker = ThumbnailLoaderWorker("https://example.com/broken.jpg", proxy="127.0.0.1:8080")

    failed_called = []
    worker.failed.connect(lambda: failed_called.append(True))

    with patch("urllib.request.build_opener", side_effect=Exception("Connection refused")):
        worker.run()
        assert failed_called == [True]
