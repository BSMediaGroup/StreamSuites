from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Any

from shared.logging.logger import get_logger
from services.clips.models import (
    CLIP_STATES,
    ClipDestination,
    ClipRecord,
    ClipRequest,
    format_clip_title,
    generate_clip_id,
)

log = get_logger("services.clips.storage")


class ClipStore:
    """
    SQLite-backed clip store.

    Tables:
      - clips
      - clip_jobs
      - clip_state_history
    """

    def __init__(self, db_path: Path | str = "data/streamsuites.db"):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clips (
                    clip_id TEXT PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    source_title TEXT NOT NULL,
                    clipper_username TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    start_seconds REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    requested_at INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    output_path TEXT,
                    published_url TEXT,
                    last_error TEXT,
                    updated_at INTEGER,
                    requested_by TEXT,
                    destination_platform TEXT,
                    destination_channel_url TEXT,
                    clip_title TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clip_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clip_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    detail TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clip_state_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clip_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT,
                    created_at INTEGER NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _row_to_record(self, row: Mapping[str, Any]) -> ClipRecord:
        return ClipRecord(
            clip_id=row["clip_id"],
            creator_id=row["creator_id"],
            source_title=row["source_title"],
            clipper_username=row["clipper_username"],
            source_path=row["source_path"],
            start_seconds=row["start_seconds"],
            duration_seconds=row["duration_seconds"],
            requested_at=row["requested_at"],
            state=row["state"],
            output_path=row["output_path"],
            published_url=row["published_url"],
            last_error=row["last_error"],
            updated_at=row["updated_at"],
            requested_by=row["requested_by"],
            destination_platform=row["destination_platform"],
            destination_channel_url=row["destination_channel_url"],
            clip_title=row["clip_title"],
        )

    def _validate_state(self, state: str) -> None:
        if state not in CLIP_STATES:
            raise ValueError(f"Invalid clip state: {state}")

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def enqueue(self, request: ClipRequest, destination: ClipDestination) -> ClipRecord:
        requested_at = int(request.requested_at.timestamp())

        # generate deterministic-length IDs; retry on collision
        while True:
            clip_id = generate_clip_id()
            clip_title = format_clip_title(
                request.source_title,
                request.clipper_username,
                clip_id,
            )
            try:
                with self._lock, self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO clips (
                            clip_id, creator_id, source_title, clipper_username,
                            source_path, start_seconds, duration_seconds,
                            requested_at, state, output_path, published_url,
                            last_error, updated_at, requested_by,
                            destination_platform, destination_channel_url, clip_title
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            clip_id,
                            request.creator_id,
                            request.source_title,
                            request.clipper_username,
                            request.source_path,
                            float(request.start_seconds),
                            float(request.duration_seconds),
                            requested_at,
                            "queued",
                            None,
                            None,
                            None,
                            requested_at,
                            request.requested_by,
                            destination.platform,
                            destination.channel_url,
                            clip_title,
                        ),
                    )
                    self._record_state_history(conn, clip_id, "queued", reason="queued")
                    self._record_job_state(conn, clip_id, "clip", "queued", detail="queued")
                break
            except sqlite3.IntegrityError:
                # Collision on clip_id, regenerate
                continue

        return ClipRecord(
            clip_id=clip_id,
            creator_id=request.creator_id,
            source_title=request.source_title,
            clipper_username=request.clipper_username,
            source_path=request.source_path,
            start_seconds=float(request.start_seconds),
            duration_seconds=float(request.duration_seconds),
            requested_at=requested_at,
            state="queued",
            output_path=None,
            published_url=None,
            last_error=None,
            updated_at=requested_at,
            requested_by=request.requested_by,
            destination_platform=destination.platform,
            destination_channel_url=destination.channel_url,
            clip_title=clip_title,
        )

    def claim_queued(self, limit: int) -> List[ClipRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM clips
                WHERE state = 'queued'
                ORDER BY requested_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            claimed: List[ClipRecord] = []
            now = int(time.time())

            for row in rows:
                clip_id = row["clip_id"]
                conn.execute(
                    """
                    UPDATE clips
                    SET state = ?, updated_at = ?, last_error = NULL
                    WHERE clip_id = ?
                    """,
                    ("encoding", now, clip_id),
                )
                self._record_state_history(conn, clip_id, "encoding", reason="encoding")
                self._record_job_state(conn, clip_id, "encode", "encoding", detail="encoding")
                updated_row = dict(row)
                updated_row["state"] = "encoding"
                updated_row["updated_at"] = now
                updated_row["last_error"] = None
                claimed.append(self._row_to_record(updated_row))

            return claimed

    def update_state(
        self,
        clip_id: str,
        state: str,
        *,
        reason: Optional[str] = None,
        output_path: Optional[str] = None,
        published_url: Optional[str] = None,
        error: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> Optional[ClipRecord]:
        self._validate_state(state)
        now = int(time.time())

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE clips
                SET state = ?, output_path = COALESCE(?, output_path),
                    published_url = COALESCE(?, published_url),
                    last_error = ?, updated_at = ?
                WHERE clip_id = ?
                """,
                (state, output_path, published_url, error, now, clip_id),
            )
            self._record_state_history(conn, clip_id, state, reason=reason)
            if job_type:
                self._record_job_state(conn, clip_id, job_type, state, detail=reason)

            row = conn.execute(
                "SELECT * FROM clips WHERE clip_id = ?", (clip_id,)
            ).fetchone()

        if not row:
            return None
        return self._row_to_record(row)

    def get_all(self) -> List[ClipRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM clips ORDER BY requested_at DESC").fetchall()
        return [self._row_to_record(r) for r in rows]

    def _record_state_history(
        self,
        conn: sqlite3.Connection,
        clip_id: str,
        state: str,
        *,
        reason: Optional[str],
    ) -> None:
        conn.execute(
            """
            INSERT INTO clip_state_history (clip_id, state, reason, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (clip_id, state, reason, int(time.time())),
        )

    def _record_job_state(
        self,
        conn: sqlite3.Connection,
        clip_id: str,
        job_type: str,
        state: str,
        *,
        detail: Optional[str],
    ) -> None:
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO clip_jobs (clip_id, job_type, state, detail, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (clip_id, job_type, state, detail, now, now),
        )

    def record_job_transition(
        self,
        clip_id: str,
        job_type: str,
        state: str,
        *,
        detail: Optional[str] = None,
    ) -> None:
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO clip_jobs (clip_id, job_type, state, detail, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (clip_id, job_type, state, detail, now, now),
            )

    def get_history(self, clip_id: str) -> List[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT state, reason, created_at
                FROM clip_state_history
                WHERE clip_id = ?
                ORDER BY created_at ASC
                """,
                (clip_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def prune_failed(self, clip_ids: Iterable[str]) -> None:
        with self._lock, self._connect() as conn:
            for clip_id in clip_ids:
                conn.execute(
                    "UPDATE clips SET last_error = last_error WHERE clip_id = ?",
                    (clip_id,),
                )
