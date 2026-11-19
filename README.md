# ⚡ Instagram & YouTube Video Downloader Pro

A production-grade, ultra-fast Instagram (Reels, Videos, Carousels, Posts, Stories) and YouTube (Videos, Shorts, Music/Audio, Playlists) downloader engineered with **Clean Hexagonal Architecture (Ports & Adapters)** and a sleek **PySide6 (Qt 6) Dark Luxe Design System**.

---

## ✨ Features

- 🎯 **All Media Formats Supported**:
  - **Instagram**: Reels (`/reel/`, `/reels/`, `/share/reel/`), Feed Posts & Carousels (`/p/`), Stories & Highlights (`/stories/`), IGTV (`/tv/`)
  - **YouTube**: Standard Videos (`watch?v=`), Shorts (`/shorts/`), Short links (`youtu.be`), Embeds (`/embed/`), Live Streams (`/live/`), and Full Playlists (`playlist?list=`)
- 🎨 **Modern Design System (PySide6 / Qt 6)**:
  - Brand accent gradients (Instagram Coral/Purple, YouTube Red `#FF0000`) & Dark Obsidian palette (`#0B0F19`, `#161E2E`)
  - Real-time animated progress bars with live download speed (MB/s) and ETA
  - High-DPI scaling and native Windows taskbar integration
  - Intelligent URL detection & badge indicator for Instagram vs. YouTube
- 🚀 **High-Throughput Concurrent Batch & Playlist Engine**:
  - Multi-threaded worker pool (1 to 8 concurrent threads)
  - Paste dozens or hundreds of mixed Instagram & YouTube URLs at once or load directly from `.txt` files
  - Automatic YouTube playlist unpacking into the batch download queue
  - Automatic URL deduplication and sanitization
- 🎵 **Flexible Format & Audio Extraction**:
  - Best Video (MP4)
  - 4K Ultra HD (2160p), 2K Quad HD (1440p), Full HD 1080p, 720p, 480p, 360p
  - High-Fidelity Audio Only (MP3 320kbps via FFmpeg)
  - Clean M4A / AAC Audio
- 📋 **Seamless Clipboard Integration**:
  - Auto-detects both Instagram and YouTube URLs copied to your clipboard
  - 1-click quick paste & inspect
- 📜 **Download History & Media Manager**:
  - Filter and search history by creator, title, platform, or URL
  - Direct 1-click playback in Windows default player
  - "Show in Folder" Explorer integration
- ⚙️ **Power User Settings**:
  - Configurable download folder
  - Custom file naming templates (`{author}_{shortcode}`, `{author}_{title}`, `{title}`, `{id}`)
  - Custom `cookies.txt` file support (for private accounts, age-restricted YouTube videos, and stories)
  - Proxy support (HTTP/HTTPS/SOCKS5)
  - Rate limiting (KB/s)

---

## 🏗️ Architecture (Hexagonal / Ports & Adapters)

```
                         +-----------------------------+
                         |      Driving Adapters       |
                         |   (PySide6 GUI / CLI)       |
                         +--------------+--------------+
                                        |
                                        v
+--------------------------------------------------------------------------------+
|  Application Use Cases                                                         |
|  - ExtractMetadataUseCase (with in-memory cache & universal parsing)           |
|  - DownloadMediaUseCase                                                        |
|  - BatchDownloaderUseCase (ThreadPoolExecutor worker pool & playlist expander) |
|  - ManageHistoryUseCase                                                        |
|  - ManageSettingsUseCase                                                       |
+--------------------------------------------------------------------------------+
                                        |
                                        v
+--------------------------------------------------------------------------------+
|  Ports (Interfaces)                                                            |
|  - IExtractor                                                                  |
|  - IDownloader                                                                 |
|  - ISettingsRepository                                                         |
|  - IHistoryRepository                                                          |
|  - IProgressNotifier                                                           |
+--------------------------------------------------------------------------------+
                                        |
                                        v
+--------------------------------------------------------------------------------+
|  Driven Adapters                                                               |
|  - YtDlpAdapter (tuned yt-dlp extractor & downloader with DASH merging)        |
|  - FFmpegAdapter (remuxing & 320k MP3 audio transcode)                         |
|  - UniversalDirectScraper / DirectYouTubeScraper / DirectInstagramScraper     |
|  - JsonSettingsRepository (atomic JSON file storage)                           |
|  - JsonHistoryRepository (atomic JSON file storage)                            |
+--------------------------------------------------------------------------------+
```

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- FFmpeg (installed and available in system PATH)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch Application
Double-click `run.bat` or run:
```bash
python main.py
```

---

## 💻 CLI Usage

You can also use the downloader headlessly from the command line:

```bash
# Download an Instagram Reel in best available quality
python main.py --cli "https://www.instagram.com/reel/C2-7XYZ1234/"

# Download a YouTube video in 1080p
python main.py --cli "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p

# Download YouTube video or Shorts as Audio MP3 (320 kbps)
python main.py --cli "https://youtu.be/dQw4w9WgXcQ" -q mp3

# Download a YouTube Playlist
python main.py --cli "https://www.youtube.com/playlist?list=PLrEnWoR732-B41NYGQHSUGpplEwHms5sQ" --playlist -c 4

# Batch download mixed Instagram & YouTube URLs from a text file with 4 concurrent threads
python main.py --cli --batch urls.txt -c 4 -o ./my_videos

# Inspect video metadata without downloading
python main.py --cli "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --info-only

# View download history
python main.py --cli --history

# Use custom cookies for private Instagram posts or age-restricted YouTube videos
python main.py --cli "https://www.youtube.com/watch?v=ABC" --cookies cookies.txt
```

---

## 📦 Standalone Windows Installer & Portable Executable (No Python Required)

You can run the application on any Windows PC without installing Python, FFmpeg, or any dependencies.

### Option A: Professional Windows Installer (`InstagramDownloader_Setup.exe`)
1. Download `dist/InstagramDownloader_Setup.exe` to this or another PC.
2. Double-click the installer:
   - Installs without requiring Administrator elevation (or system-wide if run as admin).
   - Automatically sets up Desktop and Start Menu shortcuts.
   - Built under Windows GUI subsystem (`--windowed` / `console=False`): **No CMD / console terminal window appears**.
   - Includes bundled FFmpeg & FFprobe binaries in `bin/` for high-resolution video merging and audio extraction.
   - Built-in clean Windows Uninstaller.

### Option B: Standalone Portable ZIP (`InstagramVideoDownloader-v1.0.0-Portable.zip`)
1. Download `dist/InstagramVideoDownloader-v1.0.0-Portable.zip`.
2. Extract the archive to any folder or USB flash drive.
3. Double-click `InstagramVideoDownloader.exe` to launch immediately with zero setup.

### Rebuilding the Installer & Executable
To build the distribution packages from source:
```bash
python build_installer.py
```
This automated release script validates FFmpeg binaries, generates icons, runs PyInstaller in windowed mode, verifies headless startup (`--test-mode`), compiles the Inno Setup installer, packages the portable ZIP, and produces SHA-256 verification hashes.

For detailed architecture and multi-PC deployment notes, see [DISTRIBUTION.md](file:///d:/instagram%20video%20downloader/DISTRIBUTION.md).

---

## 🧪 Automated Testing

Run the full pytest suite (including domain models, URL parsers, use cases, adapters, installer and locator mechanisms, and headless GUI tests):

```bash
python -m pytest tests -v
```

All 93 automated tests pass with 100% success.


