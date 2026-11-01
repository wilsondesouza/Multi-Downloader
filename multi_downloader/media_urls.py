from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from multi_downloader.media_models import (
    DownloadRequest,
    MediaFormat,
    ParsedMediaURL,
    Provider,
    URLValidationError,
)

_HOST_PROVIDERS: dict[str, Provider] = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "instagram.com": "Instagram",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
}
_QUALITY_PATTERN = re.compile(r"^(?:best|[1-9]\d{0,3}p)$")
_INSTAGRAM_SHORTCODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_INSTAGRAM_POST_TYPES = {"p", "reel", "reels", "tv"}


def _normalize_twitter_path(path: str) -> str:
    parts = path.split("/")
    if len(parts) > 3 and parts[2].lower() == "status" and parts[1] != "i":
        parts[1] = "i"
        return "/".join(parts)
    return path


def parse_media_url(url: str) -> ParsedMediaURL:
    candidate = url.strip()
    if not candidate or any(ord(char) < 32 for char in candidate):
        raise URLValidationError("Insira uma URL válida.")

    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise URLValidationError("A URL informada está malformada.") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not hostname:
        raise URLValidationError(
            "Use uma URL HTTP ou HTTPS de uma plataforma suportada."
        )
    if port is not None and port != (443 if scheme == "https" else 80):
        raise URLValidationError("A URL usa uma porta não padrão.")
    if parsed.username is not None or parsed.password is not None:
        raise URLValidationError("URLs com credenciais embutidas não são permitidas.")

    hostname = hostname.lower().rstrip(".")
    provider = next(
        (
            supported_provider
            for domain, supported_provider in _HOST_PROVIDERS.items()
            if hostname == domain or hostname.endswith(f".{domain}")
        ),
        None,
    )
    if provider is None:
        raise URLValidationError("A plataforma desta URL não é suportada.")

    shortcode = None
    if provider == "Instagram":
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) < 2 or path_parts[0].lower() not in _INSTAGRAM_POST_TYPES:
            raise URLValidationError(
                "Informe o link direto de um post, reel ou IGTV público do Instagram."
            )
        shortcode = path_parts[1]
        if not _INSTAGRAM_SHORTCODE_PATTERN.fullmatch(shortcode):
            raise URLValidationError(
                "O link do Instagram contém um identificador inválido."
            )
    elif provider == "Twitter":
        parsed = parsed._replace(path=_normalize_twitter_path(parsed.path))

    return ParsedMediaURL(provider, urlunsplit(parsed), shortcode)


def create_download_request(
    url: str,
    media_format: str,
    quality: str = "best",
    destination: Path | None = None,
    overwrite: bool = False,
) -> DownloadRequest:
    parsed = parse_media_url(url)
    if media_format not in {"mp3", "mp4"}:
        raise ValueError("Selecione um formato MP3 ou MP4.")
    if parsed.provider == "Instagram" and media_format != "mp4":
        raise ValueError("O Instagram está disponível somente no formato MP4.")
    if not _QUALITY_PATTERN.fullmatch(quality):
        raise ValueError("A qualidade selecionada é inválida.")
    if quality != "best" and not 1 <= int(quality[:-1]) <= 4320:
        raise ValueError("A qualidade selecionada está fora do intervalo permitido.")

    selected_format: MediaFormat = "mp3" if media_format == "mp3" else "mp4"
    return DownloadRequest(
        parsed.url,
        parsed.provider,
        selected_format,
        quality if selected_format == "mp4" else "best",
        destination,
        overwrite,
    )
