"""Unit tests for domain models and serialization."""

from src.domain.models import (
    MediaItem,
    MediaType,
    DownloadProgress,
    AppSettings,
    QualityOption,
    DownloadHistoryItem,
    DownloadRequest,
    DownloadStatus,
    enum_value,
)


def test_media_item_formatting():
    item = MediaItem(
        url="https://www.instagram.com/reel/123/",
        shortcode="123",
        media_type=MediaType.REEL,
        title="Check out this incredible view of the sunset in the mountains!",
        author="nature_lover",
        duration_seconds=95,
    )
    assert item.formatted_duration == "1:35"
    assert "Check out this incredible view" in item.display_title


def test_media_item_default_title():
    item = MediaItem(
        url="https://www.instagram.com/reel/ABC123xyz/",
        shortcode="ABC123xyz",
        media_type=MediaType.REEL,
        title="",
    )
    assert item.display_title == "Instagram Reel (ABC123xyz)"
    assert item.formatted_duration == "Unknown"


def test_download_progress_formatting():
    progress = DownloadProgress(
        percent=45.5,
        downloaded_bytes=10 * 1024 * 1024,
        total_bytes=20 * 1024 * 1024,
        speed_str="2.5 MB/s",
        eta_str="00:04",
    )
    assert progress.formatted_size == "10.0 / 20.0 MB"
    assert progress.speed_str == "2.5 MB/s"


def test_app_settings_serialization():
    settings = AppSettings(
        download_dir="C:/Downloads/Instagram",
        concurrent_downloads=4,
        default_quality=QualityOption.Q_1080P,
        rate_limit_kb=500,
        dark_theme=True,
    )
    data = settings.to_dict()
    restored = AppSettings.from_dict(data)

    assert restored.download_dir == "C:/Downloads/Instagram"
    assert restored.concurrent_downloads == 4
    assert restored.default_quality == QualityOption.Q_1080P
    assert restored.rate_limit_kb == 500
    assert restored.dark_theme is True


def test_history_item_serialization():
    history = DownloadHistoryItem(
        id="test-1",
        url="https://www.instagram.com/p/123/",
        title="Test Post",
        author="photographer",
        file_path="C:/Downloads/photo.mp4",
        file_size_bytes=5242880,  # 5 MB
        quality="best",
        downloaded_at="2026-11-01T00:00:00",
    )
    assert history.formatted_size == "5.00 MB"
    d = history.to_dict()
    restored = DownloadHistoryItem.from_dict(d)
    assert restored.id == "test-1"
    assert restored.title == "Test Post"
    assert restored.file_size_bytes == 5242880


def test_enum_value_safe_extraction():
    assert enum_value(QualityOption.BEST) == "best"
    assert enum_value(QualityOption.AUDIO_MP3) == "mp3"
    assert enum_value(MediaType.REEL) == "reel"
    assert enum_value(DownloadStatus.QUEUED) == "queued"
    assert enum_value("already_a_string") == "already_a_string"
    assert enum_value(123) == "123"
    assert enum_value(None) == ""

    # Test that callable .value method (like on Qt widgets) is not converted to <bound method...>
    class MockWidgetWithMethod:
        def value(self):
            return 42

        def __str__(self):
            return "widget_str"

    assert enum_value(MockWidgetWithMethod()) == "widget_str"


def test_quality_option_from_value():
    # Direct Enum & values
    assert QualityOption.from_value(QualityOption.BEST) == QualityOption.BEST
    assert QualityOption.from_value("best") == QualityOption.BEST
    assert QualityOption.from_value("BEST") == QualityOption.BEST
    assert QualityOption.from_value("1080p") == QualityOption.Q_1080P
    assert QualityOption.from_value("q_1080p") == QualityOption.Q_1080P
    assert QualityOption.from_value("mp3") == QualityOption.AUDIO_MP3
    assert QualityOption.from_value("AUDIO_MP3") == QualityOption.AUDIO_MP3

    # All UI Display Names
    assert QualityOption.from_value("Best Available Quality (MP4)") == QualityOption.BEST
    assert QualityOption.from_value("Full HD 1080p (MP4)") == QualityOption.Q_1080P
    assert QualityOption.from_value("HD 720p (MP4)") == QualityOption.Q_720P
    assert QualityOption.from_value("SD 480p (MP4)") == QualityOption.Q_480P
    assert QualityOption.from_value("Audio Only (MP3 320k)") == QualityOption.AUDIO_MP3
    assert QualityOption.from_value("Audio Only (M4A/AAC)") == QualityOption.AUDIO_M4A

    # Common shorthand numbers and aliases
    assert QualityOption.from_value("1080") == QualityOption.Q_1080P
    assert QualityOption.from_value(1080) == QualityOption.Q_1080P
    assert QualityOption.from_value("720") == QualityOption.Q_720P
    assert QualityOption.from_value(720) == QualityOption.Q_720P
    assert QualityOption.from_value("480") == QualityOption.Q_480P
    assert QualityOption.from_value(480) == QualityOption.Q_480P
    assert QualityOption.from_value("aac") == QualityOption.AUDIO_M4A
    assert QualityOption.from_value("audio") == QualityOption.AUDIO_MP3

    # Invalid defaults safely to BEST
    assert QualityOption.from_value("nonexistent_quality") == QualityOption.BEST
    assert QualityOption.from_value(None) == QualityOption.BEST


def test_quality_option_get_display_name():
    assert QualityOption.get_display_name(QualityOption.BEST) == "Best Available Quality (MP4)"
    assert QualityOption.get_display_name("best") == "Best Available Quality (MP4)"
    assert QualityOption.get_display_name("1080p") == "Full HD 1080p (MP4)"
    assert QualityOption.get_display_name("Full HD 1080p (MP4)") == "Full HD 1080p (MP4)"
    assert QualityOption.get_display_name("mp3") == "Audio Only (MP3 320k)"
    assert QualityOption.get_display_name("m4a") == "Audio Only (M4A/AAC)"


def test_media_type_from_value():
    assert MediaType.from_value(MediaType.REEL) == MediaType.REEL
    assert MediaType.from_value("reel") == MediaType.REEL
    assert MediaType.from_value("REEL") == MediaType.REEL
    assert MediaType.from_value("post") == MediaType.POST
    assert MediaType.from_value("story") == MediaType.STORY
    assert MediaType.from_value("carousel") == MediaType.CAROUSEL
    assert MediaType.from_value("tv") == MediaType.TV

    # Plural forms & aliases
    assert MediaType.from_value("reels") == MediaType.REEL
    assert MediaType.from_value("posts") == MediaType.POST
    assert MediaType.from_value("stories") == MediaType.STORY
    assert MediaType.from_value("highlights") == MediaType.STORY
    assert MediaType.from_value("igtv") == MediaType.TV
    assert MediaType.from_value("clip") == MediaType.REEL

    assert MediaType.from_value("unknown_type") == MediaType.UNKNOWN
    assert MediaType.from_value(None) == MediaType.UNKNOWN


def test_download_status_from_value():
    assert DownloadStatus.from_value(DownloadStatus.COMPLETED) == DownloadStatus.COMPLETED
    assert DownloadStatus.from_value("completed") == DownloadStatus.COMPLETED
    assert DownloadStatus.from_value("COMPLETED") == DownloadStatus.COMPLETED
    assert DownloadStatus.from_value("fetching_info") == DownloadStatus.FETCHING_INFO
    assert DownloadStatus.from_value("fetching info") == DownloadStatus.FETCHING_INFO
    assert DownloadStatus.from_value("fetching") == DownloadStatus.FETCHING_INFO
    assert DownloadStatus.from_value("done") == DownloadStatus.COMPLETED
    assert DownloadStatus.from_value("finished") == DownloadStatus.COMPLETED
    assert DownloadStatus.from_value("complete") == DownloadStatus.COMPLETED
    assert DownloadStatus.from_value("error") == DownloadStatus.FAILED
    assert DownloadStatus.from_value("failed") == DownloadStatus.FAILED
    assert DownloadStatus.from_value("canceled") == DownloadStatus.CANCELLED
    assert DownloadStatus.from_value("cancelled") == DownloadStatus.CANCELLED
    assert DownloadStatus.from_value("unknown_status") == DownloadStatus.QUEUED
    assert DownloadStatus.from_value(None) == DownloadStatus.QUEUED


def test_download_history_item_quality_coercion():
    item = DownloadHistoryItem(
        id="h_test",
        url="https://www.instagram.com/reel/123/",
        title="Title",
        author="user",
        file_path="/file.mp4",
        file_size_bytes=1000,
        quality=QualityOption.BEST,
        downloaded_at="2026-11-01",
    )
    assert isinstance(item.quality, str)
    assert item.quality == "best"


def test_download_request_string_coercion():
    req = DownloadRequest(
        url="https://www.instagram.com/reel/123/",
        quality="best",
        status="completed",
    )
    assert isinstance(req.quality, QualityOption)
    assert req.quality == QualityOption.BEST
    assert req.quality.value == "best"
    assert isinstance(req.status, DownloadStatus)
    assert req.status == DownloadStatus.COMPLETED
    assert req.status.value == "completed"

    # Coercion with UI display name
    req_display = DownloadRequest(
        url="https://www.instagram.com/reel/123/",
        quality="Full HD 1080p (MP4)",
        status="finished",
    )
    assert req_display.quality == QualityOption.Q_1080P
    assert req_display.status == DownloadStatus.COMPLETED


def test_media_item_string_media_type_coercion():
    item = MediaItem(
        url="https://www.instagram.com/reel/123/",
        shortcode="123",
        media_type="reels",  # plural alias
    )
    assert isinstance(item.media_type, MediaType)
    assert item.media_type == MediaType.REEL
    assert item.media_type.value == "reel"
    assert item.display_title == "Instagram Reel (123)"


def test_app_settings_string_quality_coercion():
    settings = AppSettings(default_quality="mp3")
    assert isinstance(settings.default_quality, QualityOption)
    assert settings.default_quality == QualityOption.AUDIO_MP3
    assert settings.default_quality.value == "mp3"
    d = settings.to_dict()
    assert d["default_quality"] == "mp3"

    # With display name
    settings_disp = AppSettings(default_quality="Audio Only (M4A/AAC)")
    assert settings_disp.default_quality == QualityOption.AUDIO_M4A
