"""Tests for FFmpeg locator, windowed stream safety, and installer prerequisites."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

from src.adapters.ffmpeg_adapter import (
    locate_ffmpeg_bin,
    locate_ffmpeg_dir,
    ensure_ffmpeg_in_path,
)
from src.adapters.yt_dlp_adapter import YtDlpAdapter
from src.adapters.json_repository import (
    get_default_config_dir,
    get_default_downloads_dir,
    JsonSettingsRepository,
)
from main import _NullWriter


def test_null_writer_stream_safety():
    """Verifies that _NullWriter provides safe no-op behavior for windowed GUI mode."""
    writer = _NullWriter()
    assert writer.write("test log message\n") == len("test log message\n")
    writer.writelines(["line 1\n", "line 2\n"])
    writer.flush()
    writer.reconfigure(encoding="utf-8", errors="replace")
    assert writer.isatty() is False
    assert writer.writable() is True


def test_locate_ffmpeg_bin_finds_bundled_or_system():
    """Verifies that locate_ffmpeg_bin returns a valid path to an existing ffmpeg binary."""
    ffmpeg_bin = locate_ffmpeg_bin()
    assert ffmpeg_bin is not None
    assert Path(ffmpeg_bin).is_file()
    assert "ffmpeg" in Path(ffmpeg_bin).name.lower()


def test_locate_ffprobe_bin_finds_binary():
    """Verifies that locate_ffprobe_bin returns a valid path to an existing ffprobe binary."""
    from src.adapters.ffmpeg_adapter import locate_ffprobe_bin
    ffprobe_bin = locate_ffprobe_bin()
    assert ffprobe_bin is not None
    assert Path(ffprobe_bin).is_file()
    assert "ffprobe" in Path(ffprobe_bin).name.lower()


def test_locate_ffmpeg_dir():
    """Verifies that locate_ffmpeg_dir returns the containing directory."""
    ffmpeg_dir = locate_ffmpeg_dir()
    assert ffmpeg_dir is not None
    dir_path = Path(ffmpeg_dir)
    assert dir_path.is_dir()
    # Should contain ffmpeg binary
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    assert (dir_path / exe_name).is_file()


def test_locate_ffmpeg_bin_environment_variable_override(tmp_path):
    """Verifies that FFMPEG_PATH environment variable overrides auto-detection."""
    fake_ffmpeg = tmp_path / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    fake_ffmpeg.write_text("fake binary")

    with patch.dict(os.environ, {"FFMPEG_PATH": str(fake_ffmpeg)}):
        result = locate_ffmpeg_bin()
        assert result == str(fake_ffmpeg)


def test_locate_ffmpeg_bin_frozen_internal(tmp_path):
    """Verifies that locate_ffmpeg_bin finds ffmpeg in _internal/bin when running frozen."""
    fake_exe = tmp_path / "app.exe"
    fake_exe.touch()
    internal_bin = tmp_path / "_internal" / "bin"
    internal_bin.mkdir(parents=True)
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    fake_ffmpeg = internal_bin / exe_name
    fake_ffmpeg.write_text("binary")

    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", str(fake_exe)):
            # Clear FFMPEG_PATH env var
            env_without_ffmpeg = {k: v for k, v in os.environ.items() if "FFMPEG" not in k}
            with patch.dict(os.environ, env_without_ffmpeg, clear=True):
                res = locate_ffmpeg_bin()
                assert res == str(fake_ffmpeg)


def test_ensure_ffmpeg_in_path():
    """Verifies that ensure_ffmpeg_in_path puts the directory in os.environ['PATH']."""
    ffmpeg_dir = locate_ffmpeg_dir()
    assert ffmpeg_dir is not None

    with patch.dict(os.environ, {"PATH": "C:\\Windows\\System32"}):
        ensured = ensure_ffmpeg_in_path()
        assert ensured == ffmpeg_dir
        path_list = os.environ["PATH"].split(os.pathsep)
        assert os.path.normcase(os.path.abspath(path_list[0])) == os.path.normcase(os.path.abspath(ffmpeg_dir))


def test_ytdlp_adapter_includes_ffmpeg_location():
    """Verifies that YtDlpAdapter passes ffmpeg_location in its base options."""
    adapter = YtDlpAdapter()
    opts = adapter._build_base_options()
    ffmpeg_dir = locate_ffmpeg_dir()
    if ffmpeg_dir:
        assert "ffmpeg_location" in opts
        assert opts["ffmpeg_location"] == ffmpeg_dir


def test_get_default_config_dir_dev_mode():
    """Verifies that development mode returns the repository config directory."""
    with patch.object(sys, "frozen", False, create=True):
        config_dir = get_default_config_dir()
        assert config_dir.name == "config"
        assert config_dir.is_dir()


def test_get_default_config_dir_frozen_portable_marker(tmp_path):
    """Verifies that portable.dat next to the executable enforces portable config directory."""
    fake_exe = tmp_path / "InstagramVideoDownloader.exe"
    fake_exe.touch()
    (tmp_path / "portable.dat").write_text("portable_mode=true")

    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", str(fake_exe)):
            res = get_default_config_dir()
            assert res == tmp_path / "config"
            assert res.is_dir()


def test_get_default_config_dir_frozen_installed_marker(tmp_path):
    """Verifies that installed.dat marker overrides local config and uses %APPDATA%."""
    fake_exe = tmp_path / "App" / "InstagramVideoDownloader.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()
    (fake_exe.parent / "installed.dat").write_text("installed_mode=true")
    # Even if a local config folder exists
    (fake_exe.parent / "config").mkdir()

    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_appdata.mkdir(parents=True)

    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", str(fake_exe)):
            with patch.dict(os.environ, {"APPDATA": str(fake_appdata)}):
                res = get_default_config_dir()
                expected = fake_appdata / "InstagramVideoDownloader" / "config"
                assert res == expected


def test_get_default_config_dir_frozen_program_files_protection(tmp_path):
    """Verifies that installation in Program Files always defaults to %APPDATA% without crashing."""
    fake_exe = tmp_path / "Program Files" / "Instagram Video Downloader Pro" / "app.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()
    # Even if config folder exists in program files
    (fake_exe.parent / "config").mkdir()

    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_appdata.mkdir(parents=True)

    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", str(fake_exe)):
            with patch.dict(os.environ, {"APPDATA": str(fake_appdata)}):
                res = get_default_config_dir()
                expected = fake_appdata / "InstagramVideoDownloader" / "config"
                assert res == expected


def test_settings_repository_heals_invalid_download_dir(tmp_path):
    """Verifies that JsonSettingsRepository automatically heals invalid/non-existent drive paths."""
    config_file = tmp_path / "settings.json"
    # Write a settings file with an impossible/non-existent drive
    invalid_drive_path = "Z:\\nonexistent_drive_12345\\downloads"
    config_file.write_text(f'{{"download_dir": "{invalid_drive_path}"}}', encoding="utf-8")

    repo = JsonSettingsRepository(file_path=str(config_file))
    loaded = repo.load()
    # download_dir must NOT be the invalid drive
    assert loaded.download_dir != invalid_drive_path
    assert Path(loaded.download_dir).exists()


def test_get_default_downloads_dir():
    """Verifies default downloads directory resolution."""
    downloads_dir = get_default_downloads_dir()
    assert downloads_dir.exists()


def test_headless_qt_startup():
    """Verifies that the PySide6 MainWindow initializes headlessly on offscreen platform with valid icon."""
    from PySide6.QtWidgets import QApplication
    from src.gui.app import MainWindow

    app = QApplication.instance() or QApplication(["--platform", "offscreen"])
    assert app is not None
    window = MainWindow()
    assert window._adapter is not None
    assert window._settings_use_case is not None
    assert window._history_use_case is not None
    assert window._metadata_use_case is not None
    assert window._single_download_use_case is not None
    assert window._batch_use_case is not None
    assert not window.windowIcon().isNull()
    window.close()


def test_installer_iss_configuration():
    """Verifies that installer.iss contains valid WorkingDir, embedded icon references, and installed.dat."""
    iss_path = Path(__file__).resolve().parent.parent / "installer.iss"
    assert iss_path.is_file()
    content = iss_path.read_text(encoding="utf-8")
    assert 'WorkingDir: "{app}"' in content
    assert 'IconFilename: "{app}\\{#MyAppExeName}"' in content
    assert 'Source: "installed.dat"' in content


def test_spec_datas_hygiene():
    """Verifies that InstagramDownloader.spec does not bundle developer local config with pytest traces."""
    spec_path = Path(__file__).resolve().parent.parent / "InstagramDownloader.spec"
    assert spec_path.is_file()
    content = spec_path.read_text(encoding="utf-8")
    assert '("config", "config")' not in content
    assert '"bin/ffmpeg.exe"' in content
    assert '"bin/ffprobe.exe"' in content
