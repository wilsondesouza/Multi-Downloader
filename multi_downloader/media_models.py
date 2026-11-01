from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal


Provider = Literal["YouTube", "Instagram", "Twitter", "Facebook"]
MediaFormat = Literal["mp3", "mp4"]
ProgressCallback = Callable[[float], None]


class URLValidationError(ValueError):
    """Raised when a URL is not a supported public media link."""


@dataclass(frozen=True)
class ParsedMediaURL:
    provider: Provider
    url: str
    shortcode: str | None = None


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    provider: Provider
    media_format: MediaFormat
    quality: str = "best"
    destination: Path | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class MediaPreview:
    title: str
    duration_seconds: float | None
    qualities: list[int]
    output_path: Path | None


class DownloadCancelledError(Exception):
    """Raised when a user cancels a download between transfer chunks."""


class DownloadControl:
    def __init__(self) -> None:
        self._resume = threading.Event()
        self._resume.set()
        self._cancel = threading.Event()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._resume.set()

    def wait_until_resumed(self) -> None:
        while not self._resume.wait(timeout=0.2):
            if self._cancel.is_set():
                raise DownloadCancelledError()
        if self._cancel.is_set():
            raise DownloadCancelledError()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def is_paused(self) -> bool:
        return not self._resume.is_set()


@dataclass(frozen=True)
class DownloadResult:
    provider: Provider
    title: str
    output_directory: Path
    elapsed_seconds: float
    output_file: Path | None = None
    attempts: int = 1

