from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import instaloader
import yt_dlp

from multi_downloader.media_models import (
    DownloadCancelledError,
    DownloadControl,
    DownloadRequest,
    DownloadResult,
    MediaPreview,
    ParsedMediaURL,
    ProgressCallback,
    Provider,
    URLValidationError,
)
from multi_downloader.media_urls import create_download_request, parse_media_url

_OUTPUT_DIRECTORIES: dict[Provider, str] = {
    "YouTube": "downloads/downloads-Youtube",
    "Instagram": "downloads/downloads-Instagram",
    "Twitter": "downloads/downloads-Twitter",
    "Facebook": "downloads/downloads-Facebook",
}


def preview_media(request: DownloadRequest) -> MediaPreview:
    parsed = parse_media_url(request.url)
    if parsed.provider == "Instagram":
        output_directory = _output_directory(request)
        loader = instaloader.Instaloader(
            dirname_pattern=str(output_directory),
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
            filename_pattern="{owner_username} - {mediaid}",
        )
        if parsed.shortcode is None:
            raise URLValidationError(
                "Não foi possível identificar o post do Instagram."
            )
        post = instaloader.Post.from_shortcode(loader.context, parsed.shortcode)
        sidecar_video_indexes = (
            [
                index
                for index, contains_video in enumerate(post.get_is_videos(), start=1)
                if contains_video
            ]
            if post.typename == "GraphSidecar"
            else []
        )
        if not post.is_video and not sidecar_video_indexes:
            raise ValueError("O post do Instagram não contém vídeo.")
        output_path = Path(
            loader.format_filename(post, target=output_directory.name)
        )
        if not output_path.is_absolute():
            output_path = output_directory / output_path.name
        output_paths = (
            [output_path.with_suffix(".mp4")]
            if post.is_video
            else [
                output_path.with_name(f"{output_path.stem}_{index}.mp4")
                for index in sidecar_video_indexes
            ]
        )
        existing_output = next(
            (path for path in output_paths if path.exists()),
            output_paths[0],
        )
        return MediaPreview(
            f"Post de {post.owner_username}",
            None,
            [],
            existing_output,
        )

    options = _yt_dlp_options(request, _output_directory(request))
    options.update({"quiet": True, "no_warnings": True, "skip_download": True})
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(parsed.url, download=False)
        if not isinstance(info, dict):
            raise RuntimeError("A biblioteca não retornou os dados da mídia.")
        output_path = Path(downloader.prepare_filename(info))
        if request.media_format == "mp3":
            output_path = output_path.with_suffix(".mp3")
        elif info.get("ext") != "mp4":
            output_path = output_path.with_suffix(".mp4")
        if request.provider == "Twitter":
            output_path = output_path.with_name(
                output_path.name.encode("ascii", "ignore").decode("ascii")
            )
        return MediaPreview(
            str(info.get("title") or "Mídia"),
            _as_number(info.get("duration")),
            _available_qualities(info),
            output_path,
        )


def get_video_qualities(url: str) -> list[int]:
    request = create_download_request(url, "mp4")
    return preview_media(request).qualities


def _available_qualities(info: dict[str, object]) -> list[int]:
    formats = info.get("formats", [])
    if not isinstance(formats, list):
        return []
    heights = {
        item["height"]
        for item in formats
        if isinstance(item, dict)
        and isinstance(item.get("height"), int)
        and item["height"] > 0
    }
    return sorted(heights)


def _as_number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _output_directory(request: DownloadRequest) -> Path:
    root = request.destination or Path.cwd()
    return root / _OUTPUT_DIRECTORIES[request.provider]


def _yt_dlp_options(
    request: DownloadRequest,
    output_directory: Path,
    progress_callback: ProgressCallback | None = None,
    control: DownloadControl | None = None,
) -> dict[str, object]:
    is_audio = request.media_format == "mp3"
    prefix = "mp3_" if is_audio else f"mp4_{request.quality}_"
    options: dict[str, object] = {
        "outtmpl": str(output_directory / f"{prefix}%(title)s.%(ext)s"),
        "cachedir": False,
        "noplaylist": True,
        "nooverwrites": not request.overwrite,
        "format": (
            "bestaudio/best"
            if is_audio
            else (
                f"bestvideo[height<={request.quality[:-1]}]+bestaudio/best"
                if request.quality != "best"
                else "bestvideo+bestaudio/best"
            )
        ),
        "postprocessors": (
            [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
            if is_audio
            else []
        ),
    }
    if not is_audio:
        options["merge_output_format"] = "mp4"
    if request.provider == "Twitter":
        options.update({"restrictfilenames": True, "trim_file_name": 50})
    if progress_callback is not None or control is not None:
        def hook(status: dict[str, object]) -> None:
            if control is not None:
                try:
                    control.wait_until_resumed()
                except DownloadCancelledError as exc:
                    raise yt_dlp.utils.DownloadCancelled("Cancelled by user") from exc
            if progress_callback is not None:
                _report_progress(status, progress_callback)

        options["progress_hooks"] = [hook]
    return options


def _is_transient_error(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    if isinstance(error, instaloader.exceptions.ConnectionException):
        return not isinstance(
            error,
            (
                instaloader.exceptions.QueryReturnedNotFoundException,
                instaloader.exceptions.TooManyRequestsException,
            ),
        )
    if isinstance(error, yt_dlp.utils.DownloadError):
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "timed out",
                "timeout",
                "connection reset",
                "connection aborted",
                "temporary failure",
                "temporarily unavailable",
                "http error 5",
                "unable to download webpage",
            )
        )
    return False


def download_media(
    request: DownloadRequest,
    progress_callback: ProgressCallback | None = None,
    control: DownloadControl | None = None,
    max_retries: int = 2,
    status_callback: Callable[[str], None] | None = None,
) -> DownloadResult:
    parsed = parse_media_url(request.url)
    if parsed.provider != request.provider:
        raise ValueError("A plataforma da solicitação não corresponde à URL.")
    if max_retries < 0 or max_retries > 5:
        raise ValueError("O número de novas tentativas deve ficar entre 0 e 5.")
    request = create_download_request(
        parsed.url,
        request.media_format,
        request.quality,
        destination=request.destination,
        overwrite=request.overwrite,
    )

    output_directory = _output_directory(request)
    output_directory.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()
    attempt = 0
    while True:
        if control is not None:
            control.wait_until_resumed()
        try:
            if request.provider == "Instagram":
                title, output_file = _download_instagram(parsed, output_directory)
            else:
                title, output_file = _download_with_yt_dlp(
                    request,
                    output_directory,
                    progress_callback,
                    control,
                )
            break
        except DownloadCancelledError:
            raise
        except Exception as exc:
            if attempt >= max_retries or not _is_transient_error(exc):
                raise
            attempt += 1
            if status_callback is not None:
                status_callback(f"Nova tentativa {attempt} de {max_retries}")
            if control is not None:
                for _ in range(2 ** (attempt - 1) * 5):
                    control.wait_until_resumed()
                    if control.is_cancelled:
                        raise DownloadCancelledError()
                    time.sleep(1)
            else:
                time.sleep(2 ** (attempt - 1))

    return DownloadResult(
        request.provider,
        title,
        output_directory,
        time.perf_counter() - started_at,
        output_file,
        attempt + 1,
    )


def _download_instagram(
    parsed: ParsedMediaURL,
    output_directory: Path,
) -> tuple[str, Path | None]:
    if parsed.shortcode is None:
        raise URLValidationError("Não foi possível identificar o post do Instagram.")

    loader = instaloader.Instaloader(
        dirname_pattern=str(output_directory),
        download_pictures=False,
        download_video_thumbnails=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        filename_pattern="{owner_username} - {mediaid}",
    )
    post = instaloader.Post.from_shortcode(loader.context, parsed.shortcode)
    contains_video = post.is_video
    if post.typename == "GraphSidecar":
        contains_video = any(post.get_is_videos())
    if not contains_video:
        raise ValueError("O post do Instagram não contém vídeo.")

    downloaded = loader.download_post(post, target=output_directory.name)
    if downloaded:
        output_files = sorted(
            output_directory.glob("*.mp4"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        output_file = output_files[0] if output_files else None
        return f"Post de {post.owner_username}", output_file
    return f"Post já salvo de {post.owner_username}", None


def _download_with_yt_dlp(
    request: DownloadRequest,
    output_directory: Path,
    progress_callback: ProgressCallback | None,
    control: DownloadControl | None = None,
) -> tuple[str, Path | None]:
    options = _yt_dlp_options(
        request,
        output_directory,
        progress_callback=progress_callback,
        control=control,
    )

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(request.url, download=True)
    except yt_dlp.utils.DownloadCancelled as exc:
        raise DownloadCancelledError() from exc
    if not isinstance(info, dict):
        raise RuntimeError("A biblioteca não retornou os dados da mídia.")
    output_file = _extract_output_file(info)
    if request.media_format == "mp3" and output_file is not None:
        output_file = output_file.with_suffix(".mp3")
    return str(info.get("title") or "Mídia"), output_file


def _extract_output_file(info: dict[str, object]) -> Path | None:
    requested_downloads = info.get("requested_downloads")
    if isinstance(requested_downloads, list):
        for item in requested_downloads:
            if isinstance(item, dict):
                path = item.get("filepath") or item.get("filename")
                if isinstance(path, str):
                    return Path(path)
    path = info.get("filepath") or info.get("_filename")
    return Path(path) if isinstance(path, str) else None


def _report_progress(
    status: dict[str, object],
    callback: ProgressCallback,
) -> None:
    if status.get("status") == "finished":
        callback(100.0)
        return
    if status.get("status") != "downloading":
        return

    downloaded = status.get("downloaded_bytes")
    total = status.get("total_bytes") or status.get("total_bytes_estimate")
    if (
        isinstance(downloaded, (int, float))
        and isinstance(total, (int, float))
        and total
    ):
        callback(min(100.0, max(0.0, downloaded / total * 100)))
