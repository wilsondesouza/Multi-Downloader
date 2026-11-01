from __future__ import annotations

import json
import platform
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from multi_downloader.persistence import AppStore
from multi_downloader.service import check_ffmpeg

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_SECRET_PATTERN = re.compile(
    r"(?i)\b(token|access_token|authorization|password|passwd|secret|cookie)"
    r"\s*[:=]\s*(?:(?:bearer|basic)\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_PACKAGES = ("customtkinter", "yt-dlp", "instaloader", "packaging")


def sanitize_error_details(error: Exception) -> str:
    message = _URL_PATTERN.sub("[URL removida]", str(error))
    message = _SECRET_PATTERN.sub(r"\1=[valor removido]", message)
    return f"{type(error).__name__}: {message}"[:2000]


def create_diagnostic_report(store: AppStore) -> str:
    packages: dict[str, str] = {}
    for package in _PACKAGES:
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = "not installed"

    history = [
        {
            "provider": record.provider,
            "format": record.media_format,
            "status": record.status,
            "error_code": record.error_code,
            "attempts": record.attempts,
        }
        for record in store.list_history(limit=20)
        if record.status in {"failed", "cancelled"}
    ]
    report: dict[str, Any] = {
        "application": "Multi-Downloader",
        "python": platform.python_version(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
        },
        "packages": packages,
        "ffmpeg": check_ffmpeg() or "not found",
        "recent_failures": history,
        "privacy": (
            "Source URLs, query strings, usernames, and local file paths are excluded."
        ),
    }
    return json.dumps(report, indent=2, ensure_ascii=False)


def save_diagnostic_report(contents: str, destination: Path) -> None:
    destination.write_text(contents, encoding="utf-8")
