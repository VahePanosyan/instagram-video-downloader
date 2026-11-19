"""Unit tests for YouTube URL parsing and validation (Videos, Shorts, Playlists, Live)."""

import pytest
from src.domain.url_parser import YouTubeUrlParser, MediaUrlParser
from src.domain.models import MediaType, Platform
from src.domain.exceptions import InvalidUrlException


def test_parse_youtube_standard_watch_urls():
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&feature=shared",
        "https://www.youtube.com/watch?feature=youtu.be&v=dQw4w9WgXcQ",
    ]
    for url in test_urls:
        media_type, video_id, canonical = YouTubeUrlParser.parse(url)
        assert media_type == MediaType.VIDEO
        assert video_id == "dQw4w9WgXcQ"
        assert canonical == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert YouTubeUrlParser.is_valid(url)


def test_parse_youtube_shortened_urls():
    test_urls = [
        "https://youtu.be/dQw4w9WgXcQ",
        "http://youtu.be/dQw4w9WgXcQ",
        "https://www.youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=15",
    ]
    for url in test_urls:
        media_type, video_id, canonical = YouTubeUrlParser.parse(url)
        assert media_type == MediaType.VIDEO
        assert video_id == "dQw4w9WgXcQ"
        assert canonical == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert YouTubeUrlParser.is_valid(url)


def test_parse_youtube_shorts_urls():
    test_urls = [
        "https://www.youtube.com/shorts/3fDkJ2hZ91A",
        "https://youtube.com/shorts/3fDkJ2hZ91A",
        "https://www.youtube.com/shorts/3fDkJ2hZ91A?feature=share",
        "http://m.youtube.com/shorts/3fDkJ2hZ91A/",
    ]
    for url in test_urls:
        media_type, video_id, canonical = YouTubeUrlParser.parse(url)
        assert media_type == MediaType.SHORT
        assert video_id == "3fDkJ2hZ91A"
        assert canonical == "https://www.youtube.com/shorts/3fDkJ2hZ91A"
        assert YouTubeUrlParser.is_valid(url)


def test_parse_youtube_playlist_urls():
    test_urls = [
        "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
        "https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
        "https://music.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
        "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf&si=xyz123",
    ]
    for url in test_urls:
        media_type, list_id, canonical = YouTubeUrlParser.parse(url)
        assert media_type == MediaType.PLAYLIST
        assert list_id == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        assert canonical == "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        assert YouTubeUrlParser.is_valid(url)
        assert YouTubeUrlParser.is_playlist(url)


def test_parse_youtube_embed_and_live_urls():
    # Embed
    embed_url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
    media_type, vid, canonical = YouTubeUrlParser.parse(embed_url)
    assert media_type == MediaType.VIDEO
    assert vid == "dQw4w9WgXcQ"
    assert canonical == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    # Live
    live_url = "https://www.youtube.com/live/dQw4w9WgXcQ?feature=share"
    m_type, l_id, l_canon = YouTubeUrlParser.parse(live_url)
    assert m_type == MediaType.VIDEO
    assert l_id == "dQw4w9WgXcQ"
    assert l_canon == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_youtube_extract_helpers():
    url_video = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert YouTubeUrlParser.extract_video_id(url_video) == "dQw4w9WgXcQ"
    assert YouTubeUrlParser.extract_playlist_id(url_video) == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    url_pl_only = "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert YouTubeUrlParser.extract_video_id(url_pl_only) is None
    assert YouTubeUrlParser.extract_playlist_id(url_pl_only) == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert YouTubeUrlParser.is_playlist(url_pl_only) is True


def test_parse_youtube_invalid_urls():
    invalid_urls = [
        "",
        "   ",
        "https://www.instagram.com/reel/C2-7XYZ1234/",
        "https://vimeo.com/123456",
        "https://www.tiktok.com/@user/video/12345",
        "https://youtube.com/not_a_video_or_channel",
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
        "not a url at all",
    ]
    for url in invalid_urls:
        assert not YouTubeUrlParser.is_valid(url)
        with pytest.raises(InvalidUrlException):
            YouTubeUrlParser.parse(url)


def test_media_url_parser_universal():
    # Instagram detection
    ig_url = "https://www.instagram.com/reel/C2-7XYZ1234/?igsh=123"
    assert MediaUrlParser.detect_platform(ig_url) == Platform.INSTAGRAM
    assert MediaUrlParser.is_valid(ig_url)
    p, m, sc, can = MediaUrlParser.parse(ig_url)
    assert p == Platform.INSTAGRAM
    assert m == MediaType.REEL
    assert sc == "C2-7XYZ1234"
    assert can == "https://www.instagram.com/reel/C2-7XYZ1234/"

    # YouTube detection
    yt_url = "https://youtu.be/dQw4w9WgXcQ?t=10"
    assert MediaUrlParser.detect_platform(yt_url) == Platform.YOUTUBE
    assert MediaUrlParser.is_valid(yt_url)
    p_yt, m_yt, id_yt, can_yt = MediaUrlParser.parse(yt_url)
    assert p_yt == Platform.YOUTUBE
    assert m_yt == MediaType.VIDEO
    assert id_yt == "dQw4w9WgXcQ"
    assert can_yt == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    # Unsupported
    invalid_url = "https://twitter.com/status/12345"
    assert MediaUrlParser.detect_platform(invalid_url) == Platform.UNKNOWN
    assert not MediaUrlParser.is_valid(invalid_url)
    with pytest.raises(InvalidUrlException):
        MediaUrlParser.parse(invalid_url)


def test_parse_youtube_channel_urls():
    channel_urls = [
        ("https://www.youtube.com/@mkbhd", "@mkbhd", "https://www.youtube.com/@mkbhd/videos"),
        ("https://www.youtube.com/@mkbhd/videos", "@mkbhd", "https://www.youtube.com/@mkbhd/videos"),
        ("https://www.youtube.com/@mkbhd/shorts", "@mkbhd", "https://www.youtube.com/@mkbhd/videos"),
        ("https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ", "UCBJycsmduvYEL83R_U4JriQ", "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ/videos"),
        ("https://www.youtube.com/c/mkbhd", "mkbhd", "https://www.youtube.com/c/mkbhd/videos"),
        ("https://www.youtube.com/user/mkbhd", "mkbhd", "https://www.youtube.com/c/mkbhd/videos"),
    ]
    for url, expected_id, expected_can in channel_urls:
        assert YouTubeUrlParser.is_valid(url) is True
        assert YouTubeUrlParser.is_playlist(url) is True
        media_type, shortcode, canonical = YouTubeUrlParser.parse(url)
        assert media_type == MediaType.PLAYLIST
        assert shortcode == expected_id
        assert canonical == expected_can


def test_parse_youtube_watch_with_playlist_and_prefer_playlist():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert YouTubeUrlParser.extract_video_id(url) == "dQw4w9WgXcQ"
    assert YouTubeUrlParser.extract_playlist_id(url) == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert YouTubeUrlParser.is_playlist(url, include_watch_with_list=True) is True
    assert YouTubeUrlParser.is_playlist(url, include_watch_with_list=False) is False

    # Default parse treats as video
    m_type, sc, canon = YouTubeUrlParser.parse(url, prefer_playlist=False)
    assert m_type == MediaType.VIDEO
    assert sc == "dQw4w9WgXcQ"
    assert canon == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    # Prefer playlist treats as playlist
    m_type_pl, sc_pl, canon_pl = YouTubeUrlParser.parse(url, prefer_playlist=True)
    assert m_type_pl == MediaType.PLAYLIST
    assert sc_pl == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert canon_pl == "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"


def test_media_url_parser_rejects_domain_spoofing():
    spoofed = [
        "https://evil.com?param=youtube.com",
        "https://evil.com?param=instagram.com",
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
        "https://fakeinstagram.com/reel/123",
    ]
    for url in spoofed:
        assert MediaUrlParser.detect_platform(url) == Platform.UNKNOWN
        assert MediaUrlParser.is_valid(url) is False
        with pytest.raises(InvalidUrlException):
            MediaUrlParser.parse(url)
