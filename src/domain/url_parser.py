"""URL parser and validator for Instagram links."""

import re
from urllib.parse import urlparse, urlunparse
from typing import Tuple, Optional
from .models import MediaType, Platform
from .exceptions import InvalidUrlException


class InstagramUrlParser:
    """Parses, sanitizes, and classifies Instagram URLs."""

    # Matches instagram domain variants
    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.)?(instagram\.com|instagr\.am)/", re.IGNORECASE
    )

    # Patterns for different Instagram media types
    # 1. Reels: /reel/{shortcode}, /reels/{shortcode}, /share/reel/{shortcode}, or /share/r/{shortcode}
    REEL_PATTERN = re.compile(
        r"(?:/share)?/(?:reels?|r)/(?P<shortcode>[A-Za-z0-9_-]+)/?", re.IGNORECASE
    )

    # 2. Posts: /p/{shortcode} or /share/p/{shortcode}
    POST_PATTERN = re.compile(
        r"(?:/share)?/p/(?P<shortcode>[A-Za-z0-9_-]+)/?", re.IGNORECASE
    )

    # 3. TV / IGTV: /tv/{shortcode}
    TV_PATTERN = re.compile(
        r"/tv/(?P<shortcode>[A-Za-z0-9_-]+)/?", re.IGNORECASE
    )

    # 4. Stories:
    # 4a. Highlights: /stories/highlights/{highlight_id}
    STORY_HIGHLIGHT_PATTERN = re.compile(
        r"/stories/highlights/(?P<highlight_id>[0-9]+)/?", re.IGNORECASE
    )
    # 4b. Single Story: /stories/{username}/{story_id}
    STORY_PATTERN = re.compile(
        r"/stories/(?P<username>[A-Za-z0-9_.-]+)/(?P<story_id>[0-9]+)/?", re.IGNORECASE
    )
    # 4c. User Story Tray: /stories/{username}
    USER_STORY_PATTERN = re.compile(
        r"/stories/(?P<username>[A-Za-z0-9_.-]+)/?", re.IGNORECASE
    )

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        """Strips query parameters, tracking tags (e.g. ?igsh=...), whitespace."""
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")

        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        parsed = urlparse(url)
        # Strip query and fragments to produce clean canonical URL
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", "", ""))
        return clean_url

    @classmethod
    def parse(cls, raw_url: str) -> Tuple[MediaType, str, str]:
        """
        Parses an Instagram URL.
        Returns:
            Tuple of (MediaType, shortcode_or_id, canonical_url)
        Raises:
            InvalidUrlException if URL is not a recognized Instagram media URL.
        """
        clean_url = cls.sanitize_url(raw_url)
        parsed = urlparse(clean_url)

        netloc = parsed.netloc.lower()
        valid_domains = ["instagram.com", "instagr.am", "www.instagram.com", "m.instagram.com"]
        is_ig = netloc in valid_domains or netloc.endswith(".instagram.com") or netloc.endswith(".instagr.am")
        if not is_ig:
            raise InvalidUrlException(f"Not an Instagram URL: {raw_url}")

        path = parsed.path

        # Check Reel
        reel_match = cls.REEL_PATTERN.search(path)
        if reel_match:
            shortcode = reel_match.group("shortcode")
            canonical = f"https://www.instagram.com/reel/{shortcode}/"
            return MediaType.REEL, shortcode, canonical

        # Check Post
        post_match = cls.POST_PATTERN.search(path)
        if post_match:
            shortcode = post_match.group("shortcode")
            canonical = f"https://www.instagram.com/p/{shortcode}/"
            return MediaType.POST, shortcode, canonical

        # Check TV
        tv_match = cls.TV_PATTERN.search(path)
        if tv_match:
            shortcode = tv_match.group("shortcode")
            canonical = f"https://www.instagram.com/tv/{shortcode}/"
            return MediaType.TV, shortcode, canonical

        # Check Story Highlight
        high_match = cls.STORY_HIGHLIGHT_PATTERN.search(path)
        if high_match:
            hid = high_match.group("highlight_id")
            canonical = f"https://www.instagram.com/stories/highlights/{hid}/"
            return MediaType.STORY, f"highlight_{hid}", canonical

        # Check Single Story
        story_match = cls.STORY_PATTERN.search(path)
        if story_match:
            username = story_match.group("username")
            story_id = story_match.group("story_id")
            canonical = f"https://www.instagram.com/stories/{username}/{story_id}/"
            return MediaType.STORY, f"{username}_{story_id}", canonical

        # Check User Story Tray (e.g. /stories/{username}/)
        user_story_match = cls.USER_STORY_PATTERN.search(path)
        if user_story_match and user_story_match.group("username").lower() != "highlights":
            username = user_story_match.group("username")
            canonical = f"https://www.instagram.com/stories/{username}/"
            return MediaType.STORY, f"{username}_story", canonical

        raise InvalidUrlException(
            f"Could not identify Instagram post, reel, story or TV item in URL: {raw_url}"
        )

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        """Returns True if the URL is a supported Instagram URL, False otherwise."""
        try:
            cls.parse(raw_url)
            return True
        except (InvalidUrlException, Exception):
            return False


class YouTubeUrlParser:
    """Parses, sanitizes, and classifies YouTube URLs (Videos, Shorts, Playlists, Music, Live)."""

    # Matches youtube domain variants
    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE
    )

    # 1. YouTube Shorts: /shorts/{id}
    SHORTS_PATTERN = re.compile(
        r"/shorts/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 2. Watch URLs: /watch?v={id} or ?v={id} or &v={id}
    WATCH_PATTERN = re.compile(
        r"(?:/watch(?:\.php)?\?(?:.*&)?|[?&])v=(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 3. Shortened youtu.be URLs: youtu.be/{id}
    YOUTUBE_SHORT_DOMAIN_PATTERN = re.compile(
        r"youtu\.be/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 4. Embed URLs: /embed/{id}
    EMBED_PATTERN = re.compile(
        r"/embed/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 5. Live stream URLs: /live/{id}
    LIVE_PATTERN = re.compile(
        r"/live/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 6. Legacy /v/{id}
    V_PATTERN = re.compile(
        r"/v/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 7. Playlist ID pattern
    PLAYLIST_PARAM_PATTERN = re.compile(
        r"[?&]list=(?P<list_id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )
    PLAYLIST_PATH_PATTERN = re.compile(
        r"/playlist\?(?:.*&)?list=(?P<list_id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    # 8. Channel patterns (@handle, /channel/{id}, /c/{custom}, /user/{name})
    CHANNEL_HANDLE_PATTERN = re.compile(
        r"/@(?P<handle>[A-Za-z0-9_.-]+)", re.IGNORECASE
    )
    CHANNEL_ID_PATTERN = re.compile(
        r"/channel/(?P<channel_id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )
    CHANNEL_CUSTOM_PATTERN = re.compile(
        r"/(?:c|user)/(?P<custom_name>[A-Za-z0-9_.-]+)", re.IGNORECASE
    )

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        """Sanitizes YouTube URL and returns canonical form."""
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")

        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        valid_domains = [
            "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
            "youtu.be", "www.youtu.be",
        ]
        is_yt = netloc in valid_domains or any(netloc.endswith("." + d) for d in valid_domains)
        if not is_yt:
            raise InvalidUrlException(f"Not a YouTube URL: {raw_url}")

        # Check channel
        ch = cls.extract_channel(url)
        if ch:
            if ch.startswith("@"):
                return f"https://www.youtube.com/{ch}/videos"
            elif ch.startswith("UC"):
                return f"https://www.youtube.com/channel/{ch}/videos"
            else:
                return f"https://www.youtube.com/c/{ch}/videos"

        # Try extract playlist
        if "/playlist" in parsed.path:
            pl_match = cls.PLAYLIST_PARAM_PATTERN.search(url)
            if pl_match:
                list_id = pl_match.group("list_id")
                return f"https://www.youtube.com/playlist?list={list_id}"

        # Try extract shorts
        shorts_match = cls.SHORTS_PATTERN.search(parsed.path)
        if shorts_match:
            vid = shorts_match.group("id")
            return f"https://www.youtube.com/shorts/{vid}"

        # Try extract standard video
        vid = cls.extract_video_id(url)
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"

        # If it's a playlist without video
        pl_id = cls.extract_playlist_id(url)
        if pl_id:
            return f"https://www.youtube.com/playlist?list={pl_id}"

        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return clean_url

    @classmethod
    def extract_video_id(cls, raw_url: str) -> Optional[str]:
        """Extracts 11-char YouTube video ID if present in the URL."""
        if not raw_url:
            return None
        url = raw_url.strip()

        # Check Shorts
        match = cls.SHORTS_PATTERN.search(url)
        if match:
            return match.group("id")

        # Check watch?v=...
        match = cls.WATCH_PATTERN.search(url)
        if match:
            return match.group("id")

        # Check youtu.be/...
        match = cls.YOUTUBE_SHORT_DOMAIN_PATTERN.search(url)
        if match:
            return match.group("id")

        # Check embed/...
        match = cls.EMBED_PATTERN.search(url)
        if match:
            return match.group("id")

        # Check live/...
        match = cls.LIVE_PATTERN.search(url)
        if match:
            return match.group("id")

        # Check /v/...
        match = cls.V_PATTERN.search(url)
        if match:
            return match.group("id")

        return None

    @classmethod
    def extract_playlist_id(cls, raw_url: str) -> Optional[str]:
        """Extracts playlist ID if present in query parameters."""
        if not raw_url:
            return None
        match = cls.PLAYLIST_PARAM_PATTERN.search(raw_url)
        if match:
            return match.group("list_id")
        return None

    @classmethod
    def extract_channel(cls, raw_url: str) -> Optional[str]:
        """Extracts channel handle (@handle), ID (UC...), or custom name if present."""
        if not raw_url:
            return None
        url = raw_url.strip()
        parsed = urlparse(url if "://" in url else "https://" + url)
        path = parsed.path

        m = cls.CHANNEL_HANDLE_PATTERN.search(path)
        if m:
            return f"@{m.group('handle')}"
        m = cls.CHANNEL_ID_PATTERN.search(path)
        if m:
            return m.group("channel_id")
        m = cls.CHANNEL_CUSTOM_PATTERN.search(path)
        if m:
            return m.group("custom_name")
        return None

    @classmethod
    def is_playlist(cls, raw_url: str, include_watch_with_list: bool = False) -> bool:
        """Returns True if the URL points specifically to a playlist or channel collection."""
        if not raw_url:
            return False
        url = raw_url.strip()
        parsed = urlparse(url if "://" in url else "https://" + url)
        if "/playlist" in parsed.path:
            return cls.extract_playlist_id(url) is not None
        if cls.extract_channel(url):
            return True
        if "list=" in url:
            if include_watch_with_list:
                return cls.extract_playlist_id(url) is not None
            return not bool(cls.extract_video_id(url))
        return False

    @classmethod
    def parse(cls, raw_url: str, prefer_playlist: bool = False) -> Tuple[MediaType, str, str]:
        """
        Parses a YouTube URL.
        Returns:
            Tuple of (MediaType, id_or_list_id, canonical_url)
        Raises:
            InvalidUrlException if URL is not a recognized YouTube URL.
        """
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")

        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        valid_domains = [
            "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
            "youtu.be", "www.youtu.be",
        ]
        is_yt = netloc in valid_domains or any(netloc.endswith("." + d) for d in valid_domains)
        if not is_yt:
            raise InvalidUrlException(f"Not a YouTube URL: {raw_url}")

        # 0. If prefer_playlist is True and a playlist ID is present:
        if prefer_playlist:
            pl_id = cls.extract_playlist_id(url)
            if pl_id:
                canonical = f"https://www.youtube.com/playlist?list={pl_id}"
                return MediaType.PLAYLIST, pl_id, canonical

        # 1. Check Shorts
        shorts_match = cls.SHORTS_PATTERN.search(parsed.path)
        if shorts_match:
            video_id = shorts_match.group("id")
            canonical = f"https://www.youtube.com/shorts/{video_id}"
            return MediaType.SHORT, video_id, canonical

        # 2. Check Playlist URL (/playlist?list=... or list= with no v=)
        if "/playlist" in parsed.path or (cls.PLAYLIST_PARAM_PATTERN.search(url) and not cls.extract_video_id(url)):
            pl_match = cls.PLAYLIST_PARAM_PATTERN.search(url)
            if pl_match:
                list_id = pl_match.group("list_id")
                canonical = f"https://www.youtube.com/playlist?list={list_id}"
                return MediaType.PLAYLIST, list_id, canonical

        # 3. Check Channel URLs (@handle, /channel/..., /c/..., /user/...)
        ch = cls.extract_channel(url)
        if ch:
            if ch.startswith("@"):
                canonical = f"https://www.youtube.com/{ch}/videos"
            elif ch.startswith("UC"):
                canonical = f"https://www.youtube.com/channel/{ch}/videos"
            else:
                canonical = f"https://www.youtube.com/c/{ch}/videos"
            return MediaType.PLAYLIST, ch, canonical

        # 4. Check Standard Video / Shorts / Watch / youtu.be / embed / live
        video_id = cls.extract_video_id(url)
        if video_id:
            canonical = f"https://www.youtube.com/watch?v={video_id}"
            return MediaType.VIDEO, video_id, canonical

        # 5. Fallback: check if list parameter exists
        list_id = cls.extract_playlist_id(url)
        if list_id:
            canonical = f"https://www.youtube.com/playlist?list={list_id}"
            return MediaType.PLAYLIST, list_id, canonical

        raise InvalidUrlException(
            f"Could not identify YouTube video, shorts, or playlist in URL: {raw_url}"
        )

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        """Returns True if the URL is a supported YouTube URL, False otherwise."""
        try:
            cls.parse(raw_url)
            return True
        except (InvalidUrlException, Exception):
            return False


class TikTokUrlParser:
    """Parses, sanitizes, and classifies TikTok URLs (videos, photos, user feeds)."""

    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.|m\.|vt\.|vm\.)?tiktok\.com/", re.IGNORECASE
    )
    VIDEO_PATTERN = re.compile(
        r"/video/(?P<id>[0-9]+)", re.IGNORECASE
    )
    PHOTO_PATTERN = re.compile(
        r"/photo/(?P<id>[0-9]+)", re.IGNORECASE
    )
    SHORT_PATTERN = re.compile(
        r"(?:vt|vm)\.tiktok\.com/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", "", ""))

    @classmethod
    def parse(cls, raw_url: str) -> Tuple[MediaType, str, str]:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if "tiktok.com" not in netloc:
            raise InvalidUrlException(f"Not a TikTok URL: {raw_url}")

        path = parsed.path
        # Check Short links (vm.tiktok.com or vt.tiktok.com)
        short_match = cls.SHORT_PATTERN.search(url)
        if short_match:
            sid = short_match.group("id")
            return MediaType.VIDEO, sid, url.split("?")[0]

        # Check Photo slideshow
        photo_match = cls.PHOTO_PATTERN.search(path)
        if photo_match:
            pid = photo_match.group("id")
            return MediaType.POST, pid, f"https://www.tiktok.com/@user/photo/{pid}"

        # Check Video
        vid_match = cls.VIDEO_PATTERN.search(path)
        if vid_match:
            vid = vid_match.group("id")
            return MediaType.VIDEO, vid, f"https://www.tiktok.com/@user/video/{vid}"

        # Fallback for general TikTok link
        slug = [p for p in path.split("/") if p]
        shortcode = slug[-1] if slug else "tiktok_media"
        return MediaType.VIDEO, shortcode, url.split("?")[0]

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        try:
            cls.parse(raw_url)
            return True
        except Exception:
            return False


class TwitterUrlParser:
    """Parses and classifies Twitter / X video and media URLs."""

    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.|mobile\.)?(twitter\.com|x\.com)/", re.IGNORECASE
    )
    STATUS_PATTERN = re.compile(
        r"/(?:[^/]+/status|i/status)/(?P<id>[0-9]+)", re.IGNORECASE
    )

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    @classmethod
    def parse(cls, raw_url: str) -> Tuple[MediaType, str, str]:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if not any(d in netloc for d in ["twitter.com", "x.com"]):
            raise InvalidUrlException(f"Not a Twitter/X URL: {raw_url}")

        match = cls.STATUS_PATTERN.search(parsed.path)
        if match:
            status_id = match.group("id")
            canonical = f"https://x.com/i/status/{status_id}"
            return MediaType.VIDEO, status_id, canonical

        raise InvalidUrlException(f"Could not extract Twitter status ID from URL: {raw_url}")

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        try:
            cls.parse(raw_url)
            return True
        except Exception:
            return False


class RedditUrlParser:
    """Parses and classifies Reddit video and media URLs."""

    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.|old\.|v\.)?(reddit\.com|redd\.it)/", re.IGNORECASE
    )
    V_REDDIT_PATTERN = re.compile(
        r"v\.redd\.it/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )
    COMMENT_PATTERN = re.compile(
        r"/comments/(?P<id>[A-Za-z0-9]+)", re.IGNORECASE
    )
    SHORT_PATTERN = re.compile(
        r"redd\.it/(?P<id>[A-Za-z0-9]+)", re.IGNORECASE
    )

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    @classmethod
    def parse(cls, raw_url: str) -> Tuple[MediaType, str, str]:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if not any(d in netloc for d in ["reddit.com", "redd.it"]):
            raise InvalidUrlException(f"Not a Reddit URL: {raw_url}")

        v_match = cls.V_REDDIT_PATTERN.search(url)
        if v_match:
            vid = v_match.group("id")
            return MediaType.VIDEO, vid, f"https://v.redd.it/{vid}"

        c_match = cls.COMMENT_PATTERN.search(parsed.path)
        if c_match:
            cid = c_match.group("id")
            return MediaType.VIDEO, cid, cls.sanitize_url(url)

        s_match = cls.SHORT_PATTERN.search(url)
        if s_match:
            sid = s_match.group("id")
            return MediaType.VIDEO, sid, f"https://redd.it/{sid}"

        slug = [p for p in parsed.path.split("/") if p]
        code = slug[-1] if slug else "reddit_post"
        return MediaType.VIDEO, code, cls.sanitize_url(url)

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        try:
            cls.parse(raw_url)
            return True
        except Exception:
            return False


class FacebookUrlParser:
    """Parses and classifies Facebook Reels and Watch URLs."""

    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.|m\.|web\.)?(facebook\.com|fb\.watch|fb\.com)/", re.IGNORECASE
    )
    REEL_PATTERN = re.compile(
        r"/reel/(?P<id>[0-9]+)", re.IGNORECASE
    )
    WATCH_PATTERN = re.compile(
        r"/(?:watch|videos)/.*[?&]v=(?P<id>[0-9]+)", re.IGNORECASE
    )
    FB_WATCH_PATTERN = re.compile(
        r"fb\.watch/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    @classmethod
    def parse(cls, raw_url: str) -> Tuple[MediaType, str, str]:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if not any(d in netloc for d in ["facebook.com", "fb.watch", "fb.com"]):
            raise InvalidUrlException(f"Not a Facebook URL: {raw_url}")

        r_match = cls.REEL_PATTERN.search(parsed.path)
        if r_match:
            rid = r_match.group("id")
            return MediaType.REEL, rid, f"https://www.facebook.com/reel/{rid}"

        fw_match = cls.FB_WATCH_PATTERN.search(url)
        if fw_match:
            fid = fw_match.group("id")
            return MediaType.VIDEO, fid, f"https://fb.watch/{fid}"

        w_match = cls.WATCH_PATTERN.search(url)
        if w_match:
            wid = w_match.group("id")
            return MediaType.VIDEO, wid, f"https://www.facebook.com/watch/?v={wid}"

        slug = [p for p in parsed.path.split("/") if p]
        code = slug[-1] if slug else "fb_video"
        return MediaType.VIDEO, code, url.split("?")[0]

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        try:
            cls.parse(raw_url)
            return True
        except Exception:
            return False


class PinterestUrlParser:
    """Parses and classifies Pinterest pin URLs."""

    DOMAIN_PATTERN = re.compile(
        r"^(https?://)?(www\.|[a-z]{2}\.)?(pinterest\.[a-z.]+|pin\.it)/", re.IGNORECASE
    )
    PIN_PATTERN = re.compile(
        r"/pin/(?P<id>[0-9]+)", re.IGNORECASE
    )
    PIN_IT_PATTERN = re.compile(
        r"pin\.it/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE
    )

    @classmethod
    def parse(cls, raw_url: str) -> Tuple[MediaType, str, str]:
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")
        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if not ("pinterest." in netloc or "pin.it" in netloc):
            raise InvalidUrlException(f"Not a Pinterest URL: {raw_url}")

        p_match = cls.PIN_PATTERN.search(parsed.path)
        if p_match:
            pid = p_match.group("id")
            return MediaType.VIDEO, pid, f"https://www.pinterest.com/pin/{pid}/"

        it_match = cls.PIN_IT_PATTERN.search(url)
        if it_match:
            iid = it_match.group("id")
            return MediaType.VIDEO, iid, f"https://pin.it/{iid}"

        slug = [p for p in parsed.path.split("/") if p]
        code = slug[-1] if slug else "pinterest_pin"
        return MediaType.VIDEO, code, url.split("?")[0]

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        try:
            cls.parse(raw_url)
            return True
        except Exception:
            return False


class MediaUrlParser:
    """URL parser and router supporting Instagram, YouTube, and extended multi-platform media."""

    KNOWN_EXTENDED_DOMAINS = [
        "vimeo.com",
        "dailymotion.com",
        "bilibili.com",
        "twitch.tv",
        "soundcloud.com",
        "bandcamp.com",
        "rumble.com",
        "threads.net",
        "snapchat.com",
        "vk.com",
    ]

    @classmethod
    def detect_platform(cls, raw_url: str, extended: bool = False) -> Platform:
        if not raw_url or not raw_url.strip():
            return Platform.UNKNOWN

        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if any(netloc == d or netloc.endswith("." + d) for d in ["instagram.com", "instagr.am"]):
                return Platform.INSTAGRAM
            if any(netloc == d or netloc.endswith("." + d) for d in ["youtube.com", "youtu.be"]):
                return Platform.YOUTUBE

            if extended:
                if any(netloc == d or netloc.endswith("." + d) for d in ["tiktok.com", "vt.tiktok.com", "vm.tiktok.com"]):
                    return Platform.TIKTOK
                if any(netloc == d or netloc.endswith("." + d) for d in ["twitter.com", "x.com", "t.co"]):
                    return Platform.TWITTER
                if any(netloc == d or netloc.endswith("." + d) for d in ["reddit.com", "redd.it", "v.redd.it"]):
                    return Platform.REDDIT
                if any(netloc == d or netloc.endswith("." + d) for d in ["facebook.com", "fb.watch", "fb.com"]):
                    return Platform.FACEBOOK
                if "pinterest." in netloc or "pin.it" in netloc:
                    return Platform.PINTEREST
                if "twitch.tv" in netloc:
                    return Platform.TWITCH
                if "soundcloud.com" in netloc:
                    return Platform.SOUNDCLOUD
                if any(netloc == d or netloc.endswith("." + d) for d in cls.KNOWN_EXTENDED_DOMAINS):
                    return Platform.UNIVERSAL
        except Exception:
            pass

        return Platform.UNKNOWN

    @classmethod
    def is_valid(cls, raw_url: str, extended: bool = False) -> bool:
        """Returns True if the URL is valid for supported platforms."""
        if not raw_url or not raw_url.strip():
            return False

        if InstagramUrlParser.is_valid(raw_url):
            return True
        if YouTubeUrlParser.is_valid(raw_url):
            return True

        if extended:
            if TikTokUrlParser.is_valid(raw_url):
                return True
            if TwitterUrlParser.is_valid(raw_url):
                return True
            if RedditUrlParser.is_valid(raw_url):
                return True
            if FacebookUrlParser.is_valid(raw_url):
                return True
            if PinterestUrlParser.is_valid(raw_url):
                return True
            plat = cls.detect_platform(raw_url, extended=True)
            if plat in (Platform.TWITCH, Platform.SOUNDCLOUD, Platform.UNIVERSAL):
                return True

        return False

    @classmethod
    def sanitize_url(cls, raw_url: str, extended: bool = False) -> str:
        """Sanitizes URL based on the detected platform."""
        platform = cls.detect_platform(raw_url, extended=extended)
        if platform == Platform.INSTAGRAM:
            return InstagramUrlParser.sanitize_url(raw_url)
        elif platform == Platform.YOUTUBE:
            return YouTubeUrlParser.sanitize_url(raw_url)
        elif extended:
            if platform == Platform.TIKTOK:
                return TikTokUrlParser.sanitize_url(raw_url)
            elif platform == Platform.TWITTER:
                return TwitterUrlParser.sanitize_url(raw_url)
            elif platform == Platform.REDDIT:
                return RedditUrlParser.sanitize_url(raw_url)
            elif platform == Platform.FACEBOOK:
                return FacebookUrlParser.sanitize_url(raw_url)
        return raw_url.strip()

    @classmethod
    def parse(
        cls,
        raw_url: str,
        prefer_playlist: bool = False,
        extended: bool = False,
    ) -> Tuple[Platform, MediaType, str, str]:
        """
        Parses URL detecting the appropriate media platform.
        Returns:
            Tuple of (Platform, MediaType, id_or_shortcode, canonical_url)
        Raises:
            InvalidUrlException if URL is unsupported or malformed.
        """
        if not raw_url or not raw_url.strip():
            raise InvalidUrlException("URL cannot be empty")

        platform = cls.detect_platform(raw_url, extended=extended)
        if platform == Platform.INSTAGRAM:
            media_type, shortcode, canonical = InstagramUrlParser.parse(raw_url)
            return Platform.INSTAGRAM, media_type, shortcode, canonical
        elif platform == Platform.YOUTUBE:
            media_type, shortcode, canonical = YouTubeUrlParser.parse(raw_url, prefer_playlist=prefer_playlist)
            return Platform.YOUTUBE, media_type, shortcode, canonical

        if extended:
            if platform == Platform.TIKTOK:
                media_type, shortcode, canonical = TikTokUrlParser.parse(raw_url)
                return Platform.TIKTOK, media_type, shortcode, canonical
            elif platform == Platform.TWITTER:
                media_type, shortcode, canonical = TwitterUrlParser.parse(raw_url)
                return Platform.TWITTER, media_type, shortcode, canonical
            elif platform == Platform.REDDIT:
                media_type, shortcode, canonical = RedditUrlParser.parse(raw_url)
                return Platform.REDDIT, media_type, shortcode, canonical
            elif platform == Platform.FACEBOOK:
                media_type, shortcode, canonical = FacebookUrlParser.parse(raw_url)
                return Platform.FACEBOOK, media_type, shortcode, canonical
            elif platform == Platform.PINTEREST:
                media_type, shortcode, canonical = PinterestUrlParser.parse(raw_url)
                return Platform.PINTEREST, media_type, shortcode, canonical
            elif platform in (Platform.TWITCH, Platform.SOUNDCLOUD, Platform.UNIVERSAL):
                clean = raw_url.strip()
                parsed = urlparse(clean if "://" in clean else "https://" + clean)
                slug = [p for p in parsed.path.split("/") if p]
                sc = slug[-1] if slug else "media"
                return platform, MediaType.VIDEO, sc, clean

        raise InvalidUrlException(
            f"Unsupported media URL. Please provide an Instagram or YouTube link: {raw_url}"
        )


class UniversalMediaUrlParser:
    """Universal multi-platform URL parser supporting all platforms by default."""

    @classmethod
    def detect_platform(cls, raw_url: str) -> Platform:
        return MediaUrlParser.detect_platform(raw_url, extended=True)

    @classmethod
    def is_valid(cls, raw_url: str) -> bool:
        return MediaUrlParser.is_valid(raw_url, extended=True)

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        return MediaUrlParser.sanitize_url(raw_url, extended=True)

    @classmethod
    def parse(cls, raw_url: str, prefer_playlist: bool = False) -> Tuple[Platform, MediaType, str, str]:
        return MediaUrlParser.parse(raw_url, prefer_playlist=prefer_playlist, extended=True)


UniversalUrlParser = UniversalMediaUrlParser
