import os
import sys
import time
import threading
import tempfile
import gc

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.models import QualityOption, AppSettings, DownloadRequest, Platform, MediaType
from src.domain.exceptions import (
    DownloaderException,
    NetworkException,
    AuthenticationRequiredException,
    InvalidUrlException,
    ExtractionException,
    DownloadException,
    PostProcessingException,
)
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.adapters.ffmpeg_adapter import FFmpegAdapter
from src.adapters.direct_scraper import DirectInstagramScraper, DirectYouTubeScraper, UniversalDirectScraper
from src.gui.workers import ThumbnailLoaderWorker

# Qt imports for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from src.gui.app import MainWindow
from src.gui.components.url_input import SingleUrlWidget
from src.gui.components.log_panel import EventLogWidget, QtLoggingHandler, LogSignalBridge
import logging


def print_header(title: str):
    print(f"\n{'='*70}\n[CHALLENGE SUITE] {title}\n{'='*70}")


def test_suite_quality_formats():
    print_header("SUITE 1: Quality Formats & Stream Configuration Stress Test")
    adapter = YtDlpAdapter()

    # 1. Test all QualityOption members
    all_options = list(QualityOption)
    print(f"Total QualityOption members: {len(all_options)}")
    assert len(all_options) == 11, f"Expected 11 QualityOption members, got {len(all_options)}"

    for opt in all_options:
        fmt_str, postprocessors = adapter._determine_format(opt)
        assert isinstance(fmt_str, str) and len(fmt_str) > 0, f"Empty format string for {opt}"
        print(f"  ✓ {opt.name} ({opt.value}): format_str={fmt_str[:45]}... postprocessors={len(postprocessors)}")

    # 2. Verify Lossless Audio Codecs
    print("\nVerifying WAV Lossless Configuration:")
    wav_fmt, wav_pp = adapter._determine_format(QualityOption.AUDIO_WAV)
    assert wav_fmt == "bestaudio/best", f"Unexpected format for WAV: {wav_fmt}"
    assert len(wav_pp) == 1, "WAV must specify exactly 1 postprocessor"
    assert wav_pp[0]["key"] == "FFmpegExtractAudio"
    assert wav_pp[0]["preferredcodec"] == "wav"
    assert "preferredquality" not in wav_pp[0], "Lossless WAV must not set lossy bitrate"
    print("  ✓ YtDlpAdapter WAV configured: key=FFmpegExtractAudio, preferredcodec=wav (no lossy compression)")

    print("\nVerifying FLAC Lossless Configuration:")
    flac_fmt, flac_pp = adapter._determine_format(QualityOption.AUDIO_FLAC)
    assert flac_fmt == "bestaudio/best", f"Unexpected format for FLAC: {flac_fmt}"
    assert len(flac_pp) == 1, "FLAC must specify exactly 1 postprocessor"
    assert flac_pp[0]["key"] == "FFmpegExtractAudio"
    assert flac_pp[0]["preferredcodec"] == "flac"
    assert "preferredquality" not in flac_pp[0], "Lossless FLAC must not set lossy bitrate"
    print("  ✓ YtDlpAdapter FLAC configured: key=FFmpegExtractAudio, preferredcodec=flac (no lossy compression)")

    # Test FFmpegAdapter codec arguments for WAV and FLAC
    ffmpeg_adapter = FFmpegAdapter(ffmpeg_path="ffmpeg_mock")
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_in = Path(tmp_dir) / "input.mp4"
        fake_in.write_bytes(b"dummy_video_bytes")
        fake_wav_out = Path(tmp_dir) / "output.wav"
        fake_flac_out = Path(tmp_dir) / "output.flac"

        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0)

            # WAV extraction
            ffmpeg_adapter.extract_audio(str(fake_in), str(fake_wav_out), format_type="wav")
            wav_cmd = mock_sub.call_args[0][0]
            assert "-c:a" in wav_cmd and wav_cmd[wav_cmd.index("-c:a") + 1] == "pcm_s16le", f"WAV must use pcm_s16le: {wav_cmd}"
            assert "-b:a" not in wav_cmd, "Lossless PCM WAV must not set bitrate limit"
            print(f"  ✓ FFmpegAdapter WAV command: {' '.join(wav_cmd)}")

            # FLAC extraction
            ffmpeg_adapter.extract_audio(str(fake_in), str(fake_flac_out), format_type="flac")
            flac_cmd = mock_sub.call_args[0][0]
            assert "-c:a" in flac_cmd and flac_cmd[flac_cmd.index("-c:a") + 1] == "flac", f"FLAC must use flac codec: {flac_cmd}"
            assert "-b:a" not in flac_cmd, "Lossless FLAC must not set bitrate limit"
            print(f"  ✓ FFmpegAdapter FLAC command: {' '.join(flac_cmd)}")

    # 3. Verify 4K stream merging and vertical video handling
    print("\nVerifying 4K Stream Merging & Vertical Fallback:")
    fmt_4k, pp_4k = adapter._determine_format(QualityOption.Q_2160P)
    base_opts = adapter._build_base_options()
    assert base_opts["merge_output_format"] == "mp4", f"Expected merge_output_format='mp4', got {base_opts.get('merge_output_format')}"
    assert "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]" in fmt_4k
    assert "bestvideo[height<=2160]+bestaudio" in fmt_4k, "4K must support merging WebM/VP9 video + audio"
    assert "bestvideo[width<=2160]+bestaudio" in fmt_4k, "4K must support vertical video width fallback"
    print("  ✓ 4K format merges disparate audio/video streams into MP4 container:")
    print(f"    {fmt_4k}")

    print("\n[SUITE 1 RESULT]: PASS - All quality formats, lossless codecs, and 4K stream mergers verified.")


def test_suite_network_and_proxy():
    print_header("SUITE 2: Network & Proxy Resilience Stress Test")
    adapter = YtDlpAdapter()

    # 1. Schemeless and Varied Proxy Normalization
    proxy_matrix = [
        ("127.0.0.1:8888", "http://127.0.0.1:8888"),
        ("localhost:8080", "http://localhost:8080"),
        ("192.168.1.100:3128", "http://192.168.1.100:3128"),
        ("http://127.0.0.1:8888", "http://127.0.0.1:8888"),
        ("https://secure-proxy.com:8443", "https://secure-proxy.com:8443"),
        ("socks5://127.0.0.1:1080", "socks5://127.0.0.1:1080"),
        ("socks5h://user:pass@remote.host:1080", "socks5h://user:pass@remote.host:1080"),
        ("socks4://10.0.0.1:1080", "socks4://10.0.0.1:1080"),
    ]
    for raw_proxy, expected in proxy_matrix:
        settings = AppSettings(proxy=raw_proxy)
        opts = adapter._build_base_options(settings)
        assert opts.get("proxy") == expected, f"Failed normalizing '{raw_proxy}': expected '{expected}', got '{opts.get('proxy')}'"
        print(f"  ✓ Proxy normalization: {raw_proxy:>36} -> {expected}")

    # Empty/whitespace proxies
    for empty_proxy in ["", "   ", None]:
        settings = AppSettings(proxy=empty_proxy)
        opts = adapter._build_base_options(settings)
        assert "proxy" not in opts, f"Empty proxy should not set 'proxy' in options: {opts.get('proxy')}"
    print("  ✓ Empty and whitespace proxies correctly omitted from options.")

    # 2. Unreachable Proxy NetworkException Translation (extract_info & download)
    from yt_dlp.utils import DownloadError

    proxy_error_messages = [
        "Unable to connect to proxy 127.0.0.1:8888",
        "Failed to connect to proxy: [WinError 10061] No connection could be made because the target machine actively refused it",
        "ProxyError(Cannot connect to proxy: 502 Bad Gateway)",
        "Connection timed out after 25 seconds while connecting to proxy",
        "HTTP Error 504: Gateway Timeout through proxy",
    ]

    print("\nTesting extract_info exception mapping on unreachable proxy errors:")
    with patch("src.domain.url_parser.MediaUrlParser.parse") as mock_parse:
        mock_parse.return_value = (Platform.INSTAGRAM, MediaType.VIDEO, "testcode", "https://www.instagram.com/reel/testcode/")
        for err_msg in proxy_error_messages:
            with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
                mock_inst = MagicMock()
                mock_inst.__enter__.return_value = mock_inst
                mock_inst.extract_info.side_effect = DownloadError(err_msg)
                mock_ydl_cls.return_value = mock_inst

                try:
                    adapter.extract_info("https://www.instagram.com/reel/testcode/", AppSettings(proxy="127.0.0.1:9999"))
                    assert False, f"Should have raised NetworkException for {err_msg}"
                except NetworkException as ne:
                    print(f"  ✓ Caught NetworkException: {ne}")
                except Exception as other:
                    assert False, f"Unexpected exception type: {type(other)}: {other}"

    print("\nTesting download exception mapping on unreachable proxy errors:")
    with tempfile.TemporaryDirectory() as tmp_dir:
        req = DownloadRequest(
            url="https://www.instagram.com/reel/testcode/",
            output_dir=tmp_dir,
            quality=QualityOption.BEST,
        )
        for err_msg in ["Proxy error connecting to Instagram: Connection refused", "timed out while waiting for proxy"]:
            with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
                mock_inst = MagicMock()
                mock_inst.__enter__.return_value = mock_inst
                mock_inst.extract_info.side_effect = DownloadError(err_msg)
                mock_ydl_cls.return_value = mock_inst

                try:
                    adapter.download(req, settings=AppSettings(proxy="127.0.0.1:9999"))
                    assert False, f"Should have raised NetworkException for {err_msg}"
                except NetworkException as ne:
                    print(f"  ✓ Caught NetworkException on download: {ne}")
                except Exception as other:
                    assert False, f"Unexpected exception type: {type(other)}: {other}"

    # 3. Direct Scrapers & Thumbnail Worker Resilience
    print("\nTesting Scrapers and Workers with unreachable proxy:")
    scraper = DirectInstagramScraper(proxy="127.0.0.1:1")
    assert scraper._proxy == "127.0.0.1:1"
    res = scraper.fetch_oembed("https://www.instagram.com/p/test/")
    assert res is None, "fetch_oembed should return None on unreachable proxy"
    preview = scraper.quick_preview("https://www.instagram.com/p/test/")
    assert preview is not None and preview.shortcode == "test", "quick_preview should generate fallback MediaItem"
    print("  ✓ DirectInstagramScraper handled unreachable proxy gracefully (returned fallback MediaItem without crashing).")

    # ThumbnailLoaderWorker test
    worker = ThumbnailLoaderWorker("http://127.0.0.1:1/thumb.jpg", proxy="127.0.0.1:1")
    failed_received = []
    worker.failed.connect(lambda: failed_received.append(True))
    worker.run()
    assert len(failed_received) == 1, "ThumbnailLoaderWorker must emit failed signal on network error"
    print("  ✓ ThumbnailLoaderWorker gracefully emitted failed signal without crashing.")

    print("\n[SUITE 2 RESULT]: PASS - Network and proxy resilience fully verified.")


def test_suite_cookies_handling():
    print_header("SUITE 3: Cookies Handling Stress Test")
    adapter = YtDlpAdapter()

    # 1. Test browser cookies extraction injection
    browsers = ["Chrome", "firefox", "EDGE", "Brave", "Opera", "Vivaldi", "Chromium"]
    for b in browsers:
        settings = AppSettings(cookies_browser=b)
        opts = adapter._build_base_options(settings)
        assert opts.get("cookiesfrombrowser") == (b.lower(),), f"Failed for browser {b}: {opts.get('cookiesfrombrowser')}"
        print(f"  ✓ Browser '{b}' correctly injected as cookiesfrombrowser: {opts.get('cookiesfrombrowser')}")

    # Blank browser
    for blank in ["", "   ", None]:
        settings = AppSettings(cookies_browser=blank)
        opts = adapter._build_base_options(settings)
        assert "cookiesfrombrowser" not in opts, "Blank cookies_browser should not set option"
    print("  ✓ Blank cookies_browser cleanly ignored.")

    # 2. Test cookies file handling: existing vs non-existent
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        tf.write(b"# Netscape HTTP Cookie File\n")
        temp_cookie_path = tf.name

    try:
        # Existing file
        settings_exist = AppSettings(cookies_file=temp_cookie_path)
        opts_exist = adapter._build_base_options(settings_exist)
        assert opts_exist.get("cookiefile") == temp_cookie_path
        print(f"  ✓ Existing cookie file verified in options: {temp_cookie_path}")

        # Non-existent file
        non_existent_path = temp_cookie_path + ".non_existent.txt"
        settings_non_exist = AppSettings(cookies_file=non_existent_path)
        opts_non_exist = adapter._build_base_options(settings_non_exist)
        assert "cookiefile" not in opts_non_exist, "Non-existent cookie file must NOT be passed to yt-dlp"
        print(f"  ✓ Non-existent cookie file safely omitted from options.")
    finally:
        if os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)

    # 3. Test cookie error handling to AuthenticationRequiredException
    from yt_dlp.utils import DownloadError

    cookie_errors = [
        "Could not read cookies from Chrome: database is locked",
        "Could not read cookies from Firefox: cookies.sqlite is busy",
        "Invalid cookies file: header does not match Netscape format",
        "Instagram authentication required: please login",
        "This account is private. Please provide cookies.",
    ]
    with patch("src.domain.url_parser.MediaUrlParser.parse") as mock_parse:
        mock_parse.return_value = (Platform.INSTAGRAM, MediaType.VIDEO, "private_code", "https://www.instagram.com/reel/private_code/")
        for err in cookie_errors:
            with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
                mock_inst = MagicMock()
                mock_inst.__enter__.return_value = mock_inst
                mock_inst.extract_info.side_effect = DownloadError(err)
                mock_ydl_cls.return_value = mock_inst

                try:
                    adapter.extract_info("https://www.instagram.com/reel/private_code/")
                    assert False, f"Should have raised AuthenticationRequiredException for: {err}"
                except AuthenticationRequiredException as are:
                    print(f"  ✓ Translated cookie error to AuthenticationRequiredException: {are.message[:60]}...")
                except Exception as ex:
                    assert False, f"Unexpected exception: {type(ex)}: {ex}"

    print("\n[SUITE 3 RESULT]: PASS - Cookies handling and error handling fully verified.")


def test_suite_gui_theme_and_headless():
    print_header("SUITE 4: GUI Theme Switching & Headless Concurrency Stress Test")
    app = QApplication.instance() or QApplication([])

    print("\n1. Initializing MainWindow headlessly...")
    win = MainWindow()
    assert win.tabs.count() == 5, f"Expected 5 tabs, got {win.tabs.count()}"
    assert hasattr(win, "log_panel"), "MainWindow must have log_panel"
    assert hasattr(win, "tab_single"), "MainWindow must have tab_single"

    # Rapid Theme Switching Loop (50 iterations = 100 theme switches)
    print("\n2. Executing rapid theme switching stress loop (50 iterations = 100 toggles)...")
    gc.collect()
    start_time = time.perf_counter()

    for i in range(50):
        # Switch to Light Theme
        win.apply_theme(False)
        assert not win._current_settings.dark_theme
        assert "🌙" in win.header.btn_theme_toggle.text() or "Dark" in win.header.btn_theme_toggle.text()

        # Switch to Dark Theme
        win.apply_theme(True)
        assert win._current_settings.dark_theme
        assert "☀️" in win.header.btn_theme_toggle.text() or "Light" in win.header.btn_theme_toggle.text()

        if (i + 1) % 10 == 0:
            print(f"  ... completed {i + 1}/50 theme toggle cycles")

    elapsed = time.perf_counter() - start_time
    avg_per_switch = (elapsed / 100) * 1000
    print(f"  ✓ 100 theme switches completed in {elapsed:.3f}s ({avg_per_switch:.2f} ms per switch)")
    assert elapsed < 25.0, f"Theme switching took too long: {elapsed}s"

    # Two-tier mode switching in SingleUrlWidget
    print("\n3. Testing two-tier mode switching in SingleUrlWidget...")
    single: SingleUrlWidget = win.tab_single
    assert single.combo_quality.count() == len(QualityOption), "Quality combo box must have all options"

    # Video Mode Check
    single.radio_mode_video.setChecked(True)
    view = single.combo_quality.view()
    for row in range(single.combo_quality.count()):
        opt = single.combo_quality.itemData(row)
        if opt in single.AUDIO_OPTIONS:
            assert view.isRowHidden(row), f"Audio option {opt} should be hidden in Video mode"
        else:
            assert not view.isRowHidden(row), f"Video option {opt} should be visible in Video mode"
    print("  ✓ Video mode correctly hides all 4 audio options and displays all 7 video options")

    # Audio Mode Check
    single.radio_mode_audio.setChecked(True)
    for row in range(single.combo_quality.count()):
        opt = single.combo_quality.itemData(row)
        if opt in single.AUDIO_OPTIONS:
            assert not view.isRowHidden(row), f"Audio option {opt} should be visible in Audio mode"
        else:
            assert view.isRowHidden(row), f"Video option {opt} should be hidden in Audio mode"
    print("  ✓ Audio mode correctly hides all 7 video options and displays all 4 audio options")

    # Check bidirectional quality setting
    single.set_quality(QualityOption.AUDIO_FLAC)
    assert single.get_quality() == QualityOption.AUDIO_FLAC
    assert single.radio_mode_audio.isChecked(), "Setting AUDIO_FLAC must auto-select Audio mode"
    assert "FLAC Audio Track" in single.lbl_format_badge.text()
    print("  ✓ Setting AUDIO_FLAC automatically switches mode to Audio Only and updates format badge")

    single.set_quality(QualityOption.Q_2160P)
    assert single.get_quality() == QualityOption.Q_2160P
    assert single.radio_mode_video.isChecked(), "Setting Q_2160P must auto-select Video mode"
    assert "4K Ultra HD MP4" in single.lbl_format_badge.text()
    print("  ✓ Setting Q_2160P automatically switches mode to Video and updates format badge")

    # 4. Concurrent EventLogWidget stress test across threads
    print("\n4. Stress testing EventLogWidget with 10 concurrent threads emitting 100 logs each (1,000 logs)...")
    log_panel: EventLogWidget = win.log_panel
    log_panel.clear_logs()

    num_threads = 10
    logs_per_thread = 100
    levels = ["INFO", "SUCCESS", "WARNING", "ERROR", "DEBUG"]

    def worker_thread(tid: int):
        for j in range(logs_per_thread):
            lvl = levels[j % len(levels)]
            log_panel.log(lvl, f"Thread-{tid} message {j}: testing concurrent stress")

    threads = [threading.Thread(target=worker_thread, args=(t,)) for t in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Process all queued Qt events
    app.processEvents()

    t_log = time.perf_counter() - t0
    total_logs = len(log_panel._all_entries)
    print(f"  ✓ Ingested {total_logs} log entries concurrently across {num_threads} threads in {t_log:.3f}s")
    assert total_logs == num_threads * logs_per_thread, f"Expected {num_threads * logs_per_thread} logs, got {total_logs}"

    # Verify search and filtering under load
    log_panel.combo_filter.setCurrentText("ERROR")
    app.processEvents()
    error_count = sum(1 for e in log_panel._all_entries if e[1] == "ERROR")
    displayed_text = log_panel.log_view.toPlainText()
    displayed_lines = [line for line in displayed_text.splitlines() if line.strip()]
    print(f"  ✓ Filtered for ERROR: found {error_count} records, log_view displays {len(displayed_lines)} lines")
    assert len(displayed_lines) == error_count

    # Test clearing
    log_panel.clear_logs()
    assert len(log_panel._all_entries) == 0
    assert log_panel.log_view.toPlainText() == ""
    print("  ✓ clear_logs() reset all memory and views cleanly.")

    print("\n[SUITE 4 RESULT]: PASS - GUI theme switching, two-tier mode switching, and concurrent event log verified.")


if __name__ == "__main__":
    t_start = time.perf_counter()
    test_suite_quality_formats()
    test_suite_network_and_proxy()
    test_suite_cookies_handling()
    test_suite_gui_theme_and_headless()
    t_total = time.perf_counter() - t_start

    print(f"\n{'='*70}\nALL 4 CHALLENGE STRESS SUITES PASSED EMPIRICALLY IN {t_total:.2f}s!\n{'='*70}\n")
