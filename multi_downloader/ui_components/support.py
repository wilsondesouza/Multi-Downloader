from __future__ import annotations

from typing import TYPE_CHECKING

import threading
import re

from multi_downloader.service import (
    check_dependency_updates,
    check_ffmpeg,
    is_update_available,
)
from multi_downloader.ui_components.models import _UIEvent

if TYPE_CHECKING:
    from multi_downloader.ui import MultiDownloaderApp


class SupportMixin:

    def _check_ffmpeg(self: MultiDownloaderApp) -> None:
        def worker() -> None:
            try:
                version = check_ffmpeg()
                
                if version:
                    # Captura os 8 dígitos de data precedidos por hífen
                    match_date = re.search(r'-(\d{8})\b', version)
                    if match_date:
                        version = match_date.group(1)
                    else:
                        # Fallback de segurança para releases estáveis sem data (ex: captura "7.1" em "ffmpeg version 7.1")
                        match_stable = re.search(r'version\s+([a-zA-Z0-9.-]+)', version)
                        version = match_stable.group(1) if match_stable else version

                message = (
                    f"FFmpeg: {version}"
                    if version
                    else "FFmpeg não encontrado (necessário para MP3)"
                )
            except Exception as exc:
                message = f"FFmpeg: verificação falhou ({type(exc).__name__})"
            
            self._events.put(_UIEvent(kind="ffmpeg", message=message))

        threading.Thread(target=worker, daemon=True).start()


    def _check_updates(self: MultiDownloaderApp) -> None:
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
