from __future__ import annotations

from dataclasses import dataclass

from multi_downloader.service import (
    DownloadControl,
    DownloadRequest,
    DownloadResult,
    MediaPreview,
)


@dataclass
class _DownloadJob:
    job_id: int
    history_id: int
    request: DownloadRequest
    title: str = "Aguardando prévia"
    preview: MediaPreview | None = None
    attempts: int = 0
    control: DownloadControl | None = None
    skip_requested: bool = False


@dataclass(frozen=True)
class _UIEvent:
    kind: str
    job_id: int = 0
    progress: float = 0.0
    preview: MediaPreview | None = None
    result: DownloadResult | None = None
    error: Exception | None = None
    message: str = ""
