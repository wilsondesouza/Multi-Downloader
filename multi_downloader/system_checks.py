from __future__ import annotations


def check_ffmpeg() -> str | None:
    import shutil
    import subprocess

    executable = shutil.which("ffmpeg")
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "FFmpeg foi encontrado, mas não respondeu corretamente."
    if result.returncode != 0:
        return "FFmpeg foi encontrado, mas não respondeu corretamente."
    first_line = result.stdout.splitlines()
    return first_line[0] if first_line else "FFmpeg disponível"


def check_dependency_updates(timeout: float = 8.0) -> dict[str, tuple[str, str]]:
    import json
    from importlib.metadata import PackageNotFoundError, version
    from urllib.request import urlopen

    packages = ("yt-dlp", "instaloader", "customtkinter", "packaging")
    updates: dict[str, tuple[str, str]] = {}
    for package in packages:
        try:
            installed = version(package)
        except PackageNotFoundError:
            continue
        try:
            with urlopen(
                f"https://pypi.org/pypi/{package}/json",
                timeout=timeout,
            ) as response:
                latest = json.load(response)["info"]["version"]
        except (OSError, ValueError, KeyError) as exc:
            updates[package] = (installed, f"unavailable: {type(exc).__name__}")
            continue
        updates[package] = (installed, latest)
    return updates


def is_update_available(installed: str, latest: str) -> bool:
    from packaging.version import InvalidVersion, Version

    try:
        return Version(latest) > Version(installed)
    except InvalidVersion:
        return False
