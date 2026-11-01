from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    download_directory: str = ""
    default_quality: str = "best"
    confirm_overwrite: bool = True
    max_retries: int = 2
    check_updates_on_startup: bool = False


@dataclass(frozen=True)
class HistoryRecord:
    id: int
    provider: str
    title: str
    media_format: str
    created_at: str
    status: str
    output_path: str
    error_code: str
    attempts: int


def get_application_data_directory() -> Path:
    if sys.platform == "win32":
        base_directory = os.environ.get("LOCALAPPDATA")
        if base_directory:
            return Path(base_directory) / "MultiDownloader"
        return Path.home() / "AppData" / "Local" / "MultiDownloader"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MultiDownloader"
    base_directory = os.environ.get("XDG_STATE_HOME")
    if base_directory:
        return Path(base_directory) / "multi-downloader"
    return Path.home() / ".local" / "state" / "multi-downloader"


class AppStore:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or (
            get_application_data_directory() / "history.sqlite3"
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY,
                    provider TEXT NOT NULL,
                    title TEXT NOT NULL,
                    media_format TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    error_code TEXT NOT NULL DEFAULT '',
                    attempts INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def load_settings(self) -> AppSettings:
        with self._lock:
            rows = self._connection.execute(
                "SELECT key, value FROM settings"
            ).fetchall()
        stored = {row["key"]: json.loads(row["value"]) for row in rows}
        defaults = asdict(AppSettings())
        defaults.update(stored)
        return AppSettings(**defaults)

    def save_settings(self, settings: AppSettings) -> None:
        values = asdict(settings)
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                [(key, json.dumps(value)) for key, value in values.items()],
            )

    def create_history_record(
        self,
        provider: str,
        title: str,
        media_format: str,
        output_path: str = "",
        status: str = "queued",
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO history (
                    provider, title, media_format, created_at, status, output_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    title,
                    media_format,
                    created_at,
                    status,
                    output_path,
                ),
            )
        return int(cursor.lastrowid)

    def update_history_record(
        self,
        record_id: int,
        *,
        title: str | None = None,
        status: str,
        output_path: str | None = None,
        error_code: str = "",
        attempts: int = 0,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE history
                SET title = COALESCE(?, title),
                    status = ?,
                    output_path = COALESCE(?, output_path),
                    error_code = ?,
                    attempts = ?
                WHERE id = ?
                """,
                (title, status, output_path, error_code, attempts, record_id),
            )

    def list_history(self, limit: int = 100) -> list[HistoryRecord]:
        if not 1 <= limit <= 1000:
            raise ValueError("History limit must be between 1 and 1000.")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, provider, title, media_format, created_at, status,
                       output_path, error_code, attempts
                FROM history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [HistoryRecord(**dict(row)) for row in rows]

    def mark_incomplete_history(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE history
                SET status = 'interrupted',
                    error_code = 'AppClosed'
                WHERE status IN ('queued', 'previewing', 'downloading', 'paused')
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()
