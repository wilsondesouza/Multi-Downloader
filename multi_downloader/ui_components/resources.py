from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory:
        return Path(bundle_directory) / relative_path
    return Path(__file__).resolve().parents[2] / relative_path
