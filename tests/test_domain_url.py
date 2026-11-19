"""Unit tests for Instagram URL parsing and validation."""

import pytest
from src.domain.url_parser import InstagramUrlParser
from src.domain.models import MediaType
from src.domain.exceptions import InvalidUrlException


def test_parse_valid_reel_urls():
    test_urls = [
        "https://www.instagram.com/reel/C2-7XYZ1234/",
        "https://instagram.com/reel/C2-7XYZ1234",
        "http://www.instagram.com/reels/C2-7XYZ1234/",
        "https://www.instagram.com/reel/C2-7XYZ1234/?igsh=MWZzZmpuY3RlbG5raw==",
        "https://www.instagram.com/share/reel/C2-7XYZ1234/",
        "https://www.instagram.com/share/r/C2-7XYZ1234/",
    ]
    for url in test_urls:
        media_type, shortcode, canonical = InstagramUrlParser.parse(url)
        assert media_type == MediaType.REEL
        assert shortcode == "C2-7XYZ1234"
        assert canonical == "https://www.instagram.com/reel/C2-7XYZ1234/"


def test_parse_valid_post_urls():
    test_urls = [
        "https://www.instagram.com/p/B123_abcXYZ/",
        "https://instagram.com/p/B123_abcXYZ",
        "https://instagr.am/p/B123_abcXYZ/",
        "https://www.instagram.com/p/B123_abcXYZ/?utm_source=ig_web_copy_link",
        "https://www.instagram.com/share/p/B123_abcXYZ/",
    ]
    for url in test_urls:
        media_type, shortcode, canonical = InstagramUrlParser.parse(url)
        assert media_type == MediaType.POST
        assert shortcode == "B123_abcXYZ"
        assert canonical == "https://www.instagram.com/p/B123_abcXYZ/"


def test_parse_valid_tv_urls():
    url = "https://www.instagram.com/tv/CBxyz789_TV/"
    media_type, shortcode, canonical = InstagramUrlParser.parse(url)
    assert media_type == MediaType.TV
    assert shortcode == "CBxyz789_TV"
    assert canonical == "https://www.instagram.com/tv/CBxyz789_TV/"


def test_parse_valid_story_urls():
    # Single story
    url = "https://www.instagram.com/stories/cool_creator/3298712345678901234/?igsh=xyz"
    media_type, shortcode, canonical = InstagramUrlParser.parse(url)
    assert media_type == MediaType.STORY
    assert shortcode == "cool_creator_3298712345678901234"
    assert canonical == "https://www.instagram.com/stories/cool_creator/3298712345678901234/"

    # Highlight story
    url_high = "https://www.instagram.com/stories/highlights/17895692348590123/"
    mtype_h, sc_h, canon_h = InstagramUrlParser.parse(url_high)
    assert mtype_h == MediaType.STORY
    assert sc_h == "highlight_17895692348590123"
    assert canon_h == "https://www.instagram.com/stories/highlights/17895692348590123/"

    # User story tray
    url_user = "https://www.instagram.com/stories/nasa/"
    mtype_u, sc_u, canon_u = InstagramUrlParser.parse(url_user)
    assert mtype_u == MediaType.STORY
    assert sc_u == "nasa_story"
    assert canon_u == "https://www.instagram.com/stories/nasa/"


def test_parse_invalid_urls():
    invalid_urls = [
        "",
        "   ",
        "https://youtube.com/watch?v=123",
        "https://www.tiktok.com/@user/video/123",
        "https://www.instagram.com/some_user_profile/",
        "https://notinstagram.com/reel/1234",
        "random string not a url",
    ]
    for url in invalid_urls:
        assert not InstagramUrlParser.is_valid(url)
        with pytest.raises(InvalidUrlException):
            InstagramUrlParser.parse(url)
