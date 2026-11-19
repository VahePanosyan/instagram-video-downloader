"""Use case for loading, updating, and saving settings."""

from pathlib import Path
from ..domain.models import AppSettings
from ..ports.repository import ISettingsRepository


class ManageSettingsUseCase:
    """Manages application settings lifecycle."""

    def __init__(self, settings_repo: ISettingsRepository):
        self._repo = settings_repo
        self._current_settings = self._repo.load()

    def get_settings(self) -> AppSettings:
        return self._current_settings

    def update_settings(self, new_settings: AppSettings) -> AppSettings:
        # Validate download directory exists or can be created
        if new_settings.download_dir:
            try:
                Path(new_settings.download_dir).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # Clamp concurrency
        new_settings.concurrent_downloads = max(1, min(new_settings.concurrent_downloads, 16))

        self._repo.save(new_settings)
        self._current_settings = new_settings
        return self._current_settings
