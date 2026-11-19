"""Domain layer package initialization."""

from .models import (
    Platform,
    MediaType,
    QualityOption,
    DownloadStatus,
    DownloadProgress,
    MediaItem,
    DownloadRequest,
    AppSettings,
    DownloadHistoryItem,
)
from .exceptions import (
    DownloaderException,
    InvalidUrlException,
    ExtractionException,
    AuthenticationRequiredException,
    DownloadException,
    StorageException,
    NetworkException,
    PostProcessingException,
)
from .url_parser import InstagramUrlParser, YouTubeUrlParser, MediaUrlParser, UniversalUrlParser

__all__ = [
    "Platform",
    "MediaType",
    "QualityOption",
    "DownloadStatus",
    "DownloadProgress",
    "MediaItem",
    "DownloadRequest",
    "AppSettings",
    "DownloadHistoryItem",
    "DownloaderException",
    "InvalidUrlException",
    "ExtractionException",
    "AuthenticationRequiredException",
    "DownloadException",
    "StorageException",
    "NetworkException",
    "PostProcessingException",
    "InstagramUrlParser",
    "YouTubeUrlParser",
    "MediaUrlParser",
    "UniversalUrlParser",
]
