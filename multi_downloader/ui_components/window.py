from __future__ import annotations

from typing import TYPE_CHECKING

import sys
from tkinter import PhotoImage

import customtkinter as ctk

from multi_downloader.ui_components.constants import _DEFAULT_QUALITY_OPTIONS
from multi_downloader.ui_components.resources import resource_path

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class WindowMixin:

    def _set_window_icon(self: MultiDownloaderApp) -> None:
        png_path = resource_path("assets/images/icon.png")
        if not png_path.is_file():
            raise FileNotFoundError(f"Application icon not found: {png_path}")
        self._window_icon = PhotoImage(master=self.root, file=str(png_path))
        self.root.iconphoto(True, self._window_icon)
        if sys.platform == "win32":
            ico_path = resource_path("assets/images/icon.ico")
            if not ico_path.is_file():
                raise FileNotFoundError(
                    f"Windows application icon not found: {ico_path}"
                )
            self.root.iconbitmap(str(ico_path))


    def _build_widgets(self: MultiDownloaderApp) -> None:
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


    def _refresh_queue_view(self: MultiDownloaderApp) -> None:
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
                f"{index}. {job.request.provider} — "
                f"{job.request.media_format.upper()} "
                f"({job.title})"
            )
        if not lines:
            lines.append("A fila está vazia.")
        self.queue_area.configure(state="normal")
        self.queue_area.delete("1.0", "end")
        self.queue_area.insert("1.0", "\n".join(lines))
        self.queue_area.configure(state="disabled")


    def _refresh_history(self: MultiDownloaderApp) -> None:
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


    def _set_instagram_mode(self: MultiDownloaderApp, enabled: bool) -> None:
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
