from __future__ import annotations

from typing import TYPE_CHECKING

import queue
from dataclasses import replace
from tkinter import messagebox

from multi_downloader.diagnostics import sanitize_error_details
from multi_downloader.service import DownloadCancelledError, MediaPreview
from multi_downloader.ui_components.models import _DownloadJob, _UIEvent

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class DownloadEventsMixin:

    def _handle_preview(self: MultiDownloaderApp, event: _UIEvent) -> None:
        job = self._active_job
        if job is None or event.preview is None:
            return
        job.preview = event.preview
        job.title = event.preview.title
        self._refresh_queue_view()
        if job.skip_requested:
            self._finish_job_as_skipped(job)
            return
        self._log_history_preview(job, event.preview)

        output_path = event.preview.output_path
        if output_path is not None and output_path.exists():
            if job.request.provider == "Instagram":
                messagebox.showinfo(
                    "Arquivo já existe",
                    "O Instaloader não oferece substituição segura de arquivos. "
                    "O item será ignorado; remova o arquivo existente se quiser "
                    "baixá-lo novamente.",
                    parent=self.root,
                )
                self._finish_job_as_skipped(job, "OutputExists")
                return
            if self.confirm_overwrite_var.get():
                overwrite = messagebox.askyesno(
                    "Arquivo já existe",
                    f"{event.preview.title}\n\n{output_path}\n\n"
                    "Deseja substituir o arquivo existente?",
                    parent=self.root,
                )
                if not overwrite:
                    self._finish_job_as_skipped(job, "OverwriteDeclined")
                    return
            job.request = replace(job.request, overwrite=True)
        self._run_active_download(job)

    def _log_history_preview(
        self: MultiDownloaderApp,
        job: _DownloadJob,
        preview: MediaPreview,
    ) -> None:
        if preview.duration_seconds is None:
            summary = preview.title
        else:
            summary = (
                f"{preview.title} — {self._format_duration(preview.duration_seconds)}"
            )
        self.store.update_history_record(
            job.history_id,
            title=summary,
            status="queued",
            output_path=str(preview.output_path or ""),
            attempts=0,
        )
        self._refresh_history()

    def _handle_job_error(self: MultiDownloaderApp, event: _UIEvent) -> None:
        job = self._active_job
        if job is None or event.error is None:
            return
        if job.skip_requested:
            self.store.update_history_record(
                job.history_id,
                status="cancelled",
                error_code="SkippedBeforeDownload",
                attempts=0,
            )
            self._log_history(f"Ignorado antes do download: {job.title}")
            self._finish_active_job()
            return
        if isinstance(event.error, DownloadCancelledError):
            self.store.update_history_record(
                job.history_id,
                status="cancelled",
                error_code=type(event.error).__name__,
                attempts=job.attempts or 1,
            )
            self._log_history(f"Cancelado: {job.title}")
            self._finish_active_job()
            return

        details = sanitize_error_details(event.error)
        self._last_error_details = details
        job.attempts = max(1, job.attempts)
        self.store.update_history_record(
            job.history_id,
            status="failed",
            error_code=type(event.error).__name__,
            attempts=job.attempts,
        )
        self.status_label.configure(text="Falha — consulte o histórico e os detalhes")
        self._log_history(f"Falha: {job.title} ({type(event.error).__name__})")
        self._show_error_details(details)
        self._finish_active_job()

    def _handle_job_done(self: MultiDownloaderApp, event: _UIEvent) -> None:
        job = self._active_job
        result = event.result
        if job is None or result is None:
            return
        output_path = result.output_file or result.output_directory
        self.store.update_history_record(
            job.history_id,
            title=result.title,
            status="completed",
            output_path=str(output_path),
            attempts=result.attempts,
        )
        self.progress.set(1)
        self.status_label.configure(text="Download concluído")
        self._log_history(
            f"Concluído: {result.title} ({result.elapsed_seconds:.1f} s)"
        )
        self._refresh_history()
        if not self._pending_jobs and result.output_directory.exists():
            self._open_directory(result.output_directory)
        self._finish_active_job()

    def _finish_job_as_skipped(
        self,
        job: _DownloadJob,
        reason: str = "SkippedBeforeDownload",
    ) -> None:
        self.store.update_history_record(
            job.history_id,
            status="skipped",
            error_code=reason,
        )
        self._log_history(f"Ignorado: {job.title} ({reason})")
        self._refresh_history()
        self._finish_active_job()

    def _handle_retry(self: MultiDownloaderApp, event: _UIEvent) -> None:
        job = self._active_job
        if job is None:
            return
        job.attempts += 1
        self.status_label.configure(text=event.message)
        self.store.update_history_record(
            job.history_id,
            status="downloading",
            attempts=job.attempts + 1,
        )
        self._refresh_history()

    def _drain_events(self: MultiDownloaderApp) -> None:
        if self._closing:
            return
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event.kind == "ffmpeg":
                self.ffmpeg_label.configure(text=event.message)
            elif event.kind == "updates":
                self._show_update_results(event.message)
            elif event.kind == "diagnostic":
                self._show_diagnostic_report(event.message)
            elif event.kind == "diagnostic_error":
                messagebox.showerror(
                    "Falha ao gerar diagnóstico",
                    f"Não foi possível preparar o relatório ({event.message}).",
                    parent=self.root,
                )
            elif event.kind == "qualities":
                if (
                    event.job_id == self._quality_request_id
                    and event.preview is not None
                ):
                    if event.preview.qualities:
                        options = ["best"] + [
                            f"{height}p" for height in event.preview.qualities
                        ]
                        self.quality_menu.configure(values=options)
                    self.status_label.configure(text=event.message)
            elif event.kind == "quality_error":
                if (
                    event.job_id == self._quality_request_id
                    and event.error is not None
                ):
                    self.status_label.configure(
                        text=(
                            "Prévia indisponível; as qualidades padrão permanecem. "
                            f"({type(event.error).__name__})"
                        )
                    )
            elif event.kind == "progress" and self._active_job is not None:
                if event.job_id == self._active_job.job_id:
                    self.progress.set(min(1.0, max(0.0, event.progress / 100)))
                    if event.progress >= 100:
                        self.status_label.configure(
                            text="Finalizando arquivo ou conversão..."
                        )
            elif event.kind == "preview_ready" and self._active_job is not None:
                if event.job_id == self._active_job.job_id:
                    self._handle_preview(event)
            elif event.kind == "job_done" and self._active_job is not None:
                if event.job_id == self._active_job.job_id:
                    self._handle_job_done(event)
            elif event.kind == "job_error" and self._active_job is not None:
                if event.job_id == self._active_job.job_id:
                    self._handle_job_error(event)
            elif event.kind == "retry":
                self._handle_retry(event)
        self.root.after(100, self._drain_events)
