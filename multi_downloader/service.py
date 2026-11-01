"""Stable public facade for media URL, download, and environment services."""

from multi_downloader.media_downloads import (
    download_media,
    get_video_qualities,
    preview_media,
)
from multi_downloader.media_models import (
    DownloadCancelledError,
    DownloadControl,
    DownloadRequest,
    DownloadResult,
    MediaFormat,
    MediaPreview,
    ParsedMediaURL,
    ProgressCallback,
    Provider,
    URLValidationError,
)
from multi_downloader.media_urls import create_download_request, parse_media_url
from multi_downloader.system_checks import (
    check_dependency_updates,
    check_ffmpeg,
    is_update_available,
)

__all__ = [
    "DownloadCancelledError",
    "DownloadControl",
    "DownloadRequest",
    "DownloadResult",
    "MediaFormat",
    "MediaPreview",
    "ParsedMediaURL",
    "ProgressCallback",
    "Provider",
    "URLValidationError",
    "check_dependency_updates",
    "check_ffmpeg",
    "create_download_request",
    "download_media",
    "get_video_qualities",
    "is_update_available",
    "parse_media_url",
    "preview_media",
]
