"""Tests for engine self-updater and health diagnostics."""

from unittest.mock import MagicMock, patch
from src.adapters.engine_updater import EngineUpdaterAdapter
from src.use_cases.update_engine import UpdateEngineUseCase


def test_updater_check_updates_success():
    adapter = EngineUpdaterAdapter()
    fake_json = b'{"info": {"version": "2026.11.01"}}'

    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_json
        mock_open.return_value.__enter__.return_value = mock_resp

        with patch.object(adapter, "get_current_version", return_value="2024.01.01"):
            has_update, curr, latest = adapter.check_for_updates()
            assert has_update is True
            assert curr == "2024.01.01"
            assert latest == "2026.11.01"


def test_updater_check_updates_already_latest():
    adapter = EngineUpdaterAdapter()
    fake_json = b'{"info": {"version": "2026.11.01"}}'

    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_json
        mock_open.return_value.__enter__.return_value = mock_resp

        with patch.object(adapter, "get_current_version", return_value="2026.11.01"):
            has_update, curr, latest = adapter.check_for_updates()
            assert has_update is False
            assert curr == "2026.11.01"
            assert latest == "2026.11.01"


def test_updater_perform_update_success():
    adapter = EngineUpdaterAdapter()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        messages = []
        success = adapter.perform_update(progress_callback=lambda m: messages.append(m))
        assert success is True
        assert len(messages) >= 2
        assert "completed successfully" in messages[-1]


def test_update_engine_use_case():
    mock_adapter = MagicMock()
    mock_adapter.check_for_updates.return_value = (True, "1.0", "2.0")
    mock_adapter.perform_update.return_value = True
    mock_adapter.check_ffmpeg_health.return_value = (True, "ffmpeg 6.0", "/path/ffmpeg")

    use_case = UpdateEngineUseCase(mock_adapter)
    assert use_case.check_update() == (True, "1.0", "2.0")
    assert use_case.update() is True
    healthy, ver, path = use_case.check_ffmpeg()
    assert healthy is True
    assert ver == "ffmpeg 6.0"
