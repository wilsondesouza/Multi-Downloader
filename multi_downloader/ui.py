from __future__ import annotations

import ctypes
import logging
import queue
import sys
from collections import deque
from pathlib import Path
from tkinter import BooleanVar, StringVar, messagebox

import customtkinter as ctk

from multi_downloader.persistence import AppStore, HistoryRecord
from multi_downloader.ui_components.dialogs import DialogsMixin
from multi_downloader.ui_components.download_events import DownloadEventsMixin
from multi_downloader.ui_components.queue import QueueMixin
from multi_downloader.ui_components.history import HistoryMixin
from multi_downloader.ui_components.models import _DownloadJob, _UIEvent
from multi_downloader.ui_components.quality import QualityMixin
from multi_downloader.ui_components.support import SupportMixin
from multi_downloader.ui_components.window import WindowMixin

_APP_USER_MODEL_ID = "WilsonSouza.MultiDownloader"
_LOGGER = logging.getLogger(__name__)


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        _APP_USER_MODEL_ID
    )
    if result != 0:
        _LOGGER.warning(
            "Could not set the Windows taskbar application ID (HRESULT 0x%08X).",
            result,
        )


class MultiDownloaderApp(
    WindowMixin,
    DialogsMixin,
    QueueMixin,
    DownloadEventsMixin,
    SupportMixin,
    HistoryMixin,
    QualityMixin,
):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        _set_windows_app_user_model_id()

        self.root = ctk.CTk()
        self.root.title("Multi Downloader")
        self.root.geometry("840x760")
        self.root.minsize(680, 650)
        self._set_window_icon()

        self.store = AppStore()
        self.store.mark_incomplete_history()
        self.settings = self.store.load_settings()
        self._events: queue.Queue[_UIEvent] = queue.Queue()
        self._pending_jobs: deque[_DownloadJob] = deque()
        self._active_job: _DownloadJob | None = None
        self._closing = False
        self._quality_request_id = 0
        self._quality_after_id: str | None = None
        self._job_counter = 0
        self._history_options: dict[str, HistoryRecord] = {}
        self._last_error_details = ""
        self._cancel_queue_after_current = False

        self.url_var = StringVar()
        self.format_var = StringVar(value="mp4")
        self.quality_var = StringVar(value=self.settings.default_quality)
        self.download_directory_var = StringVar(
            value=self.settings.download_directory or str(Path.cwd())
        )
        self.confirm_overwrite_var = BooleanVar(value=self.settings.confirm_overwrite)
        self.retries_var = StringVar(value=str(self.settings.max_retries))
        self.check_updates_startup_var = BooleanVar(
            value=self.settings.check_updates_on_startup
        )

        self._build_widgets()
        self.url_var.trace_add("write", self._on_url_change)
        self.url_entry.bind("<Return>", lambda _event: self._start_download())
        self.root.bind("<Control-Return>", lambda _event: self._start_download())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_events)
        self.root.after(150, self._check_ffmpeg)
        self._refresh_history()
        if self.settings.check_updates_on_startup:
            self.root.after(500, self._check_updates)


    def run(self) -> None:
        self.root.mainloop()


    def _on_close(self) -> None:
        if self._active_job is not None:
            close = messagebox.askyesno(
                "Download em andamento",
                "Fechar agora pode interromper a transferência e deixar um "
                "arquivo parcial. Deseja fechar mesmo assim?",
                parent=self.root,
            )
            if not close:
                return
            if self._active_job.control is not None:
                self._active_job.control.cancel()
        self._closing = True
        if self._quality_after_id is not None:
            self.root.after_cancel(self._quality_after_id)
        self.store.mark_incomplete_history()
        self.store.close()
        self.root.destroy()


def main() -> None:
    MultiDownloaderApp().run()
