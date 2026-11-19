"""Tests for adapters: JsonSettingsRepository, JsonHistoryRepository, FFmpegAdapter, YtDlpAdapter."""

import threading
from src.adapters.json_repository import JsonSettingsRepository, JsonHistoryRepository
from src.adapters.ffmpeg_adapter import FFmpegAdapter
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.domain.models import (
    QualityOption,
    DownloadHistoryItem,
    DownloadRequest,
    MediaItem,
)


def test_json_settings_repository(tmp_path):
    settings_file = tmp_path / "settings.json"
    repo = JsonSettingsRepository(file_path=str(settings_file))

    # Initial load returns default
    s = repo.load()
    assert s.concurrent_downloads == 3

    # Save modified
    s.concurrent_downloads = 5
    s.proxy = "http://127.0.0.1:8080"
    repo.save(s)

    # Reload from file
    loaded = repo.load()
    assert loaded.concurrent_downloads == 5
    assert loaded.proxy == "http://127.0.0.1:8080"


def test_json_history_repository(tmp_path):
    history_file = tmp_path / "history.json"
    repo = JsonHistoryRepository(file_path=str(history_file))

    assert repo.get_all() == []

    item1 = DownloadHistoryItem(
        id="h1", url="url1", title="Title 1", author="Author 1",
        file_path="/path/1.mp4", file_size_bytes=1000, quality="best", downloaded_at="2026-11-01T01:00:00"
    )
    item2 = DownloadHistoryItem(
        id="h2", url="url2", title="Title 2", author="Author 2",
        file_path="/path/2.mp4", file_size_bytes=2000, quality="1080p", downloaded_at="2026-11-01T02:00:00"
    )

    repo.add(item1)
    repo.add(item2)

    items = repo.get_all()
    assert len(items) == 2
    # Verify descending sort by date
    assert items[0].id == "h2"
    assert items[1].id == "h1"

    # Remove item
    assert repo.remove("h1") is True
    assert len(repo.get_all()) == 1

    # Clear
    repo.clear()
    assert repo.get_all() == []


def test_ffmpeg_adapter_availability():
    adapter = FFmpegAdapter()
    # Since ffmpeg is installed on this system, is_available should be True
    assert adapter.is_available is True
    assert adapter.get_ffmpeg_path() is not None


def test_ytdlp_adapter_filename_sanitization():
    adapter = YtDlpAdapter()
    sanitized = adapter._sanitize_filename_component('Bad: Name / With * Weird? "Chars" <And> | Pipes')
    assert ":" not in sanitized
    assert "/" not in sanitized
    assert "*" not in sanitized
    assert "?" not in sanitized
    assert '"' not in sanitized
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert "|" not in sanitized


def test_ytdlp_adapter_format_selector():
    adapter = YtDlpAdapter()

    # Best
    fmt, pp = adapter._determine_format(QualityOption.BEST)
    assert "bestvideo" in fmt
    assert len(pp) == 0

    # 1080p
    fmt, pp = adapter._determine_format(QualityOption.Q_1080P)
    assert "1080" in fmt
    assert len(pp) == 0

    # MP3
    fmt, pp = adapter._determine_format(QualityOption.AUDIO_MP3)
    assert "bestaudio" in fmt
    assert len(pp) == 1
    assert pp[0]["preferredcodec"] == "mp3"

    # M4A
    fmt, pp = adapter._determine_format(QualityOption.AUDIO_M4A)
    assert "bestaudio" in fmt
    assert len(pp) == 1
    assert pp[0]["preferredcodec"] == "m4a"


def test_json_history_thread_safety_concurrent_writes(tmp_path):
    history_file = tmp_path / "concurrent_history.json"
    repo = JsonHistoryRepository(file_path=str(history_file))

    errors = []

    def worker(i: int):
        try:
            repo.add(DownloadHistoryItem(
                id=f"id_{i}",
                url=f"https://instagram.com/p/{i}/",
                title=f"Video Title {i}",
                author=f"user_{i}",
                file_path=f"/path/{i}.mp4",
                file_size_bytes=1000 + i,
                quality="best",
                downloaded_at="2026-11-01T00:00:00",
            ))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    all_items = repo.get_all()
    assert len(all_items) == 25


def test_ytdlp_filename_template_title_and_tokens():
    adapter = YtDlpAdapter()
    req = DownloadRequest(
        url="https://instagram.com/reel/123/",
        media_item=MediaItem(
            url="https://instagram.com/reel/123/",
            shortcode="C123abc",
            author="super_creator",
            title="A Beautiful Sunset in Rome",
            upload_date="20261101",
        ),
        filename_template="{author}_{title}",
    )

    author = adapter._sanitize_filename_component(req.media_item.author)
    shortcode = adapter._sanitize_filename_component(req.media_item.shortcode)
    title = adapter._sanitize_filename_component(req.media_item.title)
    upload_date = adapter._sanitize_filename_component(req.media_item.upload_date)

    template = req.filename_template
    prefix = (
        template.replace("{author}", author)
        .replace("{shortcode}", shortcode)
        .replace("{title}", title)
        .replace("{id}", shortcode)
        .replace("{date}", upload_date)
    )
    prefix = adapter._sanitize_filename_component(prefix)

    assert "{title}" not in prefix
    assert prefix == "super_creator_A_Beautiful_Sunset_in_Rome"
