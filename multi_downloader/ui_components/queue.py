from __future__ import annotations

from typing import TYPE_CHECKING

import threading
from pathlib import Path
from tkinter import messagebox

from multi_downloader.service import (
    DownloadControl,
    DownloadRequest,
    URLValidationError,
    create_download_request,
    download_media,
    preview_media,
)
from multi_downloader.ui_components.models import _DownloadJob, _UIEvent

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class QueueMixin:

    def _enqueue_batch_urls(
        self: MultiDownloaderApp,
        urls: list[str],
    ) -> tuple[int, list[str]]:
        accepted = 0
        rejected: list[str] = []
        for url in urls:
            try:
                request = self._create_request(url)
            except (URLValidationError, ValueError):
                rejected.append(url)
                continue
            self._enqueue_request(request)
            accepted += 1
        self._start_next_job()
        return accepted, rejected

    def _create_request(self: MultiDownloaderApp, url: str) -> DownloadRequest:
        destination_root = Path(self.download_directory_var.get()).expanduser()
        if not destination_root.is_absolute():
            raise ValueError("Escolha um diretório de destino absoluto.")
        return create_download_request(
            url,
            self.format_var.get(),
            self.quality_var.get(),
            destination=destination_root,
        )

    def _start_download(self: MultiDownloaderApp) -> None:
        try:
            request = self._create_request(self.url_var.get())
        except (URLValidationError, ValueError) as exc:
            messagebox.showerror("Link inválido", str(exc), parent=self.root)
            return
        self._enqueue_request(request)
        self.url_var.set("")
        self._start_next_job()

    def _enqueue_request(self: MultiDownloaderApp, request: DownloadRequest) -> None:
        self._job_counter += 1
        history_id = self.store.create_history_record(
            request.provider,
            "Aguardando prévia",
            request.media_format,
            status="queued",
        )
        self._pending_jobs.append(
            _DownloadJob(self._job_counter, history_id, request)
        )
        self._refresh_queue_view()
        self._refresh_history()

    def _start_next_job(self: MultiDownloaderApp) -> None:
        if self._closing or self._active_job is not None or not self._pending_jobs:
            return
        job = self._pending_jobs.popleft()
        job.control = DownloadControl()
        self._active_job = job
        self.store.update_history_record(
            job.history_id,
            status="previewing",
            attempts=0,
        )
        self.status_label.configure(
            text=f"Consultando mídia em {job.request.provider}..."
        )
        self.cancel_button.configure(state="normal", text="Pular prévia")
        self._refresh_queue_view()

        def worker() -> None:
            try:
                preview = preview_media(job.request)
                self._events.put(
                    _UIEvent(kind="preview_ready", job_id=job.job_id, preview=preview)
                )
            except Exception as exc:
                self._events.put(
                    _UIEvent(kind="job_error", job_id=job.job_id, error=exc)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _run_active_download(self: MultiDownloaderApp, job: _DownloadJob) -> None:
        self.store.update_history_record(
            job.history_id,
            title=job.title,
            status="downloading",
            attempts=1,
        )
        self.status_label.configure(text=f"Baixando {job.title}...")
        self.pause_button.configure(
            state="disabled" if job.request.provider == "Instagram" else "normal",
            text="Pausar",
        )
        self.cancel_button.configure(
            state="normal",
            text=(
                "Parar após mídia"
                if job.request.provider == "Instagram"
                else "Cancelar"
            ),
        )
        self.progress.set(0)
        self._refresh_history()

        def worker() -> None:
            try:
                result = download_media(
                    job.request,
                    progress_callback=lambda value: self._events.put(
                        _UIEvent(
                            kind="progress",
                            job_id=job.job_id,
                            progress=value,
                        )
                    ),
                    control=job.control,
                    max_retries=self.settings.max_retries,
                    status_callback=lambda status: self._events.put(
                        _UIEvent(
                            kind="retry",
                            job_id=job.job_id,
                            message=status,
                        )
                    ),
                )
                self._events.put(
                    _UIEvent(kind="job_done", job_id=job.job_id, result=result)
                )
            except Exception as exc:
                self._events.put(
                    _UIEvent(kind="job_error", job_id=job.job_id, error=exc)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_active_job(self: MultiDownloaderApp) -> None:
        self._active_job = None
        self.pause_button.configure(state="disabled", text="Pausar")
        self.cancel_button.configure(state="disabled", text="Cancelar")
        self.progress.set(0)
        self._refresh_queue_view()
        if self._cancel_queue_after_current:
            self._cancel_queue_after_current = False
            self._clear_queue()
        self._start_next_job()

    def _toggle_pause(self: MultiDownloaderApp) -> None:
        job = self._active_job
        if job is None or job.control is None:
            return
        if job.request.provider == "Instagram":
            messagebox.showinfo(
                "Pausa indisponível",
                "O Instaloader não oferece pausa segura durante a transferência. "
                "Você ainda pode parar a fila após a mídia atual.",
                parent=self.root,
            )
            return
        if job.control.is_paused:
            job.control.resume()
            self.pause_button.configure(text="Pausar")
            self.status_label.configure(text=f"Baixando {job.title}...")
            status = "downloading"
        else:
            job.control.pause()
            self.pause_button.configure(text="Retomar")
            self.status_label.configure(text=f"Baixamento pausado: {job.title}")
            status = "paused"
        self.store.update_history_record(
            job.history_id,
            status=status,
            attempts=max(1, job.attempts),
        )
        self._refresh_history()

    def _cancel_active(self: MultiDownloaderApp) -> None:
        job = self._active_job
        if job is None:
            return
        if job.preview is None:
            job.skip_requested = True
            self.cancel_button.configure(state="disabled")
            self.status_label.configure(
                text="O item será pulado assim que a consulta da prévia terminar."
            )
            return
        if job.request.provider == "Instagram":
            self._cancel_queue_after_current = True
            self.cancel_button.configure(state="disabled")
            self.status_label.configure(
                text=(
                    "A fila parará quando a transferência atual do Instagram "
                    "terminar."
                )
            )
            return
        if job.control is not None:
            job.control.cancel()
            self.status_label.configure(text="Cancelando...")

    def _clear_queue(self: MultiDownloaderApp) -> None:
        while self._pending_jobs:
            job = self._pending_jobs.popleft()
            self.store.update_history_record(
                job.history_id,
                status="cancelled",
                error_code="RemovedFromQueue",
            )
        self._refresh_queue_view()
        self._refresh_history()
