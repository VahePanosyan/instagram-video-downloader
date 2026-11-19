# Project: Instagram & YouTube Video Downloader Pro

## Architecture
The application follows Hexagonal Architecture (Ports & Adapters) with a clean separation of concerns:
- **Domain Layer (`src/domain/`)**: Pure business logic, value objects, domain models (`QualityOption`, `DownloadRequest`, `MediaItem`, `AppSettings`, `DownloadProgress`), and domain exception hierarchy (`DownloaderException`, `InvalidUrlException`, `ExtractionException`, `DownloadException`, etc.).
- **Ports Layer (`src/ports/`)**: Abstract interfaces (`DownloaderPort`, `MetadataExtractorPort`, `NotifierPort`, `HistoryRepositoryPort`, `SettingsRepositoryPort`).
- **Adapters Layer (`src/adapters/`)**: Concrete implementations of ports (`YtDlpAdapter`, `FFmpegAdapter`, `DirectInstagramScraper`, `DirectYouTubeScraper`, `JsonHistoryRepository`, `JsonSettingsRepository`).
- **Use Cases Layer (`src/use_cases/`)**: Interactors coordinating domain and ports (`DownloadMediaUseCase`, `ExtractMetadataUseCase`, `BatchDownloaderUseCase`, `ManageHistoryUseCase`, `ManageSettingsUseCase`).
- **Presentation Layer (`src/gui/`, `src/cli.py`)**: PySide6 desktop GUI with modular components, dynamic dual-theme styling (`ThemeTokens`, `DarkThemeTokens`, `LightThemeTokens`, `build_stylesheet`), asynchronous worker threads (`QThread`), and CLI entry points.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Audio Extraction MP3 | Extract and encode audio to 320 kbps MP3 | M1 | Survey |
| 2 | Audio Extraction M4A | Extract AAC audio into M4A container | M1 | Survey |
| 3 | Audio Extraction WAV | Extract uncompressed lossless PCM audio to WAV | M1 | Survey |
| 4 | Audio Extraction FLAC | Extract lossless compressed audio to FLAC | M1 | Survey |
| 5 | Video Resolution 4K (2160p) | Select 4K video streams with audio merging | M1 | Survey |
| 6 | Video Resolutions 1080p, 720p, Best | Select 1080p, 720p or Best available MP4 video | M1 | Survey |
| 7 | Output Detection for New Formats | Resolve downloaded target paths for .wav and .flac | M1 | Survey |
| 8 | Proxy Integration | Support HTTP, HTTPS, and SOCKS5 proxies in yt-dlp & urllib | M2 | Survey |
| 9 | Cookies File Support | Pass Netscape cookies.txt to yt-dlp for private/restricted media | M2 | Survey |
| 10 | Browser Cookies Extraction | Extract cookies from Chrome, Firefox, Edge, Brave, Opera | M2 | Survey |
| 11 | Proxy-Aware Thumbnail Loader | Ensure image scraping honors configured proxy | M2 | Survey |
| 12 | Dynamic Dual-Theme System | Dark and Light themes with instant runtime switching | M3 | Survey |
| 13 | Ergonomic Mode & Quality Selectors | Two-tier UI: Video vs Audio mode with dynamic format choices | M3 | Survey |
| 14 | Dynamic Progress & Live Telemetry | Detailed metrics (speed, ETA, size) with stage status badges | M3 | Survey |
| 15 | Enhanced History Panel | History table with search, platform badges, open file/folder | M3 | Survey |
| 16 | Integrated Event Log Panel | Thread-safe color-coded log console with copy/export | M3 | Survey |
| 17 | Exception & Crash Hardening | Robust error messages for network errors, rate limits, private content | M4 | Survey |
| 18 | Pytest Suite Expansion & 100% Pass | Expand tests to verify all formats, proxies, cookies, and GUI | M4 | Survey |
| 19 | Multi-Platform Routing Engine | Dedicated parsers for TikTok, Twitter/X, Reddit, Facebook, Pinterest, and Universal fallback | M5 | Upgrade |
| 20 | Subtitles & Closed Captions | Extract SRT/VTT or embed subtitles into video containers | M5 | Upgrade |
| 21 | Video Section Trimming | Download or slice precise time intervals without quality loss | M5 | Upgrade |
| 22 | Audio & Video Metadata Tagging | Embed ID3 tags, chapter markers, and album cover art into media | M5 | Upgrade |
| 23 | In-App Media Preview Player | Integrated QtMultimedia preview player with controls and external fallback | M5 | Upgrade |
| 24 | Queue Management 2.0 | Pause, resume, reorder, and duplicate link prevention | M5 | Upgrade |
| 25 | Engine Self-Updater & Health | Check yt-dlp version on PyPI, perform pip updates, and check FFmpeg health | M5 | Upgrade |
| 26 | Desktop Integration & Tray | Drag & drop link/.txt support and system tray background minimization | M5 | Upgrade |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Formats & Downloader Engine | Domain models (`AUDIO_WAV`, `AUDIO_FLAC`), `YtDlpAdapter`, `FFmpegAdapter` | None | DONE |
| M2 | Network, Proxy & Cookies Subsystem | `AppSettings` update, proxy normalization, browser cookies (`cookiesfrombrowser`), scraper proxy integration | M1 | DONE |
| M3 | PySide6 GUI Complete Redesign | Dual-theme engine (`design_system.py`), ThemeManager, Mode/Format selectors, Progress metrics, History tab, Event Log panel, Settings tab | M1, M2 | DONE |
| M4 | Test Suite Expansion & Bugfix Audit | Unit/integration tests for formats, proxy, cookies, GUI headless verification, 100% test pass rate | M1, M2, M3 | DONE |
| M5 | Enterprise Multi-Platform & Engine Upgrade | TikTok, X, Reddit, FB, Pinterest, Subtitles, Clipping, In-App Player, Queue 2.0, Updater, Tray | M1-M4 | DONE |

## Interface Contracts
### Domain Models ↔ Adapters
- `QualityOption`: Enum values `best`, `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`, `mp3`, `m4a`, `wav`, `flac`.
- `AppSettings`: `download_path: str`, `default_quality: str`, `auto_paste: bool`, `sound_enabled: bool`, `proxy: str`, `cookies_file: str`, `dark_theme: bool`, `cookies_browser: str`.
- `YtDlpAdapter.download(request: DownloadRequest) -> DownloadResult`:
  - When `request.quality == QualityOption.AUDIO_WAV`: produces `.wav` file on disk via `FFmpegExtractAudio`.
  - When `request.quality == QualityOption.AUDIO_FLAC`: produces `.flac` file on disk via `FFmpegExtractAudio`.
  - When `request.quality == QualityOption.Q_2160P`: selects up to 2160p stream merged into `.mp4`.
  - When `settings.cookies_browser` is set: passes `cookiesfrombrowser: (browser_name,)`.
  - When `settings.proxy` is set: passes normalized `proxy: "http://..."` or `"socks5://..."`.

### GUI ↔ Concurrency & Workers
- `WorkerManager`: Tracks active `QThread` instances by ID; cleans up with `deleteLater()`.
- `ThemeManager`: Emits `theme_changed(str)`; `MainWindow._apply_theme(str)` updates QSS dynamically without app restart.
- `EventLogWidget`: Connected to Python logging or `LogSignalEmitter`; displays timestamped entries with HTML severity coloring.

## Code Layout
- `src/domain/models.py`: Domain entity models and quality enums.
- `src/domain/exceptions.py`: Domain exception definitions.
- `src/domain/url_parser.py`: URL parser for Instagram and YouTube links.
- `src/adapters/yt_dlp_adapter.py`: yt-dlp downloader implementation.
- `src/adapters/ffmpeg_adapter.py`: FFmpeg subprocess audio extractor and multiplexer.
- `src/adapters/direct_scraper.py`: Fallback oEmbed direct scrapers.
- `src/gui/design_system.py`: Design tokens, dual stylesheets, and dynamic QSS builder.
- `src/gui/app.py`: Main window, theme manager, logging integration, and event routing.
- `src/gui/workers.py`: Asynchronous QThread workers.
- `src/gui/components/`: Modular UI widgets (URL input, Batch, Queue, History, Settings, Event Log).
- `tests/`: Pytest suite.
