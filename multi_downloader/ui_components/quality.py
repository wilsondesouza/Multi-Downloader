from __future__ import annotations

from typing import TYPE_CHECKING

import threading
from pathlib import Path

from multi_downloader.service import (
    URLValidationError,
    create_download_request,
    parse_media_url,
    preview_media,
)
from multi_downloader.ui_components.models import _UIEvent

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class QualityMixin:

    def _on_url_change(self: MultiDownloaderApp, *_: object) -> None:
        self._quality_request_id += 1
        request_id = self._quality_request_id
        if self._quality_after_id is not None:
            self.root.after_cancel(self._quality_after_id)
            self._quality_after_id = None
        try:
            parsed = parse_media_url(self.url_var.get())
        except URLValidationError:
            self._set_instagram_mode(False)
            return

        is_instagram = parsed.provider == "Instagram"
        self._set_instagram_mode(is_instagram)
        if not is_instagram and self.format_var.get() == "mp4":
            self._quality_after_id = self.root.after(
                650,
                lambda: self._request_qualities(self.url_var.get(), request_id),
            )


    def _on_format_change(self: MultiDownloaderApp) -> None:
        self.quality_menu.configure(
            state="normal" if self.format_var.get() == "mp4" else "disabled"
        )
        if self.format_var.get() == "mp4":
            self._on_url_change()


    def _request_qualities(
        self: MultiDownloaderApp,
        url: str,
        request_id: int,
    ) -> None:
        self._quality_after_id = None
        try:
            request = create_download_request(
                url,
                "mp4",
                destination=Path(self.download_directory_var.get()),
            )
        except (URLValidationError, ValueError):
            return

        def worker() -> None:
            try:
                preview = preview_media(request)
                message = (
                    f"{preview.title}"
                    + (
                        f" — {self._format_duration(preview.duration_seconds)}"
                        if preview.duration_seconds is not None
                        else ""
                    )
                )
                self._events.put(
                    _UIEvent(
                        kind="qualities",
                        job_id=request_id,
                        preview=preview,
                        message=message,
                    )
                )
            except Exception as exc:
                self._events.put(
                    _UIEvent(
                        kind="quality_error",
                        job_id=request_id,
                        error=exc,
                    )
                )

        threading.Thread(target=worker, daemon=True).start()
