from __future__ import annotations

from typing import TYPE_CHECKING

import threading
import webbrowser
from pathlib import Path
from tkinter import BooleanVar, StringVar, filedialog, messagebox

import customtkinter as ctk

from multi_downloader.diagnostics import (
    create_diagnostic_report,
    save_diagnostic_report,
)
from multi_downloader.persistence import AppSettings
from multi_downloader.ui_components.constants import (
    _DEFAULT_QUALITY_OPTIONS,
    _MAX_BATCH_SIZE,
)
from multi_downloader.ui_components.models import _UIEvent

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class DialogsMixin:

    def _paste_url(self: MultiDownloaderApp) -> None:
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


    def _choose_directory(self: MultiDownloaderApp) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            initialdir=self.download_directory_var.get(),
            mustexist=True,
        )
        if selected:
            self.download_directory_var.set(selected)
            self._save_preferences()


    def _open_settings_dialog(self: MultiDownloaderApp) -> None:
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


    def _save_preferences(self: MultiDownloaderApp) -> None:
        self.settings = AppSettings(
            download_directory=self.download_directory_var.get().strip(),
            default_quality=self.quality_var.get(),
            confirm_overwrite=self.confirm_overwrite_var.get(),
            max_retries=int(self.retries_var.get()),
            check_updates_on_startup=self.check_updates_startup_var.get(),
        )
        self.store.save_settings(self.settings)


    def _open_batch_dialog(self: MultiDownloaderApp) -> None:
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
                    f"{accepted} links adicionados; "
                    f"{len(rejected)} links inválidos foram ignorados.",
                    parent=self.root,
                )

        ctk.CTkButton(
            actions,
            text="Adicionar à fila",
            command=enqueue_batch,
        ).pack(side="right")


    def _show_error_details(self: MultiDownloaderApp, details: str) -> None:
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


    def _show_update_results(self: MultiDownloaderApp, text: str) -> None:
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


    def _review_diagnostics(self: MultiDownloaderApp) -> None:
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


    def _show_diagnostic_report(self: MultiDownloaderApp, report: str) -> None:
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


    def _save_report(self: MultiDownloaderApp, report: str) -> None:
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


    def _copy_error_details(self: MultiDownloaderApp) -> None:
        if not self._last_error_details:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._last_error_details)
        self.status_label.configure(text="Detalhes técnicos copiados")
