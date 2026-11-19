"""Unit tests for YouTube adapters and scrapers."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from yt_dlp.utils import DownloadError
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.adapters.direct_scraper import DirectYouTubeScraper, UniversalDirectScraper
from src.domain.models import (
    QualityOption,
    MediaType,
    Platform,
    DownloadRequest,
    MediaItem,
    AppSettings,
)
from src.domain.exceptions import AuthenticationRequiredException


def test_youtube_format_selectors():
    adapter = YtDlpAdapter()

    # 4K
    fmt_4k, pp_4k = adapter._determine_format(QualityOption.Q_2160P)
    assert "2160" in fmt_4k
    assert len(pp_4k) == 0

    # 2K
    fmt_2k, pp_2k = adapter._determine_format(QualityOption.Q_1440P)
    assert "1440" in fmt_2k
    assert len(pp_2k) == 0

    # 1080p
    fmt_1080, pp_1080 = adapter._determine_format(QualityOption.Q_1080P)
    assert "1080" in fmt_1080
    assert len(pp_1080) == 0

    # 360p
    fmt_360, pp_360 = adapter._determine_format(QualityOption.Q_360P)
    assert "360" in fmt_360
    assert len(pp_360) == 0

    # MP3
    fmt_mp3, pp_mp3 = adapter._determine_format(QualityOption.AUDIO_MP3)
    assert "bestaudio" in fmt_mp3
    assert len(pp_mp3) == 1
    assert pp_mp3[0]["preferredcodec"] == "mp3"
    assert pp_mp3[0]["preferredquality"] == "320"

    # M4A
    fmt_m4a, pp_m4a = adapter._determine_format(QualityOption.AUDIO_M4A)
    assert "bestaudio" in fmt_m4a
    assert len(pp_m4a) == 1
    assert pp_m4a[0]["preferredcodec"] == "m4a"


def test_youtube_filename_template_resolution():
    adapter = YtDlpAdapter()
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        media_item=MediaItem(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            shortcode="dQw4w9WgXcQ",
            platform=Platform.YOUTUBE,
            author="RickAstleyVEVO",
            title="Never Gonna Give You Up (Official Music Video)",
            upload_date="20091025",
        ),
        filename_template="{author}_{title}",
    )

    platform = req.media_item.platform
    default_author = "youtube" if platform == Platform.YOUTUBE else "instagram"
    author = adapter._sanitize_filename_component(req.media_item.author or default_author)
    shortcode = adapter._sanitize_filename_component(req.media_item.shortcode)
    title = adapter._sanitize_filename_component(req.media_item.title)
    upload_date = adapter._sanitize_filename_component(req.media_item.upload_date or "")

    template = req.filename_template
    prefix = (
        template.replace("{author}", author)
        .replace("{shortcode}", shortcode)
        .replace("{title}", title)
        .replace("{id}", shortcode)
        .replace("{date}", upload_date)
    )
    prefix = adapter._sanitize_filename_component(prefix)

    assert "RickAstleyVEVO" in prefix
    assert "Never_Gonna_Give_You_Up" in prefix
    assert ":" not in prefix
    assert "?" not in prefix


def test_youtube_video_metadata_extraction_mocked():
    adapter = YtDlpAdapter()
    fake_info = {
        "id": "dQw4w9WgXcQ",
        "title": "Never Gonna Give You Up",
        "uploader": "Rick Astley",
        "duration": 212,
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        "view_count": 1500000000,
        "like_count": 16000000,
        "upload_date": "20091025",
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = fake_info
        mock_ydl_cls.return_value = mock_instance

        item = adapter.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert item.shortcode == "dQw4w9WgXcQ"
        assert item.platform == Platform.YOUTUBE
        assert item.media_type == MediaType.VIDEO
        assert item.title == "Never Gonna Give You Up"
        assert item.author == "Rick Astley"
        assert item.duration_seconds == 212
        assert item.formatted_duration == "3:32"
        assert item.view_count == 1500000000


def test_youtube_shorts_metadata_extraction_mocked():
    adapter = YtDlpAdapter()
    fake_info = {
        "id": "3fDkJ2hZ91A",
        "title": "Amazing YouTube Short",
        "uploader": "ShortsCreator",
        "duration": 45,
        "thumbnail": "https://i.ytimg.com/vi/3fDkJ2hZ91A/hqdefault.jpg",
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = fake_info
        mock_ydl_cls.return_value = mock_instance

        item = adapter.extract_info("https://www.youtube.com/shorts/3fDkJ2hZ91A")

        assert item.shortcode == "3fDkJ2hZ91A"
        assert item.platform == Platform.YOUTUBE
        assert item.media_type == MediaType.SHORT
        assert item.title == "Amazing YouTube Short"
        assert item.author == "ShortsCreator"
        assert item.duration_seconds == 45


def test_youtube_playlist_metadata_extraction_mocked():
    adapter = YtDlpAdapter()
    fake_playlist = {
        "_type": "playlist",
        "id": "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
        "title": "Select Lectures Playlist",
        "uploader": "Lex Fridman",
        "entries": [
            {"id": "vid_1", "webpage_url": "https://www.youtube.com/watch?v=vid_1", "title": "Lecture 1"},
            {"id": "vid_2", "webpage_url": "https://www.youtube.com/watch?v=vid_2", "title": "Lecture 2"},
            {"id": "vid_3", "url": "https://www.youtube.com/watch?v=vid_3", "title": "Lecture 3"},
        ],
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = fake_playlist
        mock_ydl_cls.return_value = mock_instance

        item = adapter.extract_info("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")

        assert item.is_playlist is True
        assert item.media_type == MediaType.PLAYLIST
        assert item.platform == Platform.YOUTUBE
        assert len(item.playlist_urls) == 3
        assert item.playlist_urls[0] == "https://www.youtube.com/watch?v=vid_1"
        assert item.playlist_urls[1] == "https://www.youtube.com/watch?v=vid_2"
        assert item.playlist_urls[2] == "https://www.youtube.com/watch?v=vid_3"


def test_youtube_error_translations():
    adapter = YtDlpAdapter()

    # 1. Bot check / sign in
    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError("Sign in to confirm you're not a bot")
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(AuthenticationRequiredException) as excinfo:
            adapter.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "YouTube authentication required" in str(excinfo.value)

    # 2. Age-restricted
    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.side_effect = DownloadError("Sign in to confirm your age. This video may be inappropriate")
        mock_ydl_cls.return_value = mock_inst

        with pytest.raises(AuthenticationRequiredException) as excinfo:
            adapter.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "age-restricted" in str(excinfo.value)


def test_direct_youtube_scraper():
    scraper = DirectYouTubeScraper()
    fake_json = {
        "title": "Astley Hit Remastered",
        "author_name": "Rick Astley",
        "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    }

    with patch.object(scraper, "fetch_oembed", return_value=fake_json):
        item = scraper.quick_preview("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert item.platform == Platform.YOUTUBE
        assert item.title == "Astley Hit Remastered"
        assert item.author == "Rick Astley"
        assert item.thumbnail_url == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"


def test_universal_direct_scraper_routing():
    universal = UniversalDirectScraper()

    with patch.object(universal._yt_scraper, "quick_preview") as mock_yt:
        mock_yt.return_value = MediaItem(url="u", shortcode="yt1", platform=Platform.YOUTUBE)
        res = universal.quick_preview("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert res.platform == Platform.YOUTUBE
        mock_yt.assert_called_once()

    with patch.object(universal._ig_scraper, "quick_preview") as mock_ig:
        mock_ig.return_value = MediaItem(url="u", shortcode="ig1", platform=Platform.INSTAGRAM)
        res = universal.quick_preview("https://www.instagram.com/reel/C2-7XYZ1234/")
        assert res.platform == Platform.INSTAGRAM
        mock_ig.assert_called_once()


def test_direct_youtube_scraper_oembed_none_fallback_no_nameerror():
    scraper = DirectYouTubeScraper()
    with patch.object(scraper, "fetch_oembed", return_value=None):
        item = scraper.quick_preview("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert item.platform == Platform.YOUTUBE
        assert item.shortcode == "dQw4w9WgXcQ"
        assert item.media_type == MediaType.VIDEO
        assert item.thumbnail_url == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"


def test_direct_youtube_scraper_playlist_detection():
    scraper = DirectYouTubeScraper()
    with patch.object(scraper, "fetch_oembed", return_value=None):
        item = scraper.quick_preview("https://www.youtube.com/playlist?list=PL123")
        assert item.platform == Platform.YOUTUBE
        assert item.media_type == MediaType.PLAYLIST
        assert item.is_playlist is True


def test_youtube_flat_playlist_raw_video_ids():
    adapter = YtDlpAdapter()
    fake_playlist = {
        "_type": "playlist",
        "id": "PL_TEST_FLAT",
        "title": "Flat Playlist",
        "uploader": "Test Channel",
        "entries": [
            {"id": "raw_id_1", "url": "raw_id_1", "title": "Track 1"},
            {"id": "raw_id_2", "url": "https://www.youtube.com/watch?v=raw_id_2", "title": "Track 2"},
            {"id": "raw_id_3", "webpage_url": None, "url": None, "title": "Track 3"},
        ],
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst
        mock_inst.extract_info.return_value = fake_playlist
        mock_ydl_cls.return_value = mock_inst

        item = adapter.extract_info("https://www.youtube.com/playlist?list=PL_TEST_FLAT")
        assert len(item.playlist_urls) == 3
        assert item.playlist_urls[0] == "https://www.youtube.com/watch?v=raw_id_1"
        assert item.playlist_urls[1] == "https://www.youtube.com/watch?v=raw_id_2"
        assert item.playlist_urls[2] == "https://www.youtube.com/watch?v=raw_id_3"


def test_youtube_playlist_download_folder_separation(tmp_path):
    adapter = YtDlpAdapter()
    settings = AppSettings(download_dir=str(tmp_path))

    req = DownloadRequest(
        url="https://www.youtube.com/playlist?list=PL_DISCO",
        media_item=MediaItem(
            url="https://www.youtube.com/playlist?list=PL_DISCO",
            shortcode="PL_DISCO",
            platform=Platform.YOUTUBE,
            media_type=MediaType.PLAYLIST,
            is_playlist=True,
            title="Disco Hits",
            author="DiscoMaster",
        ),
        output_dir=str(tmp_path),
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst

        def fake_extract(url, download=True):
            # Simulate yt-dlp downloading files into the configured playlist directory
            call_opts = mock_ydl_cls.call_args[0][0]
            folder = Path(call_opts["outtmpl"]).parent
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "01 - Song 1.mp4").write_text("audio data 1")
            (folder / "02 - Song 2.mp4").write_text("audio data 2")
            return {"id": "PL_DISCO", "title": "Disco Hits"}

        mock_inst.extract_info.side_effect = fake_extract
        mock_ydl_cls.return_value = mock_inst

        saved_path = adapter.download(req, settings)
        assert Path(saved_path).is_dir()
        assert len(list(Path(saved_path).iterdir())) == 2
