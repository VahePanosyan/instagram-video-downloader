# Distribution & Installation Guide: Instagram & YouTube Video Downloader Pro

This document explains how to distribute, install, and run **Instagram & YouTube Video Downloader Pro** across different Windows PCs without requiring Python, FFmpeg, or any development dependencies.

---

## 1. Distribution Packages

The automated build pipeline produces two release distribution formats in the `dist/` directory:

| Package | Filename | Description | Target Use Case |
| :--- | :--- | :--- | :--- |
| **Windows Installer** | `InstagramDownloader_Setup.exe` | Complete Inno Setup installer wizard with LZMA2 solid compression. | **Recommended for end users.** Installs to Program Files/AppData, creates Desktop and Start Menu shortcuts, registers Windows uninstaller. |
| **Portable ZIP** | `InstagramVideoDownloader-v1.0.0-Portable.zip` | Standalone directory archive. No installation required. | **Recommended for USB drives or quick transfer.** Extract anywhere and double-click the `.exe`. |

Both packages are completely self-contained and pre-bundled with:
- The compiled GUI application executable (`InstagramVideoDownloader.exe`)
- The full PySide6 Qt GUI framework runtime and Windows platform plugins
- The complete `yt-dlp` engine with all lazy extractors pre-packaged
- Bundled `ffmpeg.exe` and `ffprobe.exe` binaries for high-definition stream merging and audio extraction
- Modern multi-resolution high-DPI application icons

---

## 2. Key Architecture & Portability Guarantees

### A. Zero CMD / Command Prompt Windows
The application executable is compiled with `console=False` (`IMAGE_SUBSYSTEM_WINDOWS_GUI`). When launched:
- Windows does **not** allocate or open a console terminal window.
- Standard streams (`sys.stdout`, `sys.stderr`) are safeguarded by a custom `_NullWriter` (supporting `write`, `writelines`, `writable`, `flush`, `reconfigure`, `isatty`) to prevent any `'NoneType' object has no attribute 'write'` crashes.
- All internal child processes (e.g., FFmpeg remuxing, file explorer reveal) execute with `subprocess.CREATE_NO_WINDOW` (flag `0x08000000`), ensuring that no secondary console window flashes when operations run.

### B. Pre-bundled FFmpeg & Automated Resolution
On host PCs without FFmpeg installed in system PATH:
- The application includes an automated locator (`src.adapters.ffmpeg_adapter.locate_ffmpeg_bin` and `locate_ffprobe_bin`) that checks:
  1. Local bundled directory: `<executable_dir>/bin/ffmpeg.exe`
  2. Local root directory: `<executable_dir>/ffmpeg.exe`
  3. Temporary unpack directory (if one-file packaging): `sys._MEIPASS/bin/ffmpeg.exe`
  4. Internal packaging directory: `<executable_dir>/_internal/bin/ffmpeg.exe`
  5. System PATH: `shutil.which("ffmpeg")`
  6. Windows package locations (WinGet Gyan, Chocolatey, Program Files)
- When detected, the FFmpeg directory is:
  1. Passed directly to `yt-dlp` options as `opts["ffmpeg_location"]`.
  2. Prepended to the process's `os.environ["PATH"]`.
  3. Injected into `FFmpegAdapter` for MP3 audio conversions and thumbnail extraction.
- As a result, 1080p/1440p/4K video format merging and MP3/M4A extraction work out of the box on another PC without installing FFmpeg.

### C. Persistent User Configuration & True Portability
- **Installed Mode**: If installed via `InstagramDownloader_Setup.exe` (marked by `installed.dat`), configuration (`settings.json`) and history (`history.json`) are automatically stored in the user's roaming application data directory:
  `%APPDATA%\InstagramVideoDownloader\config\`
  This prevents `PermissionError` when installed system-wide in `C:\Program Files`, and ensures settings are preserved across app updates.
- **Portable Mode**: The portable archive contains `portable.dat` and an empty `config/` directory. When `portable.dat` is present alongside `InstagramVideoDownloader.exe`, the application runs in true portable mode, storing settings and history locally next to the executable without touching `%APPDATA%` or the Windows Registry.
- **Cross-PC Path Self-Healing**: If a configuration file is transferred from a PC with different drive letters (e.g., pointing to `D:\` on a machine that only has `C:`), `JsonSettingsRepository` automatically detects that the drive root is unreachable and safely heals the download path to the local user's `Downloads` directory.
- **Default Download Path**: Automatically defaults to the standard Windows user `Downloads` directory (`Path.home() / "Downloads"`).

---

## 3. How to Transfer and Run on Another PC

### Option 1: Using the Windows Installer (`InstagramDownloader_Setup.exe`)
1. Copy or download `InstagramDownloader_Setup.exe` to the target PC (via USB drive, network share, cloud drive, or direct download).
2. Double-click `InstagramDownloader_Setup.exe`.
3. The modern setup wizard will appear:
   - Supports both "Install for current user only" (no administrator password required) and "Install for all users".
   - Select optional Desktop shortcut creation.
4. Click **Install**.
5. Once complete, launch the application from the Desktop shortcut or Start Menu.
6. The application opens immediately as a native Windows GUI window with no CMD prompt.
7. To uninstall: open **Windows Settings** -> **Apps** -> **Installed Apps** -> **Instagram & YouTube Video Downloader Pro** -> **Uninstall**.

### Option 2: Using the Portable Package (`InstagramVideoDownloader-v1.0.0-Portable.zip`)
1. Copy or download `InstagramVideoDownloader-v1.0.0-Portable.zip` to the target PC.
2. Right-click the `.zip` file and select **Extract All...** to any desired folder (e.g., `D:\Tools\InstagramDownloader`).
3. Open the extracted folder and double-click `InstagramVideoDownloader.exe`.
4. The application starts immediately without installing anything.

---

## 4. Rebuilding the Distribution Packages

If you modify application source code and want to rebuild the executable and installer:

```powershell
# 1. Ensure Python dependencies and tools are installed
pip install -r requirements.txt
pip install pyinstaller

# 2. Run the automated release build script
python build_installer.py
```

The build script will automatically:
1. Verify `bin/ffmpeg.exe` and `bin/ffprobe.exe`
2. Generate multi-resolution icons in `assets/`
3. Clean prior build directories
4. Run PyInstaller in windowed mode
5. Execute the compiled executable in offscreen headless mode (`--test-mode`) to verify startup
6. Compile `InstagramDownloader_Setup.exe` via Inno Setup (`ISCC.exe`)
7. Package `InstagramVideoDownloader-v1.0.0-Portable.zip`
8. Compute SHA-256 integrity checksums in `dist/SHA256SUMS.txt`
