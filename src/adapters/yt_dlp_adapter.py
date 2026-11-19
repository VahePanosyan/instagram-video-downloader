"""yt-dlp adapter implementing IExtractor and IDownloader with high-performance configurations."""

import os
import re
import shutil
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

import yt_dlp
from yt_dlp.utils import DownloadError

from ..domain.models import (
    MediaItem,
    MediaType,
    Platform,
    DownloadRequest,
    DownloadProgress,
    QualityOption,
    AppSettings,
    SubtitleMode,
)
from ..domain.exceptions import (
    ExtractionException,
    DownloadException,
    AuthenticationRequiredException,
    NetworkException,
)
from ..domain.url_parser import YouTubeUrlParser, MediaUrlParser
from ..ports.extractor import IExtractor
from ..ports.downloader import IDownloader
from .ffmpeg_adapter import locate_ffmpeg_dir


class DownloadCancelledException(Exception):
    """Internal exception raised when download is cancelled by user."""
    pass


class YtDlpAdapter(IExtractor, IDownloader):
    """Adapter leveraging yt-dlp for Instagram media extraction and downloading."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def _build_base_options(self, settings: Optional[AppSettings] = None) -> Dict[str, Any]:
        """Builds standard yt-dlp parameters tuned for Instagram stability and speed."""
        ffmpeg_dir = locate_ffmpeg_dir()
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "user_agent": self.DEFAULT_USER_AGENT,
            "retries": 10,
            "fragment_retries": 10,
            "socket_timeout": 25,
            "concurrent_fragment_downloads": 4,
            "buffersize": 1024 * 1024,
            "nocheckcertificate": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
        }
        if ffmpeg_dir:
            opts["ffmpeg_location"] = ffmpeg_dir

        if settings:
            if settings.cookies_file and os.path.exists(settings.cookies_file):
                opts["cookiefile"] = settings.cookies_file
            if settings.cookies_browser and settings.cookies_browser.strip():
                opts["cookiesfrombrowser"] = (settings.cookies_browser.strip().lower(),)
            if settings.proxy and settings.proxy.strip():
                proxy = settings.proxy.strip()
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', proxy):
                    proxy = f"http://{proxy}"
                opts["proxy"] = proxy
            if settings.rate_limit_kb > 0:
                opts["ratelimit"] = settings.rate_limit_kb * 1024
            if getattr(settings, "use_aria2c", False) and shutil.which("aria2c"):
                opts["external_downloader"] = "aria2c"
                opts["external_downloader_args"] = ["-x", "16", "-s", "16", "-k", "1M"]

        return opts

    def _sanitize_filename_component(self, name: str) -> str:
        """Sanitizes strings for safe Windows/POSIX file paths."""
        if not name:
            return "instagram"
        # Remove invalid filename characters: \ / : * ? " < > |
        cleaned = re.sub(r'[\\/*?:"<>|]', "_", name)
        # Collapse whitespace/underscores
        cleaned = re.sub(r'[\s_]+', "_", cleaned).strip(" ._")
        return cleaned[:80] if cleaned else "instagram"

    def extract_info(self, url: str, settings: Optional[AppSettings] = None) -> MediaItem:
        """Extracts media metadata from an Instagram, YouTube, or extended media URL."""
        extended_allowed = getattr(settings, "enable_multi_platform", False) if settings else False
        platform, media_type, shortcode, canonical_url = MediaUrlParser.parse(url, extended=extended_allowed)

        ydl_opts = self._build_base_options(settings)
        if media_type == MediaType.PLAYLIST:
            ydl_opts["extract_flat"] = "in_playlist"
            ydl_opts["noplaylist"] = False
        else:
            ydl_opts["extract_flat"] = False
            ydl_opts["noplaylist"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(canonical_url, download=False)
                if not info:
                    raise ExtractionException(f"No metadata found for URL: {url}")

                # Handle playlist
                is_playlist = False
                playlist_urls: List[str] = []
                if media_type == MediaType.PLAYLIST or info.get("_type") == "playlist":
                    is_playlist = True
                    media_type = MediaType.PLAYLIST
                    entries = info.get("entries") or []
                    for entry in entries:
                        if entry:
                            entry_id = entry.get("id")
                            entry_url = entry.get("webpage_url") or entry.get("url")
                            if entry_url and not entry_url.startswith("http"):
                                entry_url = f"https://www.youtube.com/watch?v={entry_url}"
                            elif not entry_url and entry_id:
                                entry_url = f"https://www.youtube.com/watch?v={entry_id}"
                            if entry_url:
                                playlist_urls.append(entry_url)

                # Handle carousel/multi-item post
                is_carousel = False
                carousel_urls: List[str] = []
                if not is_playlist and "entries" in info and info["entries"]:
                    is_carousel = True
                    for entry in info["entries"]:
                        if entry and "webpage_url" in entry:
                            carousel_urls.append(entry["webpage_url"])

                if platform == Platform.YOUTUBE:
                    title = info.get("title") or info.get("description") or ""
                else:
                    title = info.get("description") or info.get("title") or ""

                author = info.get("uploader") or info.get("channel") or info.get("playlist_uploader") or ""
                duration = int(info.get("duration", 0)) if info.get("duration") else None
                thumbnail_url = info.get("thumbnail")
                view_count = info.get("view_count")
                like_count = info.get("like_count")
                upload_date = info.get("upload_date")

                resolved_type = (
                    MediaType.PLAYLIST if is_playlist else (
                        MediaType.CAROUSEL if is_carousel else media_type
                    )
                )

                return MediaItem(
                    url=canonical_url,
                    shortcode=shortcode,
                    media_type=resolved_type,
                    platform=platform,
                    title=title,
                    author=author,
                    duration_seconds=duration,
                    thumbnail_url=thumbnail_url,
                    view_count=view_count,
                    like_count=like_count,
                    upload_date=upload_date,
                    is_carousel=is_carousel,
                    carousel_urls=carousel_urls,
                    is_playlist=is_playlist,
                    playlist_urls=playlist_urls,
                    playlist_title=info.get("title") if is_playlist else None,
                    playlist_id=info.get("id") if is_playlist else None,
                    raw_info=info,
                )

        except DownloadError as e:
            err_msg = str(e)
            plat_name = "YouTube" if platform == Platform.YOUTUBE else "Instagram"
            if "cookie" in err_msg.lower() or "cookies" in err_msg.lower():
                raise AuthenticationRequiredException(
                    f"Cookie error while accessing {plat_name}: {err_msg}. "
                    "Please check your cookies file or browser selection in Settings.",
                    details=err_msg,
                )
            elif "proxy" in err_msg.lower():
                raise NetworkException(
                    f"Proxy error connecting to {plat_name}: {err_msg}. "
                    "Please verify your proxy settings (host, port, credentials).",
                    details=err_msg,
                )
            elif "age" in err_msg.lower():
                raise AuthenticationRequiredException(
                    f"{plat_name} age-restricted content. Please configure cookies in Settings.",
                    details=err_msg,
                )
            elif any(k in err_msg.lower() for k in ["login", "private", "sign in", "bot", "members-only"]):
                raise AuthenticationRequiredException(
                    f"{plat_name} authentication required (account is private, members-only, or verification prompt triggered). "
                    "Please provide cookies in Settings.",
                    details=err_msg,
                )
            elif "timed out" in err_msg.lower() or "connection" in err_msg.lower():
                raise NetworkException(f"Network timeout connecting to {plat_name}", details=err_msg)
            else:
                raise ExtractionException(f"Failed to extract {plat_name} media information", details=err_msg)
        except Exception as e:
            if isinstance(e, (ExtractionException, AuthenticationRequiredException, NetworkException)):
                raise
            raise ExtractionException(f"Unexpected extraction error: {str(e)}")

    def _determine_format(self, quality: QualityOption) -> tuple[str, list]:
        """Returns the format selector and postprocessors for yt-dlp."""
        quality = QualityOption.from_value(quality)
        postprocessors = []

        if quality == QualityOption.AUDIO_MP3:
            format_str = "bestaudio/best"
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            })
        elif quality == QualityOption.AUDIO_M4A:
            format_str = "bestaudio[ext=m4a]/bestaudio/best"
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            })
        elif quality == QualityOption.AUDIO_WAV:
            format_str = "bestaudio/best"
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            })
        elif quality == QualityOption.AUDIO_FLAC:
            format_str = "bestaudio/best"
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "flac",
            })
        elif quality == QualityOption.Q_2160P:
            format_str = (
                "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=2160]+bestaudio/"
                "bestvideo[width<=2160]+bestaudio/"
                "best[height<=2160][ext=mp4]/"
                "best[height<=2160]/"
                "best[width<=2160]/"
                "best"
            )
        elif quality == QualityOption.Q_1440P:
            format_str = (
                "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=1440]+bestaudio/"
                "bestvideo[width<=1440]+bestaudio/"
                "best[height<=1440][ext=mp4]/"
                "best[height<=1440]/"
                "best[width<=1440]/"
                "best"
            )
        elif quality == QualityOption.Q_1080P:
            format_str = (
                "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=1080]+bestaudio/"
                "bestvideo[width<=1080]+bestaudio/"
                "best[height<=1080][ext=mp4]/"
                "best[height<=1080]/"
                "best[width<=1080]/"
                "best"
            )
        elif quality == QualityOption.Q_720P:
            format_str = (
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=720]+bestaudio/"
                "bestvideo[width<=720]+bestaudio/"
                "best[height<=720][ext=mp4]/"
                "best[height<=720]/"
                "best[width<=720]/"
                "best"
            )
        elif quality == QualityOption.Q_480P:
            format_str = (
                "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=480]+bestaudio/"
                "bestvideo[width<=480]+bestaudio/"
                "best[height<=480][ext=mp4]/"
                "best[height<=480]/"
                "best[width<=480]/"
                "best"
            )
        elif quality == QualityOption.Q_360P:
            format_str = (
                "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=360]+bestaudio/"
                "bestvideo[width<=360]+bestaudio/"
                "best[height<=360][ext=mp4]/"
                "best[height<=360]/"
                "best[width<=360]/"
                "best"
            )
        else:  # QualityOption.BEST
            format_str = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo+bestaudio/"
                "best[ext=mp4]/best"
            )

        return format_str, postprocessors

    def download(
        self,
        request: DownloadRequest,
        settings: AppSettings,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> str:
        """Downloads Instagram or YouTube media according to the request specification."""
        request.quality = QualityOption.from_value(request.quality)
        out_dir = Path(request.output_dir or settings.download_dir or "./downloads")
        out_dir.mkdir(parents=True, exist_ok=True)

        platform = request.media_item.platform if request.media_item else MediaUrlParser.detect_platform(request.url)
        default_author = "youtube" if platform == Platform.YOUTUBE else "instagram"

        author = self._sanitize_filename_component(
            request.media_item.author if request.media_item and request.media_item.author else default_author
        )
        shortcode = self._sanitize_filename_component(
            request.media_item.shortcode if request.media_item and request.media_item.shortcode else request.id
        )
        title = self._sanitize_filename_component(
            request.media_item.title if request.media_item and request.media_item.title else shortcode
        )
        upload_date = self._sanitize_filename_component(
            request.media_item.upload_date if request.media_item and request.media_item.upload_date else ""
        )

        # Build output template
        template = request.filename_template or settings.filename_template or "{author}_{shortcode}"
        filename_prefix = (
            template.replace("{author}", author)
            .replace("{shortcode}", shortcode)
            .replace("{title}", title)
            .replace("{id}", shortcode)
            .replace("{date}", upload_date)
        )
        filename_prefix = self._sanitize_filename_component(filename_prefix)
        outtmpl = str(out_dir / f"{filename_prefix}.%(ext)s")

        # Check if downloading playlist
        is_item_playlist = bool(request.media_item and request.media_item.is_playlist)
        is_yt_playlist = (platform == Platform.YOUTUBE and YouTubeUrlParser.is_playlist(request.url))
        is_playlist_req = is_item_playlist or is_yt_playlist

        ydl_opts = self._build_base_options(settings)
        if is_playlist_req:
            ydl_opts["noplaylist"] = False
            playlist_folder = out_dir / filename_prefix
            playlist_folder.mkdir(parents=True, exist_ok=True)
            outtmpl = str(playlist_folder / "%(playlist_index)02d - %(title)s.%(ext)s")
        else:
            ydl_opts["noplaylist"] = True
            outtmpl = str(out_dir / f"{filename_prefix}.%(ext)s")

        format_str, postprocessors = self._determine_format(request.quality)
        ydl_opts["format"] = format_str
        ydl_opts["outtmpl"] = outtmpl

        # Subtitles configuration
        sub_mode = getattr(request, "subtitles_mode", SubtitleMode.NONE)
        if sub_mode == SubtitleMode.NONE and getattr(settings, "subtitles_enabled", False):
            sub_mode = getattr(settings, "subtitles_mode", SubtitleMode.NONE)

        if sub_mode in (SubtitleMode.EXTERNAL_SRT, SubtitleMode.EXTERNAL_VTT, SubtitleMode.EMBED):
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            langs_str = getattr(request, "subtitles_languages", "") or getattr(settings, "subtitles_languages", "en")
            langs = [l.strip() for l in langs_str.split(",") if l.strip()]
            if langs:
                ydl_opts["subtitleslangs"] = langs

            if sub_mode == SubtitleMode.EMBED:
                postprocessors.append({"key": "FFmpegEmbedSubtitle"})
            elif sub_mode == SubtitleMode.EXTERNAL_SRT:
                postprocessors.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})
            elif sub_mode == SubtitleMode.EXTERNAL_VTT:
                postprocessors.append({"key": "FFmpegSubtitlesConvertor", "format": "vtt"})

        # Metadata & thumbnail embedding
        if getattr(settings, "embed_metadata", True):
            postprocessors.append({"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": True})

        if getattr(settings, "embed_thumbnail", True) and request.quality in (
            QualityOption.AUDIO_MP3,
            QualityOption.AUDIO_M4A,
            QualityOption.AUDIO_FLAC,
        ):
            ydl_opts["writethumbnail"] = True
            postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        # Time range section clipping
        t_start = getattr(request, "time_range_start", None)
        t_end = getattr(request, "time_range_end", None)
        if t_start or t_end:
            def _parse_time(t_val):
                if not t_val:
                    return None
                parts = str(t_val).strip().split(":")
                try:
                    if len(parts) == 3:
                        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                    elif len(parts) == 2:
                        return float(parts[0]) * 60 + float(parts[1])
                    elif len(parts) == 1:
                        return float(parts[0])
                except Exception:
                    return None
                return None

            s_sec = _parse_time(t_start) or 0.0
            e_sec = _parse_time(t_end)
            from yt_dlp.utils import download_range_func
            ydl_opts["download_ranges"] = download_range_func(None, [(s_sec, e_sec if e_sec is not None else float("inf"))])
            ydl_opts["force_keyframes_at_cuts"] = True

        if postprocessors:
            ydl_opts["postprocessors"] = postprocessors

        downloaded_filepath: Optional[str] = None

        def progress_hook(d: Dict[str, Any]) -> None:
            nonlocal downloaded_filepath
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelledException("Download cancelled by user")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0.0
                eta = d.get("eta") or 0

                percent = (downloaded / total * 100.0) if total > 0 else 0.0
                speed_str = f"{speed / 1024:.1f} KB/s" if speed < 1024 * 1024 else f"{speed / (1024 * 1024):.2f} MB/s"
                eta_str = f"{eta // 60:02d}:{eta % 60:02d}" if eta else "--:--"

                prog = DownloadProgress(
                    percent=round(percent, 1),
                    speed_bytes_sec=speed,
                    speed_str=speed_str,
                    eta_seconds=eta,
                    eta_str=eta_str,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    status_message=f"Downloading {round(percent, 1)}%",
                )
                if progress_callback:
                    progress_callback(prog)

            elif status == "finished":
                filename = d.get("filename")
                if filename:
                    downloaded_filepath = filename
                if progress_callback:
                    progress_callback(
                        DownloadProgress(
                            percent=100.0,
                            status_message="Processing / Finalizing...",
                        )
                    )

        def postprocessor_hook(d: Dict[str, Any]) -> None:
            nonlocal downloaded_filepath
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelledException("Download cancelled by user")
            if d.get("status") == "finished":
                info_dict = d.get("info_dict") or {}
                final_path = info_dict.get("filepath") or d.get("filepath")
                if final_path:
                    downloaded_filepath = final_path

        ydl_opts["progress_hooks"] = [progress_hook]
        ydl_opts["postprocessor_hooks"] = [postprocessor_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request.url, download=True)
                if not downloaded_filepath and info:
                    # Resolve expected output file path
                    if "entries" in info and info["entries"]:
                        first_entry = next((e for e in info["entries"] if e), None)
                        expected = ydl.prepare_filename(first_entry) if first_entry else ydl.prepare_filename(info)
                    else:
                        expected = ydl.prepare_filename(info)

                    if request.quality == QualityOption.AUDIO_MP3:
                        expected = str(Path(expected).with_suffix(".mp3"))
                    elif request.quality == QualityOption.AUDIO_M4A:
                        expected = str(Path(expected).with_suffix(".m4a"))
                    elif request.quality == QualityOption.AUDIO_WAV:
                        expected = str(Path(expected).with_suffix(".wav"))
                    elif request.quality == QualityOption.AUDIO_FLAC:
                        expected = str(Path(expected).with_suffix(".flac"))
                    downloaded_filepath = expected

            if is_playlist_req:
                playlist_folder = out_dir / filename_prefix
                if playlist_folder.exists():
                    files = [f for f in playlist_folder.iterdir() if f.is_file()]
                    if files or downloaded_filepath:
                        return str(playlist_folder)

            if downloaded_filepath and os.path.exists(downloaded_filepath):
                return downloaded_filepath

            # Check for converted audio variants
            if request.quality == QualityOption.AUDIO_MP3:
                mp3_candidate = out_dir / f"{filename_prefix}.mp3"
                if mp3_candidate.exists():
                    return str(mp3_candidate)
            elif request.quality == QualityOption.AUDIO_M4A:
                m4a_candidate = out_dir / f"{filename_prefix}.m4a"
                if m4a_candidate.exists():
                    return str(m4a_candidate)
            elif request.quality == QualityOption.AUDIO_WAV:
                wav_candidate = out_dir / f"{filename_prefix}.wav"
                if wav_candidate.exists():
                    return str(wav_candidate)
            elif request.quality == QualityOption.AUDIO_FLAC:
                flac_candidate = out_dir / f"{filename_prefix}.flac"
                if flac_candidate.exists():
                    return str(flac_candidate)

            # Fallback search in output directory if filename changed during post-processing
            for candidate in out_dir.glob(f"{filename_prefix}.*"):
                if candidate.is_file():
                    return str(candidate)

            raise DownloadException("File download completed but target file was not found on disk.")

        except DownloadCancelledException:
            raise
        except DownloadError as e:
            err_msg = str(e)
            plat_name = "YouTube" if platform == Platform.YOUTUBE else "Instagram"
            if "cookie" in err_msg.lower() or "cookies" in err_msg.lower():
                raise AuthenticationRequiredException(
                    f"Cookie error while accessing {plat_name}: {err_msg}. "
                    "Please check your cookies file or browser selection in Settings.",
                    details=err_msg,
                )
            elif "proxy" in err_msg.lower():
                raise NetworkException(
                    f"Proxy error connecting to {plat_name}: {err_msg}. "
                    "Please verify your proxy settings (host, port, credentials).",
                    details=err_msg,
                )
            elif "age" in err_msg.lower():
                raise AuthenticationRequiredException(
                    f"{plat_name} age-restricted content. Please configure cookies in Settings.",
                    details=err_msg,
                )
            elif any(k in err_msg.lower() for k in ["login", "private", "sign in", "bot", "members-only"]):
                raise AuthenticationRequiredException(
                    f"{plat_name} authentication required (account is private, members-only, or verification prompt triggered). "
                    "Please provide cookies in Settings.",
                    details=err_msg,
                )
            elif "timed out" in err_msg.lower() or "connection" in err_msg.lower():
                raise NetworkException(f"Network timeout connecting to {plat_name}", details=err_msg)
            raise DownloadException(f"Download error: {err_msg}")
        except Exception as e:
            if isinstance(e, DownloadCancelledException):
                raise
            plat_name = "YouTube" if platform == Platform.YOUTUBE else "Instagram"
            raise DownloadException(f"Failed to download {plat_name} video: {str(e)}")
