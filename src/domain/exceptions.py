"""Domain exceptions for Instagram Downloader."""


class DownloaderException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class InvalidUrlException(DownloaderException):
    """Raised when an invalid or unsupported Instagram URL is provided."""
    pass


class ExtractionException(DownloaderException):
    """Raised when media metadata extraction fails."""
    pass


class AuthenticationRequiredException(ExtractionException):
    """Raised when post/story requires Instagram login cookies."""
    pass


class DownloadException(DownloaderException):
    """Raised when downloading a media stream fails."""
    pass


class StorageException(DownloaderException):
    """Raised when saving or reading files from disk fails."""
    pass


class NetworkException(DownloaderException):
    """Raised when network timeout or connection error occurs."""
    pass


class PostProcessingException(DownloaderException):
    """Raised when FFmpeg conversion or remuxing fails."""
    pass
