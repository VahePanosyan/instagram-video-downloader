"""Tests for subtitles, time range trimming, and metadata embedding."""

from unittest.mock import MagicMock, patch
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.adapters.ffmpeg_adapter import FFmpegAdapter
from src.domain.models import DownloadRequest, AppSettings, QualityOption, SubtitleMode


def test_subtitles_options_embed():
    adapter = YtDlpAdapter()
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        subtitles_mode=SubtitleMode.EMBED,
        subtitles_languages="en,es",
    )
    settings = AppSettings()

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ"}
        mock_ydl.prepare_filename.return_value = "video.mp4"

        try:
            adapter.download(req, settings)
        except Exception:
            pass

        call_args = mock_ydl_cls.call_args[0][0]
        assert call_args.get("writesubtitles") is True
        assert call_args.get("subtitleslangs") == ["en", "es"]
        pps = [p.get("key") for p in call_args.get("postprocessors", [])]
        assert "FFmpegEmbedSubtitle" in pps


def test_subtitles_options_srt():
    adapter = YtDlpAdapter()
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        subtitles_mode=SubtitleMode.EXTERNAL_SRT,
        subtitles_languages="en",
    )
    settings = AppSettings()

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ"}
        mock_ydl.prepare_filename.return_value = "video.mp4"

        try:
            adapter.download(req, settings)
        except Exception:
            pass

        call_args = mock_ydl_cls.call_args[0][0]
        assert call_args.get("writesubtitles") is True
        pps = [p.get("key") for p in call_args.get("postprocessors", [])]
        assert "FFmpegSubtitlesConvertor" in pps


def test_time_range_clipping_options():
    adapter = YtDlpAdapter()
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        time_range_start="00:01:30",
        time_range_end="00:02:45",
    )
    settings = AppSettings()

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ"}
        mock_ydl.prepare_filename.return_value = "video.mp4"

        try:
            adapter.download(req, settings)
        except Exception:
            pass

        call_args = mock_ydl_cls.call_args[0][0]
        assert "download_ranges" in call_args
        assert call_args.get("force_keyframes_at_cuts") is True


def test_metadata_and_thumbnail_embedding():
    adapter = YtDlpAdapter()
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        quality=QualityOption.AUDIO_MP3,
    )
    settings = AppSettings(embed_thumbnail=True, embed_metadata=True)

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ"}
        mock_ydl.prepare_filename.return_value = "audio.mp3"

        try:
            adapter.download(req, settings)
        except Exception:
            pass

        call_args = mock_ydl_cls.call_args[0][0]
        pps = [p.get("key") for p in call_args.get("postprocessors", [])]
        assert "FFmpegMetadata" in pps
        assert "FFmpegThumbnailsConvertor" in pps
        assert "EmbedThumbnail" in pps


def test_ffmpeg_slice_media():
    adapter = FFmpegAdapter(ffmpeg_path="ffmpeg")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = adapter.slice_media("in.mp4", "out.mp4", "00:01:00", "00:02:00")
        assert res == "out.mp4"
        cmd = mock_run.call_args[0][0]
        assert "-ss" in cmd
        assert "00:01:00" in cmd
        assert "-to" in cmd
        assert "00:02:00" in cmd
