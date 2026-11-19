"""Adapters layer package initialization."""

from .ffmpeg_adapter import (
    FFmpegAdapter,
    locate_ffmpeg_bin,
    locate_ffmpeg_dir,
    ensure_ffmpeg_in_path,
)
from .direct_scraper import DirectInstagramScraper, DirectYouTubeScraper, UniversalDirectScraper
from .yt_dlp_adapter import YtDlpAdapter, DownloadCancelledException
from .json_repository import JsonSettingsRepository, JsonHistoryRepository

__all__ = [
    "FFmpegAdapter",
    "locate_ffmpeg_bin",
    "locate_ffmpeg_dir",
    "ensure_ffmpeg_in_path",
    "DirectInstagramScraper",
    "DirectYouTubeScraper",
    "UniversalDirectScraper",
    "YtDlpAdapter",
    "DownloadCancelledException",
    "JsonSettingsRepository",
    "JsonHistoryRepository",
]
