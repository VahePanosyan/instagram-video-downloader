"""Domain models for Instagram Downloader."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import datetime
import uuid


def enum_value(obj: Any) -> str:
    """Safely extracts string representation from an Enum or returns str(obj)."""
    if obj is None:
        return ""
    if isinstance(obj, Enum):
        return str(obj.value)
    if hasattr(obj, "value") and not callable(getattr(obj, "value", None)):
        return str(obj.value)
    return str(obj)


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    REDDIT = "reddit"
    FACEBOOK = "facebook"
    PINTEREST = "pinterest"
    TWITCH = "twitch"
    SOUNDCLOUD = "soundcloud"
    UNIVERSAL = "universal"
    UNKNOWN = "unknown"

    @classmethod
    def from_value(cls, val: Any) -> "Platform":
        if isinstance(val, cls):
            return val
        if isinstance(val, Enum):
            val = val.value
        elif hasattr(val, "value") and not callable(getattr(val, "value", None)):
            val = val.value
        if isinstance(val, str):
            val_lower = val.lower().strip()
            for item in cls:
                if item.value == val_lower or item.name.lower() == val_lower:
                    return item
            if "insta" in val_lower or "ig" in val_lower:
                return cls.INSTAGRAM
            if "you" in val_lower or "yt" in val_lower:
                return cls.YOUTUBE
            if "tik" in val_lower or "tok" in val_lower:
                return cls.TIKTOK
            if "twit" in val_lower or "x.com" in val_lower or val_lower == "x":
                return cls.TWITTER
            if "red" in val_lower:
                return cls.REDDIT
            if "face" in val_lower or "fb" in val_lower:
                return cls.FACEBOOK
            if "pin" in val_lower:
                return cls.PINTEREST
            if "twitc" in val_lower:
                return cls.TWITCH
            if "soundc" in val_lower:
                return cls.SOUNDCLOUD
            if "uni" in val_lower or "web" in val_lower or "generic" in val_lower:
                return cls.UNIVERSAL
        return cls.UNKNOWN


class MediaType(str, Enum):
    REEL = "reel"
    POST = "post"
    STORY = "story"
    TV = "tv"
    CAROUSEL = "carousel"
    VIDEO = "video"
    SHORT = "short"
    PLAYLIST = "playlist"
    UNKNOWN = "unknown"

    @classmethod
    def from_value(cls, val: Any) -> "MediaType":
        if isinstance(val, cls):
            return val
        if isinstance(val, Enum):
            val = val.value
        elif hasattr(val, "value") and not callable(getattr(val, "value", None)):
            val = val.value
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            val = str(int(val))
        if isinstance(val, str):
            val_lower = val.lower().strip()
            for item in cls:
                if item.value == val_lower or item.name.lower() == val_lower:
                    return item
            aliases = {
                "reels": cls.REEL,
                "reel": cls.REEL,
                "clip": cls.REEL,
                "posts": cls.POST,
                "post": cls.POST,
                "photo": cls.POST,
                "p": cls.POST,
                "stories": cls.STORY,
                "story": cls.STORY,
                "highlight": cls.STORY,
                "highlights": cls.STORY,
                "tv": cls.TV,
                "igtv": cls.TV,
                "carousel": cls.CAROUSEL,
                "carousels": cls.CAROUSEL,
                "sidecar": cls.CAROUSEL,
                "video": cls.VIDEO,
                "videos": cls.VIDEO,
                "yt_video": cls.VIDEO,
                "youtube_video": cls.VIDEO,
                "short": cls.SHORT,
                "shorts": cls.SHORT,
                "yt_short": cls.SHORT,
                "youtube_short": cls.SHORT,
                "playlist": cls.PLAYLIST,
                "playlists": cls.PLAYLIST,
                "list": cls.PLAYLIST,
            }
            if val_lower in aliases:
                return aliases[val_lower]
        return cls.UNKNOWN


class QualityOption(str, Enum):
    BEST = "best"
    Q_1080P = "1080p"
    Q_720P = "720p"
    Q_480P = "480p"
    AUDIO_MP3 = "mp3"
    AUDIO_M4A = "m4a"
    Q_2160P = "2160p"
    Q_1440P = "1440p"
    Q_360P = "360p"
    AUDIO_WAV = "wav"
    AUDIO_FLAC = "flac"

    @classmethod
    def display_names(cls) -> Dict["QualityOption", str]:
        return {
            cls.BEST: "Best Available Quality (MP4)",
            cls.Q_1080P: "Full HD 1080p (MP4)",
            cls.Q_720P: "HD 720p (MP4)",
            cls.Q_480P: "SD 480p (MP4)",
            cls.AUDIO_MP3: "Audio Only (MP3 320k)",
            cls.AUDIO_M4A: "Audio Only (M4A/AAC)",
            cls.Q_2160P: "4K Ultra HD 2160p (MP4)",
            cls.Q_1440P: "2K Quad HD 1440p (MP4)",
            cls.Q_360P: "Low SD 360p (MP4)",
            cls.AUDIO_WAV: "Audio Only (WAV Lossless)",
            cls.AUDIO_FLAC: "Audio Only (FLAC Lossless)",
        }

    @classmethod
    def get_display_name(cls, val: Any) -> str:
        opt = cls.from_value(val)
        return cls.display_names().get(opt, enum_value(opt))

    @classmethod
    def from_value(cls, val: Any) -> "QualityOption":
        if isinstance(val, cls):
            return val
        if isinstance(val, Enum):
            val = val.value
        elif hasattr(val, "value") and not callable(getattr(val, "value", None)):
            val = val.value
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            val = str(int(val))
        if isinstance(val, str):
            val_clean = val.strip()
            val_lower = val_clean.lower()
            # 1. Direct match on enum values or member names
            for item in cls:
                if item.value == val_lower or item.name.lower() == val_lower:
                    return item
            # 2. Match display names (e.g. "Best Available Quality (MP4)", "Full HD 1080p (MP4)")
            for item, disp in cls.display_names().items():
                if disp.lower().strip() == val_lower:
                    return item
            # 3. Match common shorthand aliases and partial substrings
            if "2160" in val_lower or "4k" in val_lower:
                return cls.Q_2160P
            if "1440" in val_lower or "2k" in val_lower:
                return cls.Q_1440P
            if "1080" in val_lower:
                return cls.Q_1080P
            if "720" in val_lower:
                return cls.Q_720P
            if "480" in val_lower:
                return cls.Q_480P
            if "360" in val_lower:
                return cls.Q_360P
            if "mp3" in val_lower:
                return cls.AUDIO_MP3
            if "m4a" in val_lower or "aac" in val_lower:
                return cls.AUDIO_M4A
            if "wav" in val_lower or "wave" in val_lower:
                return cls.AUDIO_WAV
            if "flac" in val_lower or "lossless" in val_lower:
                return cls.AUDIO_FLAC
            if "audio" in val_lower:
                return cls.AUDIO_MP3
            if "best" in val_lower:
                return cls.BEST
        return cls.BEST


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    FETCHING_INFO = "fetching_info"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def from_value(cls, val: Any) -> "DownloadStatus":
        if isinstance(val, cls):
            return val
        if isinstance(val, Enum):
            val = val.value
        elif hasattr(val, "value") and not callable(getattr(val, "value", None)):
            val = val.value
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            val = str(int(val))
        if isinstance(val, str):
            val_lower = val.lower().strip().replace(" ", "_").replace("-", "_")
            for item in cls:
                if item.value == val_lower or item.name.lower() == val_lower:
                    return item
            aliases = {
                "queue": cls.QUEUED,
                "pending": cls.QUEUED,
                "waiting": cls.QUEUED,
                "fetch": cls.FETCHING_INFO,
                "fetching": cls.FETCHING_INFO,
                "fetching...": cls.FETCHING_INFO,
                "download": cls.DOWNLOADING,
                "downloading...": cls.DOWNLOADING,
                "process": cls.PROCESSING,
                "processing...": cls.PROCESSING,
                "converting": cls.PROCESSING,
                "done": cls.COMPLETED,
                "finished": cls.COMPLETED,
                "complete": cls.COMPLETED,
                "success": cls.COMPLETED,
                "fail": cls.FAILED,
                "error": cls.FAILED,
                "cancel": cls.CANCELLED,
                "canceled": cls.CANCELLED,
                "cancelled": cls.CANCELLED,
                "stopped": cls.CANCELLED,
            }
            if val_lower in aliases:
                return aliases[val_lower]
        return cls.QUEUED


class SubtitleMode(str, Enum):
    NONE = "none"
    EXTERNAL_SRT = "srt"
    EXTERNAL_VTT = "vtt"
    EMBED = "embed"

    @classmethod
    def from_value(cls, val: Any) -> "SubtitleMode":
        if isinstance(val, cls):
            return val
        if isinstance(val, Enum):
            val = val.value
        elif hasattr(val, "value") and not callable(getattr(val, "value", None)):
            val = val.value
        if isinstance(val, str):
            val_lower = val.lower().strip()
            for item in cls:
                if item.value == val_lower or item.name.lower() == val_lower:
                    return item
            if "srt" in val_lower:
                return cls.EXTERNAL_SRT
            if "vtt" in val_lower:
                return cls.EXTERNAL_VTT
            if "embed" in val_lower:
                return cls.EMBED
        return cls.NONE


@dataclass
class DownloadProgress:
    percent: float = 0.0
    speed_bytes_sec: float = 0.0
    speed_str: str = "0 KB/s"
    eta_seconds: int = 0
    eta_str: str = "--:--"
    downloaded_bytes: int = 0
    total_bytes: int = 0
    status_message: str = "Pending"

    @property
    def formatted_size(self) -> str:
        if self.total_bytes <= 0:
            if self.downloaded_bytes > 0:
                return f"{self.downloaded_bytes / (1024 * 1024):.1f} MB"
            return "--"
        return f"{self.downloaded_bytes / (1024 * 1024):.1f} / {self.total_bytes / (1024 * 1024):.1f} MB"


@dataclass
class MediaItem:
    url: str
    shortcode: str
    media_type: MediaType = MediaType.REEL
    platform: Platform = Platform.INSTAGRAM
    title: str = ""
    author: str = ""
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    upload_date: Optional[str] = None
    is_carousel: bool = False
    carousel_urls: List[str] = field(default_factory=list)
    is_playlist: bool = False
    playlist_urls: List[str] = field(default_factory=list)
    playlist_title: Optional[str] = None
    playlist_id: Optional[str] = None
    direct_video_url: Optional[str] = None
    raw_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.media_type, MediaType):
            self.media_type = MediaType.from_value(self.media_type)
        if not isinstance(self.platform, Platform):
            self.platform = Platform.from_value(self.platform)

    @property
    def formatted_duration(self) -> str:
        if not self.duration_seconds:
            return "Unknown"
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes}:{seconds:02d}"

    @property
    def display_title(self) -> str:
        if self.title:
            cleaned = " ".join(self.title.split())
            return cleaned[:60] + "..." if len(cleaned) > 60 else cleaned
        plat_str = enum_value(self.platform).capitalize() if self.platform != Platform.UNKNOWN else "Media"
        type_str = enum_value(self.media_type).capitalize()
        return f"{plat_str} {type_str} ({self.shortcode})"


@dataclass
class DownloadRequest:
    url: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    media_item: Optional[MediaItem] = None
    quality: QualityOption = QualityOption.BEST
    output_dir: str = ""
    filename_template: str = "{author}_{shortcode}"
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: DownloadProgress = field(default_factory=DownloadProgress)
    error_message: Optional[str] = None
    saved_filepath: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    finished_at: Optional[str] = None
    subtitles_mode: SubtitleMode = SubtitleMode.NONE
    subtitles_languages: str = "en"
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.quality, QualityOption):
            self.quality = QualityOption.from_value(self.quality)
        if not isinstance(self.status, DownloadStatus):
            self.status = DownloadStatus.from_value(self.status)
        if not isinstance(self.subtitles_mode, SubtitleMode):
            self.subtitles_mode = SubtitleMode.from_value(self.subtitles_mode)


@dataclass
class AppSettings:
    download_dir: str = ""
    concurrent_downloads: int = 3
    default_quality: QualityOption = QualityOption.BEST
    filename_template: str = "{author}_{shortcode}"
    rate_limit_kb: int = 0  # 0 = unlimited
    proxy: str = ""
    cookies_file: str = ""
    cookies_browser: str = ""
    auto_paste_clipboard: bool = True
    dark_theme: bool = True
    sound_notifications: bool = False
    subtitles_enabled: bool = False
    subtitles_mode: SubtitleMode = SubtitleMode.NONE
    subtitles_languages: str = "en"
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    use_aria2c: bool = False
    close_to_tray: bool = False

    def __post_init__(self):
        if not isinstance(self.default_quality, QualityOption):
            self.default_quality = QualityOption.from_value(self.default_quality)
        if not isinstance(self.subtitles_mode, SubtitleMode):
            self.subtitles_mode = SubtitleMode.from_value(self.subtitles_mode)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "download_dir": self.download_dir,
            "concurrent_downloads": self.concurrent_downloads,
            "default_quality": enum_value(self.default_quality),
            "filename_template": self.filename_template,
            "rate_limit_kb": self.rate_limit_kb,
            "proxy": self.proxy,
            "cookies_file": self.cookies_file,
            "cookies_browser": self.cookies_browser,
            "auto_paste_clipboard": self.auto_paste_clipboard,
            "dark_theme": self.dark_theme,
            "sound_notifications": self.sound_notifications,
            "subtitles_enabled": self.subtitles_enabled,
            "subtitles_mode": enum_value(self.subtitles_mode),
            "subtitles_languages": self.subtitles_languages,
            "embed_thumbnail": self.embed_thumbnail,
            "embed_metadata": self.embed_metadata,
            "use_aria2c": self.use_aria2c,
            "close_to_tray": self.close_to_tray,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppSettings":
        quality_str = data.get("default_quality", QualityOption.BEST)
        quality = QualityOption.from_value(quality_str)
        sub_mode_str = data.get("subtitles_mode", SubtitleMode.NONE)
        sub_mode = SubtitleMode.from_value(sub_mode_str)

        return cls(
            download_dir=data.get("download_dir", ""),
            concurrent_downloads=int(data.get("concurrent_downloads", 3)),
            default_quality=quality,
            filename_template=data.get("filename_template", "{author}_{shortcode}"),
            rate_limit_kb=int(data.get("rate_limit_kb", 0)),
            proxy=data.get("proxy", ""),
            cookies_file=data.get("cookies_file", ""),
            cookies_browser=data.get("cookies_browser", ""),
            auto_paste_clipboard=bool(data.get("auto_paste_clipboard", True)),
            dark_theme=bool(data.get("dark_theme", True)),
            sound_notifications=bool(data.get("sound_notifications", False)),
            subtitles_enabled=bool(data.get("subtitles_enabled", False)),
            subtitles_mode=sub_mode,
            subtitles_languages=str(data.get("subtitles_languages", "en")),
            embed_thumbnail=bool(data.get("embed_thumbnail", True)),
            embed_metadata=bool(data.get("embed_metadata", True)),
            use_aria2c=bool(data.get("use_aria2c", False)),
            close_to_tray=bool(data.get("close_to_tray", False)),
        )


@dataclass
class DownloadHistoryItem:
    id: str
    url: str
    title: str
    author: str
    file_path: str
    file_size_bytes: int
    quality: str
    downloaded_at: str
    platform: str = "instagram"

    def __post_init__(self):
        self.quality = enum_value(self.quality)
        self.platform = enum_value(self.platform) or "instagram"

    @property
    def formatted_size(self) -> str:
        mb = self.file_size_bytes / (1024 * 1024)
        return f"{mb:.2f} MB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "quality": self.quality,
            "downloaded_at": self.downloaded_at,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DownloadHistoryItem":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            url=data.get("url", ""),
            title=data.get("title", ""),
            author=data.get("author", "Unknown"),
            file_path=data.get("file_path", ""),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            quality=data.get("quality", "best"),
            downloaded_at=data.get("downloaded_at", datetime.datetime.now().isoformat()),
            platform=data.get("platform", "instagram"),
        )
