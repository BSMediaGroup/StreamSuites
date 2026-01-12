"""Unified chat event storage backed by SQLite or JSONL."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shared.chat.events import ChatEvent, create_chat_event
from shared.logging.logger import get_logger
from shared.runtime import chat_context

log = get_logger("shared.chat_events.store")

DEFAULT_DB_PATH = Path("data/streamsuites.db")
DEFAULT_JSONL_ROOT = Path("shared/storage/chat_events/streams")
DEFAULT_INDEX_PATH = Path("shared/storage/chat_events/streams_index.json")


class ChatEventStore:
    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        jsonl_root: Path | str = DEFAULT_JSONL_ROOT,
        index_path: Path | str = DEFAULT_INDEX_PATH,
    ) -> None:
        self._db_path = Path(db_path)
        self._jsonl_root = Path(jsonl_root)
        self._index_path = Path(index_path)
        self._lock = threading.Lock()
        self._use_sqlite = self._db_path.exists()
        self._recent_ids: List[str] = []
        self._recent_limit = 500

        if self._use_sqlite:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()
        else:
            self._jsonl_root.mkdir(parents=True, exist_ok=True)
            self._index_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # SQLite setup
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE,
                    ts TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    author_id TEXT,
                    display_name TEXT,
                    avatar_url TEXT,
                    badges_json TEXT,
                    roles_json TEXT,
                    content_type TEXT,
                    content_text TEXT,
                    flags_json TEXT,
                    raw_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_streams (
                    stream_id TEXT PRIMARY KEY,
                    title TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    platforms_active TEXT NOT NULL,
                    chat_available INTEGER NOT NULL,
                    last_updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_events_stream_ts
                ON chat_events(stream_id, ts, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_events_ts
                ON chat_events(ts, id)
                """
            )

    # ------------------------------------------------------------------
    # JSONL helpers
    # ------------------------------------------------------------------

    def _jsonl_path(self, stream_id: str) -> Path:
        safe = stream_id.replace("/", "_").replace("\\", "_")
        return self._jsonl_root / f"{safe}.jsonl"

    def _load_index(self) -> Dict[str, Any]:
        if not self._index_path.exists():
            return {"streams": {}}
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning(f"Failed to load stream index: {exc}")
            return {"streams": {}}
        if not isinstance(payload, dict):
            return {"streams": {}}
        payload.setdefault("streams", {})
        return payload

    def _save_index(self, payload: Dict[str, Any]) -> None:
        try:
            self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning(f"Failed to save stream index: {exc}")

    # ------------------------------------------------------------------
    # Stream index
    # ------------------------------------------------------------------

    def _upsert_stream_index(
        self,
        *,
        stream_id: str,
        platform: str,
        ts: str,
        title: Optional[str] = None,
    ) -> None:
        if self._use_sqlite:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT platforms_active, started_at FROM chat_streams WHERE stream_id = ?",
                    (stream_id,),
                ).fetchone()
                if row:
                    platforms = json.loads(row["platforms_active"]) if row["platforms_active"] else []
                    if platform and platform not in platforms:
                        platforms.append(platform)
                    conn.execute(
                        """
                        UPDATE chat_streams
                        SET title = COALESCE(?, title),
                            platforms_active = ?,
                            chat_available = 1,
                            last_updated_at = ?
                        WHERE stream_id = ?
                        """,
                        (
                            title,
                            json.dumps(platforms),
                            ts,
                            stream_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO chat_streams (
                            stream_id, title, started_at, ended_at,
                            platforms_active, chat_available, last_updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            stream_id,
                            title,
                            ts,
                            None,
                            json.dumps([platform] if platform else []),
                            1,
                            ts,
                        ),
                    )
            return

        payload = self._load_index()
        streams = payload.setdefault("streams", {})
        entry = streams.get(stream_id) or {
            "stream_id": stream_id,
            "title": title,
            "started_at": ts,
            "ended_at": None,
            "platforms_active": [],
            "chat_available": True,
            "last_updated_at": ts,
        }
        if title and not entry.get("title"):
            entry["title"] = title
        platforms = entry.get("platforms_active", [])
        if platform and platform not in platforms:
            platforms.append(platform)
        entry["platforms_active"] = platforms
        entry["chat_available"] = True
        entry["last_updated_at"] = ts
        streams[stream_id] = entry
        self._save_index(payload)

    def mark_stream_ended(self, stream_id: str, ts: str) -> None:
        if not stream_id:
            return
        if self._use_sqlite:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE chat_streams SET ended_at = ? WHERE stream_id = ?",
                    (ts, stream_id),
                )
            return
        payload = self._load_index()
        streams = payload.setdefault("streams", {})
        entry = streams.get(stream_id)
        if not entry:
            return
        entry["ended_at"] = ts
        streams[stream_id] = entry
        self._save_index(payload)

    # ------------------------------------------------------------------
    # Event persistence
    # ------------------------------------------------------------------

    def append_event(self, event: ChatEvent, title: Optional[str] = None) -> bool:
        if event.event_id in self._recent_ids:
            return False
        with self._lock:
            self._recent_ids.append(event.event_id)
            if len(self._recent_ids) > self._recent_limit:
                self._recent_ids = self._recent_ids[-self._recent_limit :]

            if self._use_sqlite:
                try:
                    with self._connect() as conn:
                        conn.execute(
                            """
                            INSERT INTO chat_events (
                                event_id, ts, stream_id, source_platform,
                                author_id, display_name, avatar_url,
                                badges_json, roles_json, content_type,
                                content_text, flags_json, raw_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                event.event_id,
                                event.ts,
                                event.stream_id,
                                event.source_platform,
                                event.author.author_id,
                                event.author.display_name,
                                event.author.avatar_url,
                                json.dumps(event.author.badges),
                                json.dumps(event.author.roles),
                                event.content.type,
                                event.content.text,
                                json.dumps(event.flags.__dict__),
                                json.dumps(event.raw) if event.raw is not None else None,
                            ),
                        )
                except sqlite3.IntegrityError:
                    return False
            else:
                path = self._jsonl_path(event.stream_id)
                line = json.dumps(event.to_dict())
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")

        previous = chat_context.update_live_stream(event.stream_id)
        if previous and previous != event.stream_id:
            self.mark_stream_ended(previous, event.ts)

        self._upsert_stream_index(
            stream_id=event.stream_id,
            platform=event.source_platform,
            ts=event.ts,
            title=title,
        )
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def list_streams(self) -> List[Dict[str, Any]]:
        if self._use_sqlite:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM chat_streams ORDER BY last_updated_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]

        payload = self._load_index()
        streams = list(payload.get("streams", {}).values())
        streams.sort(key=lambda e: e.get("last_updated_at") or "", reverse=True)
        return streams

    def get_stream(self, stream_id: str) -> Optional[Dict[str, Any]]:
        if not stream_id:
            return None
        if self._use_sqlite:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM chat_streams WHERE stream_id = ?",
                    (stream_id,),
                ).fetchone()
            return dict(row) if row else None

        payload = self._load_index()
        return payload.get("streams", {}).get(stream_id)

    def _row_to_event(self, row: sqlite3.Row) -> Dict[str, Any]:
        badges = json.loads(row["badges_json"]) if row["badges_json"] else []
        roles = json.loads(row["roles_json"]) if row["roles_json"] else []
        flags = json.loads(row["flags_json"]) if row["flags_json"] else {}
        raw = json.loads(row["raw_json"]) if row["raw_json"] else None
        event = create_chat_event(
            stream_id=row["stream_id"],
            source_platform=row["source_platform"],
            author_id=row["author_id"] or "",
            display_name=row["display_name"] or "",
            text=row["content_text"] or "",
            avatar_url=row["avatar_url"],
            badges=badges,
            roles=roles,
            is_synthetic=bool(flags.get("is_synthetic")),
            is_system=bool(flags.get("is_system")),
            is_highlighted=bool(flags.get("is_highlighted")),
            raw=raw,
            event_id=row["event_id"],
            ts=row["ts"],
        )
        return event.to_dict()

    def tail(self, stream_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not stream_id:
            return []
        if self._use_sqlite:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM chat_events
                    WHERE stream_id = ?
                    ORDER BY ts DESC, id DESC
                    LIMIT ?
                    """,
                    (stream_id, limit),
                ).fetchall()
            events = [self._row_to_event(row) for row in rows]
            events.reverse()
            return events

        path = self._jsonl_path(stream_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        selected = [json.loads(line) for line in lines[-limit:] if line.strip()]
        return selected

    def range(self, stream_id: str, from_ts: Optional[str], to_ts: Optional[str]) -> List[Dict[str, Any]]:
        if not stream_id:
            return []
        if self._use_sqlite:
            clauses = ["stream_id = ?"]
            params: List[Any] = [stream_id]
            if from_ts:
                clauses.append("ts >= ?")
                params.append(from_ts)
            if to_ts:
                clauses.append("ts <= ?")
                params.append(to_ts)
            where = " AND ".join(clauses)
            with self._connect() as conn:
                rows = conn.execute(
                    f"SELECT * FROM chat_events WHERE {where} ORDER BY ts, id",
                    tuple(params),
                ).fetchall()
            return [self._row_to_event(row) for row in rows]

        events = self.tail(stream_id, limit=10000)
        filtered: List[Dict[str, Any]] = []
        for evt in events:
            ts = evt.get("ts")
            if from_ts and ts and ts < from_ts:
                continue
            if to_ts and ts and ts > to_ts:
                continue
            filtered.append(evt)
        return filtered

    def paginate(
        self,
        stream_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        if not stream_id:
            return [], None
        if self._use_sqlite:
            params: List[Any] = [stream_id]
            clause = "stream_id = ?"
            if cursor:
                clause += " AND id > ?"
                try:
                    params.append(int(cursor))
                except ValueError:
                    params.append(0)
            query = (
                "SELECT * FROM chat_events WHERE "
                + clause
                + " ORDER BY id ASC LIMIT ?"
            )
            params.append(limit + 1)
            with self._connect() as conn:
                rows = conn.execute(query, tuple(params)).fetchall()
            events = [self._row_to_event(row) for row in rows[:limit]]
            next_cursor = None
            if len(rows) > limit:
                next_cursor = str(rows[limit - 1]["id"])
            elif rows:
                next_cursor = str(rows[-1]["id"])
            return events, next_cursor

        events = self.tail(stream_id, limit=limit)
        return events, None


_STORE: Optional[ChatEventStore] = None


def get_store() -> ChatEventStore:
    global _STORE
    if _STORE is None:
        _STORE = ChatEventStore()
    return _STORE


def append_chat_event(event: ChatEvent, title: Optional[str] = None) -> bool:
    return get_store().append_event(event, title=title)


def list_streams() -> List[Dict[str, Any]]:
    return get_store().list_streams()


def get_stream(stream_id: str) -> Optional[Dict[str, Any]]:
    return get_store().get_stream(stream_id)


def tail_events(stream_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    return get_store().tail(stream_id, limit=limit)


def range_events(
    stream_id: str,
    from_ts: Optional[str],
    to_ts: Optional[str],
) -> List[Dict[str, Any]]:
    return get_store().range(stream_id, from_ts, to_ts)


def paginate_events(
    stream_id: str,
    limit: int = 50,
    cursor: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    return get_store().paginate(stream_id, limit=limit, cursor=cursor)

