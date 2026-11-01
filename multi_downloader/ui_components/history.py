from __future__ import annotations

from typing import TYPE_CHECKING

import os
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class HistoryMixin:

    def _open_selected_history_file(self: MultiDownloaderApp) -> None:
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


    def _log_history(self: MultiDownloaderApp, message: str) -> None:
        self.status_label.configure(text=message)
        self._refresh_history()


    def _open_directory(self: MultiDownloaderApp, directory: Path) -> bool:
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
