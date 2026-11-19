"""Main entry point for Instagram & YouTube Video Downloader Pro."""

import sys
import ctypes
from pathlib import Path


class _NullWriter:
    """Safe no-op writer for GUI windowed/noconsole mode when stdout/stderr is None."""

    def write(self, s: str) -> int:
        return len(s)

    def writelines(self, lines) -> None:
        pass

    def flush(self) -> None:
        pass

    def reconfigure(self, *args, **kwargs) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def setup_windows_environment():
    """Sets Windows AppUserModelID, safe GUI streams, high-DPI scaling, and FFmpeg environment."""
    # Ensure stdout/stderr are non-null in windowed/noconsole mode
    if sys.stdout is None:
        sys.stdout = _NullWriter()
    elif hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if sys.stderr is None:
        sys.stderr = _NullWriter()
    elif hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Ensure bundled or installed FFmpeg is in PATH for child processes
    try:
        from src.adapters.ffmpeg_adapter import ensure_ffmpeg_in_path
        ensure_ffmpeg_in_path()
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            myappid = "media.video.downloader.pro.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass


def main():
    setup_windows_environment()

    # Headless test verification mode
    if "--test-mode" in sys.argv:
        from PySide6.QtWidgets import QApplication
        from src.gui.app import MainWindow
        from src.adapters.ffmpeg_adapter import locate_ffmpeg_bin

        app = QApplication(["--platform", "offscreen"])
        window = MainWindow()
        assert window._adapter is not None, "Adapter not initialized"
        assert window._settings_use_case is not None, "Settings use case not initialized"
        assert window._history_use_case is not None, "History use case not initialized"
        assert locate_ffmpeg_bin() is not None, "FFmpeg binary not detected"
        assert not window.windowIcon().isNull(), "Window icon not set"
        window.close()
        app.quit()
        sys.exit(0)

    # Route to CLI mode if arguments are supplied and --gui is not explicitly specified
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from src.cli import run_cli
        sys.exit(run_cli())
    elif len(sys.argv) > 1 and "--gui" not in sys.argv:
        from src.cli import run_cli
        sys.exit(run_cli())
    elif "--gui" in sys.argv:
        sys.argv.remove("--gui")

    # Launch PySide6 GUI
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from src.gui.app import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Instagram & YouTube Video Downloader Pro")
    app.setOrganizationName("MediaDownloaderPro")

    # Set application icon
    for icon_path in [
        Path(sys.executable).parent / "assets" / "app_icon.ico" if getattr(sys, "frozen", False) else None,
        Path(sys.executable).parent / "_internal" / "assets" / "app_icon.ico" if getattr(sys, "frozen", False) else None,
        Path(getattr(sys, "_MEIPASS", "")) / "assets" / "app_icon.ico" if getattr(sys, "frozen", False) else None,
        Path(__file__).resolve().parent / "assets" / "app_icon.ico",
        Path(__file__).resolve().parent / "assets" / "app_icon.png",
    ]:
        if icon_path and icon_path.is_file():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
