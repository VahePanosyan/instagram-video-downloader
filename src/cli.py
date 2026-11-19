"""Command-line interface (CLI) for Instagram Video Downloader."""

import sys
import argparse
import threading
from pathlib import Path
from .domain.models import QualityOption, DownloadRequest, DownloadProgress, MediaType, Platform, enum_value
from .domain.url_parser import MediaUrlParser, YouTubeUrlParser
from .domain.exceptions import DownloaderException
from .adapters.yt_dlp_adapter import YtDlpAdapter
from .adapters.json_repository import JsonSettingsRepository, JsonHistoryRepository
from .use_cases.extract_metadata import ExtractMetadataUseCase
from .use_cases.download_media import DownloadMediaUseCase
from .use_cases.batch_downloader import BatchDownloaderUseCase
from .use_cases.manage_history import ManageHistoryUseCase
from .use_cases.manage_settings import ManageSettingsUseCase


def print_progress(p: DownloadProgress):
    bar_width = 30
    filled = int(p.percent / 100 * bar_width)
    bar = "=" * filled + "-" * (bar_width - filled)
    sys.stdout.write(f"\r[{bar}] {p.percent:.1f}% | {p.speed_str} | ETA: {p.eta_str}    ")
    sys.stdout.flush()


def run_cli():
    # Ensure stdout/stderr handles UTF-8 on Windows
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="media-downloader",
        description="High-performance Instagram & YouTube Video, Shorts, Reel, Audio & Playlist Downloader",
    )
    parser.add_argument("url", nargs="?", help="Instagram or YouTube URL to download")
    parser.add_argument("-b", "--batch", help="Path to text file containing URLs (one per line)")
    parser.add_argument(
        "-q", "--quality",
        choices=[q.value for q in QualityOption],
        default=QualityOption.BEST.value,
        help="Media quality / format (default: best)",
    )
    parser.add_argument("-o", "--output", help="Directory to save downloaded files")
    parser.add_argument("-c", "--concurrency", type=int, default=3, help="Max concurrent downloads for batch mode")
    parser.add_argument("--playlist", action="store_true", help="Download all items if URL is a YouTube playlist")
    parser.add_argument("--cookies", help="Path to cookies.txt file for private content/stories/bot verification")
    parser.add_argument("--proxy", help="Proxy URL (e.g. http://127.0.0.1:8080)")
    parser.add_argument("--history", action="store_true", help="Display download history")
    parser.add_argument("--clear-history", action="store_true", help="Clear download history")
    parser.add_argument("--info-only", action="store_true", help="Inspect and display metadata only without downloading")

    args = parser.parse_args()

    adapter = YtDlpAdapter()
    settings_repo = JsonSettingsRepository()
    history_repo = JsonHistoryRepository()
    settings_uc = ManageSettingsUseCase(settings_repo)
    history_uc = ManageHistoryUseCase(history_repo)
    meta_uc = ExtractMetadataUseCase(adapter)
    download_uc = DownloadMediaUseCase(adapter, history_repo)

    settings = settings_uc.get_settings()
    if args.output:
        settings.download_dir = str(Path(args.output).resolve())
    if args.concurrency:
        settings.concurrent_downloads = args.concurrency
    if args.cookies:
        settings.cookies_file = args.cookies
    if args.proxy:
        settings.proxy = args.proxy

    # Handle History
    if args.history:
        items = history_uc.get_history()
        if not items:
            print("No downloads recorded in history.")
            return 0
        print(f"\n--- Download History ({len(items)} items) ---")
        for it in items:
            plat_badge = f"[{it.platform.upper()}]" if hasattr(it, "platform") and it.platform else "[MEDIA]"
            print(f"[{it.downloaded_at[:16]}] {plat_badge} {it.title[:40]} | @{it.author} | {it.formatted_size}")
            print(f"  Path: {it.file_path}")
        return 0

    if args.clear_history:
        history_uc.clear_history()
        print("Download history cleared.")
        return 0

    # Handle Batch File
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"Error: Batch file not found: {args.batch}", file=sys.stderr)
            return 1

        with open(batch_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        quality = QualityOption.from_value(args.quality)
        batch_uc = BatchDownloaderUseCase(adapter, meta_uc, history_repo)
        added = batch_uc.add_urls(lines, settings, quality, expand_playlists=args.playlist)
        if not added:
            print("No valid Instagram or YouTube URLs found in batch file.")
            return 0

        print(f"Queued {len(added)} valid URLs for batch download...")

        done_ev = threading.Event()
        batch_uc.on_batch_finished = lambda: done_ev.set()
        batch_uc.on_item_updated = lambda req: print(f"\n[{enum_value(req.status).upper()}] {req.url}")
        batch_uc.on_item_progress = lambda req, prog: print_progress(prog)
        batch_uc.start(settings)

        done_ev.wait()
        print("\n\nAll batch downloads completed.")
        return 0

    # Handle Single URL
    if args.url:
        target_url = args.url.strip()
        if not MediaUrlParser.is_valid(target_url):
            print(f"Error: '{target_url}' is not a valid Instagram or YouTube URL.", file=sys.stderr)
            return 1

        platform = MediaUrlParser.detect_platform(target_url)
        plat_name = "YouTube" if platform == Platform.YOUTUBE else "Instagram"
        print(f"Connecting to {plat_name}...")
        try:
            item = meta_uc.execute(target_url, settings=settings)
            print(f"Title:    {item.display_title}")
            creator_label = "Channel" if item.platform == Platform.YOUTUBE else "Creator"
            print(f"{creator_label}:  {item.author}")
            print(f"Duration: {item.formatted_duration}")
            print(f"Type:     {enum_value(item.media_type).upper()}")
            if item.is_playlist:
                print(f"Playlist: {len(item.playlist_urls)} videos found")

            if args.info_only:
                return 0

            quality = QualityOption.from_value(args.quality)

            # If it's a playlist or user passed --playlist
            is_playlist_req = args.playlist or item.is_playlist or item.media_type == MediaType.PLAYLIST
            pl_id = YouTubeUrlParser.extract_playlist_id(target_url) if item.platform == Platform.YOUTUBE else None

            if (args.playlist and pl_id and not item.is_playlist):
                try:
                    pl_url = f"https://www.youtube.com/playlist?list={pl_id}"
                    item = meta_uc.execute(pl_url, settings=settings)
                    is_playlist_req = True
                except Exception:
                    pass

            if is_playlist_req and item.is_playlist and item.playlist_urls:
                batch_uc = BatchDownloaderUseCase(adapter, meta_uc, history_repo)
                added = batch_uc.add_urls(item.playlist_urls, settings, quality)
                print(f"\nQueued {len(added)} videos from playlist for batch download...")
                done_ev = threading.Event()
                batch_uc.on_batch_finished = lambda: done_ev.set()
                batch_uc.on_item_updated = lambda req: print(f"\n[{enum_value(req.status).upper()}] {req.url}")
                batch_uc.on_item_progress = lambda req, prog: print_progress(prog)
                batch_uc.start(settings)
                done_ev.wait()
                print("\n\nAll playlist downloads completed.")
                return 0

            req = DownloadRequest(
                url=item.url,
                media_item=item,
                quality=quality,
                output_dir=settings.download_dir,
            )

            print(f"\nStarting download ({enum_value(quality)})...")
            saved_path = download_uc.execute(
                request=req,
                settings=settings,
                progress_callback=print_progress,
            )
            print(f"\n\nSUCCESS! File saved to:\n{saved_path}")
            return 0

        except DownloaderException as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"\nUnexpected error: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
