"""Tests for new audio and video formats: WAV, FLAC, 4K (2160p), and FFmpeg codecs."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.adapters.ffmpeg_adapter import FFmpegAdapter
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.domain.exceptions import PostProcessingException, DownloadException
from src.domain.models import (
    AppSettings,
    DownloadRequest,
    MediaItem,
    Platform,
    QualityOption,
)


# ---------------------------------------------------------------------------
# 1. QualityOption Enum, Display Names & from_value Parsing Tests
# ---------------------------------------------------------------------------

def test_quality_option_wav_and_flac_enum_values():
    """Verify enum values and backward compatible indexing for AUDIO_WAV and AUDIO_FLAC."""
    assert QualityOption.AUDIO_WAV.value == "wav"
    assert QualityOption.AUDIO_FLAC.value == "flac"
    assert QualityOption.Q_2160P.value == "2160p"

    # Strict check: indices 0..5 must remain unchanged for existing UI selectors
    members = list(QualityOption)
    assert members[0] == QualityOption.BEST
    assert members[1] == QualityOption.Q_1080P
    assert members[2] == QualityOption.Q_720P
    assert members[3] == QualityOption.Q_480P
    assert members[4] == QualityOption.AUDIO_MP3
    assert members[5] == QualityOption.AUDIO_M4A


def test_quality_option_display_names():
    """Verify display names dictionary and get_display_name helper."""
    display_map = QualityOption.display_names()
    assert display_map[QualityOption.AUDIO_WAV] == "Audio Only (WAV Lossless)"
    assert display_map[QualityOption.AUDIO_FLAC] == "Audio Only (FLAC Lossless)"
    assert display_map[QualityOption.Q_2160P] == "4K Ultra HD 2160p (MP4)"

    assert QualityOption.get_display_name(QualityOption.AUDIO_WAV) == "Audio Only (WAV Lossless)"
    assert QualityOption.get_display_name(QualityOption.AUDIO_FLAC) == "Audio Only (FLAC Lossless)"
    assert QualityOption.get_display_name("wav") == "Audio Only (WAV Lossless)"
    assert QualityOption.get_display_name("flac") == "Audio Only (FLAC Lossless)"
    assert QualityOption.get_display_name("2160p") == "4K Ultra HD 2160p (MP4)"


@pytest.mark.parametrize(
    "input_val,expected",
    [
        ("wav", QualityOption.AUDIO_WAV),
        ("WAV", QualityOption.AUDIO_WAV),
        ("wave", QualityOption.AUDIO_WAV),
        ("WAVE", QualityOption.AUDIO_WAV),
        ("Audio Only (WAV Lossless)", QualityOption.AUDIO_WAV),
        ("audio only (wav lossless)", QualityOption.AUDIO_WAV),
        ("flac", QualityOption.AUDIO_FLAC),
        ("FLAC", QualityOption.AUDIO_FLAC),
        ("lossless", QualityOption.AUDIO_FLAC),
        ("LOSSLESS", QualityOption.AUDIO_FLAC),
        ("Audio Only (FLAC Lossless)", QualityOption.AUDIO_FLAC),
        ("audio only (flac lossless)", QualityOption.AUDIO_FLAC),
        ("2160p", QualityOption.Q_2160P),
        ("2160", QualityOption.Q_2160P),
        (2160, QualityOption.Q_2160P),
        ("4k", QualityOption.Q_2160P),
        ("4K", QualityOption.Q_2160P),
        ("4K Ultra HD 2160p (MP4)", QualityOption.Q_2160P),
    ],
)
def test_quality_option_from_value_parsing(input_val, expected):
    """Test from_value parsing of new formats, shorthand aliases, case insensitivity, and types."""
    assert QualityOption.from_value(input_val) == expected


# ---------------------------------------------------------------------------
# 2. YtDlpAdapter Format Selector Tests
# ---------------------------------------------------------------------------

def test_ytdlp_adapter_determine_format_wav():
    """Verify YtDlpAdapter format string and FFmpegExtractAudio postprocessor for WAV."""
    adapter = YtDlpAdapter()
    fmt_str, postprocessors = adapter._determine_format(QualityOption.AUDIO_WAV)

    assert fmt_str == "bestaudio/best"
    assert len(postprocessors) == 1
    pp = postprocessors[0]
    assert pp["key"] == "FFmpegExtractAudio"
    assert pp["preferredcodec"] == "wav"


def test_ytdlp_adapter_determine_format_flac():
    """Verify YtDlpAdapter format string and FFmpegExtractAudio postprocessor for FLAC."""
    adapter = YtDlpAdapter()
    fmt_str, postprocessors = adapter._determine_format(QualityOption.AUDIO_FLAC)

    assert fmt_str == "bestaudio/best"
    assert len(postprocessors) == 1
    pp = postprocessors[0]
    assert pp["key"] == "FFmpegExtractAudio"
    assert pp["preferredcodec"] == "flac"


def test_ytdlp_adapter_determine_format_4k_2160p():
    """Verify YtDlpAdapter format selector for 4K video, audio merge, and vertical video support."""
    adapter = YtDlpAdapter()
    fmt_str, postprocessors = adapter._determine_format(QualityOption.Q_2160P)

    assert len(postprocessors) == 0
    assert "2160" in fmt_str
    # Must support height<=2160 and vertical video width<=2160
    assert "height<=2160" in fmt_str
    assert "width<=2160" in fmt_str
    # Must specify audio merging
    assert "+bestaudio" in fmt_str


def test_ytdlp_adapter_determine_format_accepts_strings():
    """Verify _determine_format accepts raw strings or enum objects transparently."""
    adapter = YtDlpAdapter()
    _, pp_wav = adapter._determine_format("wav")
    assert pp_wav[0]["preferredcodec"] == "wav"

    _, pp_flac = adapter._determine_format("lossless")
    assert pp_flac[0]["preferredcodec"] == "flac"

    fmt_4k, _ = adapter._determine_format("4k")
    assert "2160" in fmt_4k


# ---------------------------------------------------------------------------
# 3. FFmpegAdapter Audio Extraction Tests
# ---------------------------------------------------------------------------

def test_ffmpeg_extract_audio_wav_command(tmp_path):
    """Verify FFmpeg command arguments for uncompressed PCM WAV extraction."""
    dummy_input = tmp_path / "sample.mp4"
    dummy_input.write_bytes(b"dummy video data")
    target_output = tmp_path / "sample.wav"

    adapter = FFmpegAdapter(ffmpeg_path="ffmpeg")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        out = adapter.extract_audio(str(dummy_input), str(target_output), format_type="wav")

        assert out == str(target_output)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        assert cmd[0] == "ffmpeg"
        assert "-vn" in cmd
        assert "-c:a" in cmd
        pcm_idx = cmd.index("-c:a") + 1
        assert cmd[pcm_idx] == "pcm_s16le"
        assert cmd[-1] == str(target_output)


def test_ffmpeg_extract_audio_flac_command(tmp_path):
    """Verify FFmpeg command arguments for lossless FLAC extraction."""
    dummy_input = tmp_path / "sample.mp4"
    dummy_input.write_bytes(b"dummy video data")
    target_output = tmp_path / "sample.flac"

    adapter = FFmpegAdapter(ffmpeg_path="ffmpeg")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        out = adapter.extract_audio(str(dummy_input), str(target_output), format_type="flac")

        assert out == str(target_output)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        assert "-vn" in cmd
        assert "-c:a" in cmd
        codec_idx = cmd.index("-c:a") + 1
        assert cmd[codec_idx] == "flac"


def test_ffmpeg_extract_audio_mp3_and_m4a_commands(tmp_path):
    """Verify FFmpeg command arguments for MP3 (320k) and M4A (192k aac)."""
    dummy_input = tmp_path / "video.mp4"
    dummy_input.write_bytes(b"dummy data")

    adapter = FFmpegAdapter(ffmpeg_path="ffmpeg")

    # MP3
    out_mp3 = tmp_path / "video.mp3"
    with patch("subprocess.run") as mock_run_mp3:
        mock_run_mp3.return_value = MagicMock(returncode=0)
        adapter.extract_audio(str(dummy_input), str(out_mp3), format_type="mp3")
        cmd_mp3 = mock_run_mp3.call_args[0][0]
        assert "libmp3lame" in cmd_mp3
        assert "320k" in cmd_mp3

    # M4A
    out_m4a = tmp_path / "video.m4a"
    with patch("subprocess.run") as mock_run_m4a:
        mock_run_m4a.return_value = MagicMock(returncode=0)
        adapter.extract_audio(str(dummy_input), str(out_m4a), format_type="m4a")
        cmd_m4a = mock_run_m4a.call_args[0][0]
        assert "aac" in cmd_m4a
        assert "192k" in cmd_m4a


def test_ffmpeg_extract_audio_missing_input_raises_exception(tmp_path):
    """Verify PostProcessingException is raised when input file does not exist."""
    adapter = FFmpegAdapter(ffmpeg_path="ffmpeg")
    non_existent = str(tmp_path / "missing.mp4")
    out_file = str(tmp_path / "out.wav")

    with pytest.raises(PostProcessingException, match="Input file not found"):
        adapter.extract_audio(non_existent, out_file, format_type="wav")


def test_ffmpeg_extract_audio_missing_binary_raises_exception(tmp_path):
    """Verify PostProcessingException is raised when ffmpeg binary is not available."""
    adapter = FFmpegAdapter(ffmpeg_path=None)
    adapter._ffmpeg_path = None  # Force None
    dummy = tmp_path / "exists.mp4"
    dummy.write_bytes(b"data")

    with pytest.raises(PostProcessingException, match="FFmpeg not found in system PATH"):
        adapter.extract_audio(str(dummy), str(tmp_path / "out.wav"), format_type="wav")


def test_ffmpeg_extract_audio_subprocess_failure_raises_exception(tmp_path):
    """Verify PostProcessingException is raised when ffmpeg execution returns non-zero error."""
    dummy = tmp_path / "input.mp4"
    dummy.write_bytes(b"data")
    adapter = FFmpegAdapter(ffmpeg_path="ffmpeg")

    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"Codec error")):
        with pytest.raises(PostProcessingException, match="FFmpeg audio extraction failed"):
            adapter.extract_audio(str(dummy), str(tmp_path / "out.wav"), format_type="wav")


# ---------------------------------------------------------------------------
# 4. YtDlpAdapter Target File Detection for Lossless Audio
# ---------------------------------------------------------------------------

def test_ytdlp_adapter_download_wav_target_file_detection(tmp_path):
    """Verify download() detects and returns .wav file produced on disk."""
    adapter = YtDlpAdapter()
    settings = AppSettings(download_dir=str(tmp_path))

    req = DownloadRequest(
        url="https://www.instagram.com/reel/C_test_wav/",
        quality=QualityOption.AUDIO_WAV,
        output_dir=str(tmp_path),
        media_item=MediaItem(
            url="https://www.instagram.com/reel/C_test_wav/",
            shortcode="C_test_wav",
            author="composer_artist",
            title="Symphony No 5",
            platform=Platform.INSTAGRAM,
        ),
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst

        def fake_extract(url, download=True):
            # yt-dlp with postprocessor creates .wav on disk
            prefix = "composer_artist_C_test_wav"
            out_file = tmp_path / f"{prefix}.wav"
            out_file.write_bytes(b"RIFF WAVE fmt data")
            return {"id": "C_test_wav", "title": "Symphony No 5"}

        mock_inst.extract_info.side_effect = fake_extract
        mock_inst.prepare_filename.return_value = str(tmp_path / "composer_artist_C_test_wav.mp4")
        mock_ydl_cls.return_value = mock_inst

        result_path = adapter.download(req, settings)
        assert result_path.endswith(".wav")
        assert Path(result_path).exists()


def test_ytdlp_adapter_download_flac_target_file_detection(tmp_path):
    """Verify download() detects and returns .flac file produced on disk."""
    adapter = YtDlpAdapter()
    settings = AppSettings(download_dir=str(tmp_path))

    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=audiovideo123",
        quality=QualityOption.AUDIO_FLAC,
        output_dir=str(tmp_path),
        media_item=MediaItem(
            url="https://www.youtube.com/watch?v=audiovideo123",
            shortcode="audiovideo123",
            author="lossless_studio",
            title="Studio Master Track",
            platform=Platform.YOUTUBE,
        ),
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_inst = MagicMock()
        mock_inst.__enter__.return_value = mock_inst

        def fake_extract(url, download=True):
            prefix = "lossless_studio_audiovideo123"
            out_file = tmp_path / f"{prefix}.flac"
            out_file.write_bytes(b"fLaC marker data")
            return {"id": "audiovideo123", "title": "Studio Master Track"}

        mock_inst.extract_info.side_effect = fake_extract
        mock_inst.prepare_filename.return_value = str(tmp_path / "lossless_studio_audiovideo123.mp4")
        mock_ydl_cls.return_value = mock_inst

        result_path = adapter.download(req, settings)
        assert result_path.endswith(".flac")
        assert Path(result_path).exists()
