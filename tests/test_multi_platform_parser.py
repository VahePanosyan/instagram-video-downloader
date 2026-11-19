"""Tests for multi-platform URL parsing (TikTok, Twitter/X, Reddit, Facebook, Pinterest, and Universal)."""

import pytest
from src.domain.models import Platform, MediaType
from src.domain.url_parser import (
    MediaUrlParser,
    UniversalMediaUrlParser,
    TikTokUrlParser,
    TwitterUrlParser,
    RedditUrlParser,
    FacebookUrlParser,
    PinterestUrlParser,
)
from src.domain.exceptions import InvalidUrlException


def test_tiktok_url_parser():
    url_video = "https://www.tiktok.com/@creator/video/7123456789012345678"
    assert TikTokUrlParser.is_valid(url_video)
    m_type, vid, canonical = TikTokUrlParser.parse(url_video)
    assert m_type == MediaType.VIDEO
    assert vid == "7123456789012345678"
    assert "7123456789012345678" in canonical

    url_short = "https://vm.tiktok.com/ZM8xXYZ12/"
    assert TikTokUrlParser.is_valid(url_short)
    m_type, sid, _ = TikTokUrlParser.parse(url_short)
    assert sid == "ZM8xXYZ12"

    assert not TikTokUrlParser.is_valid("https://example.com/not-tiktok")


def test_twitter_url_parser():
    url_twitter = "https://twitter.com/jack/status/20"
    url_x = "https://x.com/OpenAI/status/1760000000000000000"

    assert TwitterUrlParser.is_valid(url_twitter)
    assert TwitterUrlParser.is_valid(url_x)

    m_type, status_id, canonical = TwitterUrlParser.parse(url_twitter)
    assert m_type == MediaType.VIDEO
    assert status_id == "20"
    assert canonical == "https://x.com/i/status/20"

    _, x_id, _ = TwitterUrlParser.parse(url_x)
    assert x_id == "1760000000000000000"


def test_reddit_url_parser():
    url_post = "https://www.reddit.com/r/funny/comments/123456/hilarious_cat_video/"
    url_v_reddit = "https://v.redd.it/abcdef12345"
    url_short = "https://redd.it/123456"

    assert RedditUrlParser.is_valid(url_post)
    assert RedditUrlParser.is_valid(url_v_reddit)
    assert RedditUrlParser.is_valid(url_short)

    m_type, vid, _ = RedditUrlParser.parse(url_v_reddit)
    assert vid == "abcdef12345"


def test_facebook_url_parser():
    url_reel = "https://www.facebook.com/reel/1029384756"
    url_watch = "https://fb.watch/m1n2o3p4q5/"

    assert FacebookUrlParser.is_valid(url_reel)
    assert FacebookUrlParser.is_valid(url_watch)

    m_type, rid, _ = FacebookUrlParser.parse(url_reel)
    assert rid == "1029384756"


def test_pinterest_url_parser():
    url_pin = "https://www.pinterest.com/pin/123456789012345678/"
    url_pin_it = "https://pin.it/abcXYZ1"

    assert PinterestUrlParser.is_valid(url_pin)
    assert PinterestUrlParser.is_valid(url_pin_it)

    _, pid, _ = PinterestUrlParser.parse(url_pin)
    assert pid == "123456789012345678"


def test_media_url_parser_routing():
    cases = [
        ("https://www.instagram.com/reel/C2-7XYZ1234/", Platform.INSTAGRAM),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", Platform.YOUTUBE),
        ("https://www.tiktok.com/@user/video/7123456789", Platform.TIKTOK),
        ("https://x.com/user/status/123456789", Platform.TWITTER),
        ("https://v.redd.it/987654321", Platform.REDDIT),
        ("https://www.facebook.com/reel/999888777", Platform.FACEBOOK),
        ("https://www.pinterest.com/pin/555444333/", Platform.PINTEREST),
        ("https://vimeo.com/12345678", Platform.UNIVERSAL),
    ]

    for url, expected_plat in cases:
        plat = UniversalMediaUrlParser.detect_platform(url)
        assert plat == expected_plat, f"Failed for {url}: expected {expected_plat}, got {plat}"
        assert UniversalMediaUrlParser.is_valid(url)
        parsed_plat, _, _, _ = UniversalMediaUrlParser.parse(url)
        assert parsed_plat == expected_plat

    # Invalid URL check
    assert not UniversalMediaUrlParser.is_valid("not_a_valid_url")
    assert not UniversalMediaUrlParser.is_valid("https://invalid-domain.com/video")
    with pytest.raises(InvalidUrlException):
        UniversalMediaUrlParser.parse("https://invalid-domain.com/video")
