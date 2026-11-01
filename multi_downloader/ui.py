from __future__ import annotations

import ctypes
import logging
import os
import queue
import subprocess
import sys
import threading
import webbrowser
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import BooleanVar, PhotoImage, StringVar, filedialog, messagebox

import customtkinter as ctk

from multi_downloader.diagnostics import (
    create_diagnostic_report,
    sanitize_error_details,
    save_diagnostic_report,
)
from multi_downloader.persistence import (
    AppSettings,
    AppStore,
    HistoryRecord,
)
from multi_downloader.service import (
    DownloadCancelledError,
    DownloadControl,
    DownloadRequest,
    DownloadResult,
    MediaPreview,
    URLValidationError,
    check_dependency_updates,
    check_ffmpeg,
    create_download_request,
    download_media,
    is_update_available,
    parse_media_url,
    preview_media,
)

_DEFAULT_QUALITY_OPTIONS = ["best", "1080p", "720p", "480p", "360p"]
_APP_USER_MODEL_ID = "WilsonSouza.MultiDownloader"
_LOGGER = logging.getLogger(__name__)
_MAX_BATCH_SIZE = 50


def resource_path(relative_path: str) -> Path:
    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory:
        return Path(bundle_directory) / relative_path
    return Path(__file__).resolve().parent.parent / relative_path


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


class MultiDownloaderApp:
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

    def _set_window_icon(self) -> None:
        png_path = resource_path("assets/images/icon.png")
        if not png_path.is_file():
            raise FileNotFoundError(f"Application icon not found: {png_path}")
        self._window_icon = PhotoImage(master=self.root, file=str(png_path))
        self.root.iconphoto(True, self._window_icon)
        if sys.platform == "win32":
            ico_path = resource_path("assets/images/icon.ico")
            if not ico_path.is_file():
                raise FileNotFoundError(f"Windows application icon not found: {ico_path}")
            self.root.iconbitmap(str(ico_path))

    def _build_widgets(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(
            self.root,
            text="Multi Downloader",
            font=("Helvetica", 22, "bold"),
            text_color="cyan",
        ).grid(row=0, column=0, padx=20, pady=(16, 5), sticky="w")
        ctk.CTkLabel(
            self.root,
            text="Baixe apenas mídias públicas que você tem autorização para salvar.",
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 5), sticky="ew")

        url_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        url_frame.grid(row=2, column=0, padx=20, pady=4, sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(
            url_frame,
            textvariable=self.url_var,
            placeholder_text="Cole um link de YouTube, Instagram, X ou Facebook",
            height=38,
        )
        self.url_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            url_frame,
            text="Colar",
            width=72,
            command=self._paste_url,
        ).grid(row=0, column=1, padx=(0, 8))
        self.download_button = ctk.CTkButton(
            url_frame,
            text="Adicionar à fila",
            width=132,
            command=self._start_download,
        )
        self.download_button.grid(row=0, column=2)

        ctk.CTkButton(
            self.root,
            text="Adicionar vários links (um por linha)",
            command=self._open_batch_dialog,
            fg_color="transparent",
            border_width=1,
        ).grid(row=3, column=0, padx=20, pady=4, sticky="w")

        options_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        options_frame.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        ctk.CTkLabel(options_frame, text="Formato:").grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )
        self.format_mp4 = ctk.CTkRadioButton(
            options_frame,
            text="MP4",
            variable=self.format_var,
            value="mp4",
            command=self._on_format_change,
        )
        self.format_mp4.grid(row=0, column=1, padx=6)
        self.format_mp3 = ctk.CTkRadioButton(
            options_frame,
            text="MP3",
            variable=self.format_var,
            value="mp3",
            command=self._on_format_change,
        )
        self.format_mp3.grid(row=0, column=2, padx=6)
        ctk.CTkLabel(options_frame, text="Qualidade:").grid(
            row=0, column=3, padx=(18, 8), sticky="e"
        )
        self.quality_menu = ctk.CTkOptionMenu(
            options_frame,
            variable=self.quality_var,
            values=_DEFAULT_QUALITY_OPTIONS.copy(),
            width=120,
        )
        self.quality_menu.grid(row=0, column=4, sticky="e")
        ctk.CTkButton(
            options_frame,
            text="Preferências",
            width=110,
            command=self._open_settings_dialog,
            fg_color="transparent",
            border_width=1,
        ).grid(row=0, column=5, padx=(18, 0))
        options_frame.grid_columnconfigure(3, weight=1)

        destination_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        destination_frame.grid(row=5, column=0, padx=20, pady=3, sticky="ew")
        destination_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(destination_frame, text="Destino:").grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )
        ctk.CTkLabel(
            destination_frame,
            textvariable=self.download_directory_var,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(
            destination_frame,
            text="Escolher pasta",
            width=112,
            command=self._choose_directory,
        ).grid(row=0, column=2, padx=(8, 0))

        self.progress = ctk.CTkProgressBar(self.root, height=12)
        self.progress.grid(row=6, column=0, padx=20, pady=(6, 2), sticky="ew")
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(self.root, text="Pronto", anchor="w")
        self.status_label.grid(row=7, column=0, padx=20, pady=(0, 5), sticky="ew")

        controls = ctk.CTkFrame(self.root, fg_color="transparent")
        controls.grid(row=8, column=0, padx=20, pady=4, sticky="ew")
        self.pause_button = ctk.CTkButton(
            controls,
            text="Pausar",
            command=self._toggle_pause,
            state="disabled",
            width=90,
        )
        self.pause_button.pack(side="left", padx=(0, 6))
        self.cancel_button = ctk.CTkButton(
            controls,
            text="Cancelar",
            command=self._cancel_active,
            state="disabled",
            width=100,
            fg_color="#8b2525",
        )
        self.cancel_button.pack(side="left", padx=6)
        ctk.CTkButton(
            controls,
            text="Limpar fila",
            command=self._clear_queue,
            width=100,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            controls,
            text="Copiar detalhes do erro",
            command=self._copy_error_details,
            width=170,
        ).pack(side="left", padx=6)
        self.ffmpeg_label = ctk.CTkLabel(controls, text="Verificando FFmpeg...")
        self.ffmpeg_label.pack(side="right", padx=(6, 0))

        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.grid(row=10, column=0, padx=20, pady=(5, 10), sticky="nsew")
        queue_tab = self.tabs.add("Fila")
        history_tab = self.tabs.add("Histórico e suporte")

        queue_tab.grid_columnconfigure(0, weight=1)
        queue_tab.grid_rowconfigure(0, weight=1)
        self.queue_area = ctk.CTkTextbox(queue_tab, wrap="word")
        self.queue_area.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.queue_area.configure(state="disabled")
        self._refresh_queue_view()

        history_tab.grid_columnconfigure(0, weight=1)
        history_tab.grid_rowconfigure(1, weight=1)
        history_controls = ctk.CTkFrame(history_tab, fg_color="transparent")
        history_controls.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        history_controls.grid_columnconfigure(0, weight=1)
        self.history_menu = ctk.CTkOptionMenu(
            history_controls,
            values=["Nenhum download no histórico"],
        )
        self.history_menu.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(
            history_controls,
            text="Mostrar arquivo",
            command=self._open_selected_history_file,
            width=100,
        ).grid(row=0, column=1, padx=3)
        ctk.CTkButton(
            history_controls,
            text="Atualizar dependências",
            command=self._check_updates,
            width=152,
        ).grid(row=0, column=2, padx=3)
        ctk.CTkButton(
            history_controls,
            text="Exportar diagnóstico",
            command=self._review_diagnostics,
            width=145,
        ).grid(row=0, column=3, padx=(3, 0))
        self.history_area = ctk.CTkTextbox(history_tab, wrap="word")
        self.history_area.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.history_area.configure(state="disabled")

        self.root.bind("<F5>", lambda _event: self._check_updates())
        self.root.bind("<Control-Shift-D>", lambda _event: self._review_diagnostics())

    def run(self) -> None:
        self.root.mainloop()

    def _paste_url(self) -> None:
        try:
            clipboard = self.root.clipboard_get()
        except Exception as exc:
            messagebox.showerror(
                "Área de transferência indisponível",
                f"Não foi possível ler o conteúdo ({type(exc).__name__}).",
                parent=self.root,
            )
            return
        self.url_var.set(clipboard.strip())
        self.url_entry.focus_set()

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            initialdir=self.download_directory_var.get(),
            mustexist=True,
        )
        if selected:
            self.download_directory_var.set(selected)
            self._save_preferences()

    def _open_settings_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Preferências")
        dialog.geometry("440x350")
        dialog.transient(self.root)
        dialog.grab_set()

        quality = StringVar(value=self.quality_var.get())
        retries = StringVar(value=self.retries_var.get())
        overwrite = BooleanVar(value=self.confirm_overwrite_var.get())
        update_startup = BooleanVar(value=self.check_updates_startup_var.get())

        ctk.CTkLabel(dialog, text="Qualidade padrão").pack(
            padx=18, pady=(18, 4), anchor="w"
        )
        ctk.CTkOptionMenu(
            dialog,
            variable=quality,
            values=_DEFAULT_QUALITY_OPTIONS.copy(),
        ).pack(padx=18, anchor="w")
        ctk.CTkLabel(dialog, text="Novas tentativas automáticas (0–5)").pack(
            padx=18, pady=(14, 4), anchor="w"
        )
        ctk.CTkOptionMenu(
            dialog,
            variable=retries,
            values=[str(value) for value in range(6)],
        ).pack(padx=18, anchor="w")
        ctk.CTkCheckBox(
            dialog,
            text="Perguntar antes de substituir um arquivo",
            variable=overwrite,
        ).pack(padx=18, pady=(14, 4), anchor="w")
        ctk.CTkCheckBox(
            dialog,
            text="Consultar atualizações ao iniciar (usa a rede)",
            variable=update_startup,
        ).pack(padx=18, pady=4, anchor="w")

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(side="bottom", padx=18, pady=18, fill="x")
        ctk.CTkButton(
            buttons,
            text="Cancelar",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
        ).pack(side="right", padx=(6, 0))

        def save() -> None:
            try:
                max_retries = int(retries.get())
                if not 0 <= max_retries <= 5:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Preferências inválidas",
                    "O limite de tentativas deve ficar entre 0 e 5.",
                    parent=dialog,
                )
                return
            self.quality_var.set(quality.get())
            self.retries_var.set(str(max_retries))
            self.confirm_overwrite_var.set(overwrite.get())
            self.check_updates_startup_var.set(update_startup.get())
            self._save_preferences()
            dialog.destroy()

        ctk.CTkButton(buttons, text="Salvar", command=save).pack(side="right")

    def _save_preferences(self) -> None:
        self.settings = AppSettings(
            download_directory=self.download_directory_var.get().strip(),
            default_quality=self.quality_var.get(),
            confirm_overwrite=self.confirm_overwrite_var.get(),
            max_retries=int(self.retries_var.get()),
            check_updates_on_startup=self.check_updates_startup_var.get(),
        )
        self.store.save_settings(self.settings)

    def _open_batch_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Adicionar downloads em lote")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            dialog,
            text=f"Um link por linha (máximo de {_MAX_BATCH_SIZE}).",
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=10, sticky="ew")
        links = ctk.CTkTextbox(dialog, wrap="word")
        links.grid(row=1, column=0, padx=14, pady=5, sticky="nsew")
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=2, column=0, padx=14, pady=10, sticky="e")
        ctk.CTkButton(
            actions,
            text="Cancelar",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
        ).pack(side="right", padx=(6, 0))

        def enqueue_batch() -> None:
            batch_urls = [
                line.strip()
                for line in links.get("1.0", "end").splitlines()
                if line.strip()
            ]
            if not batch_urls:
                messagebox.showerror(
                    "Nenhum link",
                    "Cole pelo menos um link.",
                    parent=dialog,
                )
                return
            if len(batch_urls) > _MAX_BATCH_SIZE:
                messagebox.showerror(
                    "Lote muito grande",
                    f"O limite é de {_MAX_BATCH_SIZE} links por lote.",
                    parent=dialog,
                )
                return

            accepted, rejected = self._enqueue_batch_urls(batch_urls)
            dialog.destroy()
            if rejected:
                messagebox.showwarning(
                    "Lote parcialmente adicionado",
                    f"{accepted} links adicionados; {len(rejected)} links inválidos foram ignorados.",
                    parent=self.root,
                )

        ctk.CTkButton(
            actions,
            text="Adicionar à fila",
            command=enqueue_batch,
        ).pack(side="right")

    def _enqueue_batch_urls(self, urls: list[str]) -> tuple[int, list[str]]:
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

    def _create_request(self, url: str) -> DownloadRequest:
        destination_root = Path(self.download_directory_var.get()).expanduser()
        if not destination_root.is_absolute():
            raise ValueError("Escolha um diretório de destino absoluto.")
        return create_download_request(
            url,
            self.format_var.get(),
            self.quality_var.get(),
            destination=destination_root,
        )

    def _start_download(self) -> None:
        try:
            request = self._create_request(self.url_var.get())
        except (URLValidationError, ValueError) as exc:
            messagebox.showerror("Link inválido", str(exc), parent=self.root)
            return
        self._enqueue_request(request)
        self.url_var.set("")
        self._start_next_job()

    def _enqueue_request(self, request: DownloadRequest) -> None:
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

    def _start_next_job(self) -> None:
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
        self.status_label.configure(text=f"Consultando mídia em {job.request.provider}...")
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

    def _run_active_download(self, job: _DownloadJob) -> None:
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

    def _handle_preview(self, event: _UIEvent) -> None:
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

    def _log_history_preview(self, job: _DownloadJob, preview: MediaPreview) -> None:
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

    def _handle_job_error(self, event: _UIEvent) -> None:
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

    def _show_error_details(self, details: str) -> None:
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Falha no download")
        dialog.geometry("560x260")
        dialog.transient(self.root)
        ctk.CTkLabel(
            dialog,
            text=(
                "Verifique a conexão e se a mídia está pública. "
                "Os detalhes abaixo removem links e valores de credenciais."
            ),
            wraplength=520,
            justify="left",
        ).pack(padx=14, pady=(14, 8), anchor="w")
        textbox = ctk.CTkTextbox(dialog, height=100, wrap="word")
        textbox.pack(padx=14, pady=4, fill="both", expand=True)
        textbox.insert("1.0", details)
        textbox.configure(state="disabled")
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(padx=14, pady=10, fill="x")
        ctk.CTkButton(
            actions,
            text="Copiar detalhes",
            command=self._copy_error_details,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Fechar",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
        ).pack(side="right")

    def _handle_job_done(self, event: _UIEvent) -> None:
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

    def _finish_active_job(self) -> None:
        self._active_job = None
        self.pause_button.configure(state="disabled", text="Pausar")
        self.cancel_button.configure(state="disabled", text="Cancelar")
        self.progress.set(0)
        self._refresh_queue_view()
        if self._cancel_queue_after_current:
            self._cancel_queue_after_current = False
            self._clear_queue()
        self._start_next_job()

    def _toggle_pause(self) -> None:
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

    def _cancel_active(self) -> None:
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
                text="A fila parará quando a transferência atual do Instagram terminar."
            )
            return
        if job.control is not None:
            job.control.cancel()
            self.status_label.configure(text="Cancelando...")

    def _clear_queue(self) -> None:
        while self._pending_jobs:
            job = self._pending_jobs.popleft()
            self.store.update_history_record(
                job.history_id,
                status="cancelled",
                error_code="RemovedFromQueue",
            )
        self._refresh_queue_view()
        self._refresh_history()

    def _handle_retry(self, event: _UIEvent) -> None:
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

    def _drain_events(self) -> None:
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
                if event.job_id == self._quality_request_id and event.preview is not None:
                    if event.preview.qualities:
                        options = ["best"] + [
                            f"{height}p" for height in event.preview.qualities
                        ]
                        self.quality_menu.configure(values=options)
                    self.status_label.configure(text=event.message)
            elif event.kind == "quality_error":
                if event.job_id == self._quality_request_id and event.error is not None:
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

    def _check_ffmpeg(self) -> None:
        def worker() -> None:
            try:
                version = check_ffmpeg()
                message = (
                    f"FFmpeg: {version}"
                    if version
                    else "FFmpeg não encontrado (necessário para MP3)"
                )
            except Exception as exc:
                message = f"FFmpeg: verificação falhou ({type(exc).__name__})"
            self._events.put(_UIEvent(kind="ffmpeg", message=message))

        threading.Thread(target=worker, daemon=True).start()

    def _check_updates(self) -> None:
        self.status_label.configure(text="Consultando versões no PyPI...")

        def worker() -> None:
            try:
                updates = check_dependency_updates()
                lines = []
                for package, (installed, latest) in updates.items():
                    if latest.startswith("unavailable:"):
                        lines.append(f"{package}: {latest}")
                    else:
                        status = (
                            "atualização disponível"
                            if is_update_available(installed, latest)
                            else "atualizada"
                        )
                        lines.append(
                            f"{package}: instalada {installed}; atual {latest} "
                            f"({status})"
                        )
                self._events.put(
                    _UIEvent(
                        kind="updates",
                        message="\n".join(lines) or "Nenhuma dependência encontrada.",
                    )
                )
            except Exception as exc:
                self._events.put(
                    _UIEvent(
                        kind="updates",
                        message=f"Falha ao consultar versões: {type(exc).__name__}",
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def _show_update_results(self, text: str) -> None:
        self.status_label.configure(text="Verificação de atualizações concluída")
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Atualizações de dependências")
        dialog.geometry("540x320")
        dialog.transient(self.root)
        ctk.CTkLabel(
            dialog,
            text=(
                "Consulta manual ao PyPI. O aplicativo não instala atualizações "
                "automaticamente."
            ),
            wraplength=500,
            justify="left",
        ).pack(padx=14, pady=(14, 6), anchor="w")
        result_box = ctk.CTkTextbox(dialog, height=150)
        result_box.pack(padx=14, pady=6, fill="both", expand=True)
        result_box.insert("1.0", text)
        result_box.configure(state="disabled")
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(padx=14, pady=10, fill="x")
        ctk.CTkButton(
            buttons,
            text="Abrir instruções de instalação",
            command=lambda: webbrowser.open(
                "https://github.com/wilsondesouza/Multi-Downloader#instalação"
            ),
        ).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Fechar",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
        ).pack(side="right")

    def _review_diagnostics(self) -> None:
        self.status_label.configure(text="Preparando diagnóstico...")

        def worker() -> None:
            try:
                report = create_diagnostic_report(self.store)
            except Exception as exc:
                self._events.put(
                    _UIEvent(
                        kind="diagnostic_error",
                        message=type(exc).__name__,
                    )
                )
                return
            self._events.put(_UIEvent(kind="diagnostic", message=report))

        threading.Thread(target=worker, daemon=True).start()

    def _show_diagnostic_report(self, report: str) -> None:
        self.status_label.configure(text="Revise o diagnóstico antes de salvar")
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Revisar diagnóstico")
        dialog.geometry("650x500")
        dialog.transient(self.root)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            dialog,
            text=(
                "Revise antes de salvar. O relatório exclui URLs, query strings, "
                "nomes de usuário e caminhos locais."
            ),
            wraplength=610,
            justify="left",
        ).grid(row=0, column=0, padx=14, pady=10, sticky="w")
        preview = ctk.CTkTextbox(dialog, wrap="none")
        preview.grid(row=1, column=0, padx=14, pady=5, sticky="nsew")
        preview.insert("1.0", report)
        preview.configure(state="disabled")
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=2, column=0, padx=14, pady=10, sticky="ew")
        ctk.CTkButton(
            actions,
            text="Salvar relatório...",
            command=lambda: self._save_report(report),
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Fechar",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
        ).pack(side="right")

    def _save_report(self, report: str) -> None:
        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar diagnóstico revisado",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos os arquivos", "*.*")],
        )
        if not destination:
            return
        try:
            save_diagnostic_report(report, Path(destination))
        except OSError as exc:
            messagebox.showerror(
                "Erro ao salvar",
                f"Não foi possível salvar o relatório ({type(exc).__name__}).",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "Diagnóstico salvo",
            "O relatório revisado foi salvo no local escolhido.",
            parent=self.root,
        )

    def _copy_error_details(self) -> None:
        if not self._last_error_details:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._last_error_details)
        self.status_label.configure(text="Detalhes técnicos copiados")

    def _refresh_queue_view(self) -> None:
        if not hasattr(self, "queue_area"):
            return
        lines: list[str] = []
        if self._active_job is not None:
            state = "em andamento"
            if self._active_job.control and self._active_job.control.is_paused:
                state = "pausado"
            lines.append(
                f"● {self._active_job.request.provider} — "
                f"{self._active_job.title} ({state})"
            )
        for index, job in enumerate(self._pending_jobs, start=1):
            lines.append(
                f"{index}. {job.request.provider} — {job.request.media_format.upper()} "
                f"({job.title})"
            )
        if not lines:
            lines.append("A fila está vazia.")
        self.queue_area.configure(state="normal")
        self.queue_area.delete("1.0", "end")
        self.queue_area.insert("1.0", "\n".join(lines))
        self.queue_area.configure(state="disabled")

    def _refresh_history(self) -> None:
        if not hasattr(self, "history_area"):
            return
        records = self.store.list_history(limit=100)
        self._history_options = {}
        labels: list[str] = []
        lines: list[str] = []
        for record in records:
            stamp = record.created_at.replace("T", " ")[:19]
            label = f"{stamp} | {record.status} | {record.title}"
            labels.append(label)
            self._history_options[label] = record
            lines.append(
                f"{stamp}  {record.status.upper()}  {record.provider} "
                f"{record.media_format.upper()}  {record.title}\n"
                f"  Arquivo: {record.output_path or 'ainda não definido'}\n"
                f"  Tentativas: {record.attempts}"
                + (f"  |  Erro: {record.error_code}" if record.error_code else "")
            )
        values = labels or ["Nenhum download no histórico"]
        self.history_menu.configure(values=values)
        self.history_menu.set(values[0])
        self.history_area.configure(state="normal")
        self.history_area.delete("1.0", "end")
        self.history_area.insert(
            "1.0",
            "\n\n".join(lines) if lines else "O histórico está vazio.",
        )
        self.history_area.configure(state="disabled")

    def _open_selected_history_file(self) -> None:
        record = self._history_options.get(self.history_menu.get())
        if record is None or not record.output_path:
            messagebox.showinfo(
                "Arquivo indisponível",
                "Este registro ainda não tem um arquivo de saída.",
                parent=self.root,
            )
            return
        path = Path(record.output_path)
        if not path.exists():
            messagebox.showerror(
                "Arquivo não encontrado",
                "O arquivo do histórico não está mais disponível.",
                parent=self.root,
            )
            return
        if path.is_dir():
            self._open_directory(path)
        else:
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", f"/select,{path}"])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", os.fspath(path)])
                else:
                    self._open_directory(path.parent)
            except OSError as exc:
                self.status_label.configure(
                    text=f"Não foi possível mostrar o arquivo ({type(exc).__name__})."
                )

    def _log_history(self, message: str) -> None:
        self.status_label.configure(text=message)
        self._refresh_history()

    def _open_directory(self, directory: Path) -> bool:
        try:
            if sys.platform == "win32":
                startfile = getattr(os, "startfile", None)
                if startfile is None:
                    raise OSError("O recurso do sistema não está disponível.")
                startfile(os.fspath(directory))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", os.fspath(directory)])
            else:
                subprocess.Popen(["xdg-open", os.fspath(directory)])
        except OSError as exc:
            self.status_label.configure(
                text=f"Não foi possível abrir a pasta ({type(exc).__name__})."
            )
            return False
        return True

    @staticmethod
    def _format_duration(duration: float) -> str:
        seconds = max(0, int(duration))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"{hours}:{minutes:02}:{seconds:02}"
            if hours
            else f"{minutes}:{seconds:02}"
        )

    def _on_url_change(self, *_: object) -> None:
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

    def _set_instagram_mode(self, enabled: bool) -> None:
        state = "disabled" if enabled else "normal"
        self.format_mp3.configure(state=state)
        self.format_mp4.configure(state=state)
        if enabled:
            self.format_var.set("mp4")
        self.quality_menu.configure(
            state=(
                "normal"
                if not enabled and self.format_var.get() == "mp4"
                else "disabled"
            )
        )

    def _on_format_change(self) -> None:
        self.quality_menu.configure(
            state="normal" if self.format_var.get() == "mp4" else "disabled"
        )
        if self.format_var.get() == "mp4":
            self._on_url_change()

    def _request_qualities(self, url: str, request_id: int) -> None:
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
