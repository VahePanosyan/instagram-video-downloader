"""Tests for error handling, exception mapping, network resilience, and invalid input stability."""

import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from yt_dlp.utils import DownloadError

from src.adapters.direct_scraper import (
    DirectInstagramScraper,
    DirectYouTubeScraper,
    UniversalDirectScraper,
)
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.domain.exceptions import (
    AuthenticationRequiredException,
    DownloaderException,
    DownloadException,
    ExtractionException,
    InvalidUrlException,
    NetworkException,
    PostProcessingException,
)
from src.domain.models import AppSettings, DownloadRequest, MediaItem, Platform, QualityOption
from src.domain.url_parser import InstagramUrlParser, MediaUrlParser, YouTubeUrlParser


# ---------------------------------------------------------------------------
# 1. Domain Exception Hierarchy and Formatting Tests
# ---------------------------------------------------------------------------

def test_downloader_exception_hierarchy():
    """Verify all domain exceptions properly subclass DownloaderException."""
    assert issubclass(InvalidUrlException, DownloaderException)
    assert issubclass(ExtractionException, DownloaderException)
    assert issubclass(AuthenticationRequiredException, ExtractionException)
    assert issubclass(AuthenticationRequiredException, DownloaderException)
    assert issubclass(DownloadException, DownloaderException)
    assert issubclass(NetworkException, DownloaderException)
    assert issubclass(PostProcessingException, DownloaderException)


def test_downloader_exception_string_formatting():
    """Verify exception __str__ displays message and optional details."""
    exc_without_details = DownloaderException("Failed operation")
    assert str(exc_without_details) == "Failed operation"

    exc_with_details = DownloaderException("Connection error", details="Host unreachable")
    assert str(exc_with_details) == "Connection error: Host unreachable"
    assert exc_with_details.details == "Host unreachable"


# ---------------------------------------------------------------------------
# 2. Invalid URL Exception Mapping Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "invalid_url",
    [
        "",
        "   ",
        "not_a_url",
        "ftp://instagram.com/reel/123",
        "https://google.com/search?q=video",
        "https://vimeo.com/12345678",
        "https://tiktok.com/@user/video/123456789",
        "https://facebook.com/watch/?v=123",
    ],
)
def test_media_url_parser_invalid_urls_raise_invalid_url_exception(invalid_url):
    """Verify MediaUrlParser.parse raises InvalidUrlException for empty, unsupported, or malformed URLs."""
    with pytest.raises(InvalidUrlException):
        MediaUrlParser.parse(invalid_url)


def test_instagram_url_parser_invalid_paths_raise_invalid_url_exception():
    """Verify InstagramUrlParser raises InvalidUrlException for non-media Instagram paths."""
    with pytest.raises(InvalidUrlException):
        InstagramUrlParser.parse("https://www.instagram.com/accounts/login/")

    with pytest.raises(InvalidUrlException):
        InstagramUrlParser.parse("https://www.instagram.com/explore/tags/sunset/")

    with pytest.raises(InvalidUrlException):
        InstagramUrlParser.parse("")


def test_youtube_url_parser_invalid_paths_raise_invalid_url_exception():
    """Verify YouTubeUrlParser raises InvalidUrlException for non-video YouTube pages."""
    with pytest.raises(InvalidUrlException):
        YouTubeUrlParser.parse("https://www.youtube.com/about")

    with pytest.raises(InvalidUrlException):
        YouTubeUrlParser.parse("https://www.youtube.com/t/terms")

    with pytest.raises(InvalidUrlException):
        YouTubeUrlParser.parse("")


def test_ytdlp_adapter_extract_info_invalid_url_raises_invalid_url_exception():
    """Verify YtDlpAdapter.extract_info raises InvalidUrlException before invoking yt-dlp."""
    adapter = YtDlpAdapter()
    with pytest.raises(InvalidUrlException):
        adapter.extract_info("https://soundcloud.com/artist/track")


# ---------------------------------------------------------------------------
# 3. YtDlpAdapter Network and Timeout Exception Mapping Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error_message",
    [
        "ERROR: Unable to connect to proxy 127.0.0.1:8080: Connection refused",
        "ProxyError: Failed to connect to proxy tunnel",
        "The read operation timed out",
        "Connection reset by peer",
        "Failed to establish a new connection: [Errno 11001] getaddrinfo failed",
    ],
)
def test_ytdlp_extract_info_network_errors_map_to_network_exception(error_message):
    """Verify network timeouts, proxy failures, and connection drops map to NetworkException."""
    adapter = YtDlpAdapter()
    url = "https://www.instagram.com/reel/C_network_test/"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError(error_message)
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(NetworkException) as exc_info:
            adapter.extract_info(url)

        assert error_message in exc_info.value.details or error_message in str(exc_info.value)


@pytest.mark.parametrize(
    "error_message",
    [
        "ERROR: Unable to connect to proxy socks5://127.0.0.1:1080",
        "HTTPConnectionPool: Read timed out after 25 seconds",
        "Remote end closed connection without response",
    ],
)
def test_ytdlp_download_network_errors_map_to_network_exception(tmp_path, error_message):
    """Verify network and proxy failures during download() map to NetworkException."""
    adapter = YtDlpAdapter()
    settings = AppSettings(download_dir=str(tmp_path))
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=network_err_vid",
        output_dir=str(tmp_path),
        media_item=MediaItem(
            url="https://www.youtube.com/watch?v=network_err_vid",
            shortcode="network_err_vid",
            platform=Platform.YOUTUBE,
        ),
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError(error_message)
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(NetworkException) as exc_info:
            adapter.download(req, settings)

        assert error_message in exc_info.value.details or error_message in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. YtDlpAdapter Authentication, Private, and Cookie Exception Mapping Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error_message",
    [
        "Could not find cookies in chrome database: database is locked",
        "Cookie file is corrupted or contains invalid Netscape headers",
        "This account is private. Log in to see photos and videos from this account.",
        "Sign in to confirm you’re not a bot",
        "Sign in to confirm your age. This video may be inappropriate for some users.",
        "Join this channel to get access to members-only content",
        "members-only content requires active channel subscription",
    ],
)
def test_ytdlp_extract_info_auth_errors_map_to_authentication_required_exception(error_message):
    """Verify private media, bot verification, age restriction, and cookie locks map to AuthenticationRequiredException."""
    adapter = YtDlpAdapter()
    url = "https://www.instagram.com/p/C_private_test/"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError(error_message)
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(AuthenticationRequiredException) as exc_info:
            adapter.extract_info(url)

        assert exc_info.value.details == error_message


@pytest.mark.parametrize(
    "error_message",
    [
        "Sign in to view this private reel",
        "Cookies file rejected by instagram: Session expired",
        "Age-restricted content: Please log in to confirm age",
    ],
)
def test_ytdlp_download_auth_errors_map_to_authentication_required_exception(tmp_path, error_message):
    """Verify private/cookie/age errors during download() map to AuthenticationRequiredException."""
    adapter = YtDlpAdapter()
    settings = AppSettings(download_dir=str(tmp_path))
    req = DownloadRequest(
        url="https://www.instagram.com/reel/C_auth_test/",
        output_dir=str(tmp_path),
        media_item=MediaItem(
            url="https://www.instagram.com/reel/C_auth_test/",
            shortcode="C_auth_test",
            platform=Platform.INSTAGRAM,
        ),
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError(error_message)
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(AuthenticationRequiredException) as exc_info:
            adapter.download(req, settings)

        assert exc_info.value.details == error_message


# ---------------------------------------------------------------------------
# 5. Extraction & Download General Failures
# ---------------------------------------------------------------------------

def test_ytdlp_extract_info_none_result_raises_extraction_exception():
    """Verify ExtractionException is raised when yt-dlp returns None for metadata."""
    adapter = YtDlpAdapter()
    url = "https://www.instagram.com/reel/C_empty_meta/"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.return_value = None
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(ExtractionException, match="No metadata found"):
            adapter.extract_info(url)


def test_ytdlp_extract_info_generic_download_error_raises_extraction_exception():
    """Verify non-network, non-auth DownloadErrors map to ExtractionException."""
    adapter = YtDlpAdapter()
    url = "https://www.youtube.com/watch?v=deleted_video_123"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError("Video has been removed by the uploader")
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(ExtractionException, match="Failed to extract YouTube media information"):
            adapter.extract_info(url)


def test_ytdlp_download_missing_file_raises_download_exception(tmp_path):
    """Verify DownloadException is raised when download process finishes but target file is missing."""
    adapter = YtDlpAdapter()
    settings = AppSettings(download_dir=str(tmp_path))
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=missing_on_disk",
        output_dir=str(tmp_path),
        media_item=MediaItem(
            url="https://www.youtube.com/watch?v=missing_on_disk",
            shortcode="missing_on_disk",
            platform=Platform.YOUTUBE,
            author="channel",
            title="title",
        ),
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.return_value = {"id": "missing_on_disk", "title": "title"}
        mock_inst.prepare_filename.return_value = str(tmp_path / "nonexistent.mp4")
        mock_ydl_cls.return_value = mock_inst

        # No file created on disk
        with pytest.raises(DownloadException, match="target file was not found on disk"):
            adapter.download(req, settings)


# ---------------------------------------------------------------------------
# 6. Direct Scrapers Resilience Under Error Conditions
# ---------------------------------------------------------------------------

def test_direct_instagram_scraper_graceful_http_error():
    """Verify DirectInstagramScraper returns None rather than raising on HTTP 404/403."""
    scraper = DirectInstagramScraper()

    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None)):
        result = scraper.fetch_oembed("https://www.instagram.com/reel/C_missing/")
        assert result is None


def test_direct_instagram_scraper_graceful_timeout_error():
    """Verify DirectInstagramScraper returns None on socket/URLError timeout."""
    scraper = DirectInstagramScraper()

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
        result = scraper.fetch_oembed("https://www.instagram.com/reel/C_timeout/")
        assert result is None


def test_direct_youtube_scraper_graceful_http_error():
    """Verify DirectYouTubeScraper returns None rather than raising on HTTP errors."""
    scraper = DirectYouTubeScraper()

    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 500, "Server Error", {}, None)):
        result = scraper.fetch_oembed("https://www.youtube.com/watch?v=err_video")
        assert result is None


def test_universal_direct_scraper_quick_preview_fallback_on_oembed_failure():
    """Verify UniversalDirectScraper.quick_preview returns valid fallback MediaItem even when oEmbed fails."""
    scraper = UniversalDirectScraper()

    # Instagram fallback
    with patch.object(scraper._ig_scraper, "fetch_oembed", return_value=None):
        item_ig = scraper.quick_preview("https://www.instagram.com/reel/C123abc/")
        assert item_ig.shortcode == "C123abc"
        assert item_ig.url == "https://www.instagram.com/reel/C123abc/"
        assert item_ig.title == ""
        assert item_ig.thumbnail_url is None

    # YouTube fallback
    with patch.object(scraper._yt_scraper, "fetch_oembed", return_value=None):
        item_yt = scraper.quick_preview("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert item_yt.shortcode == "dQw4w9WgXcQ"
        assert item_yt.platform == Platform.YOUTUBE
        # YouTube fallback provides standard hqdefault thumbnail
        assert "hqdefault.jpg" in (item_yt.thumbnail_url or "")
