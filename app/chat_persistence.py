import hashlib
import os
import sqlite3
from pathlib import Path


DB_PATH = Path(os.getenv("CHAT_DB_PATH", "/tmp/tingt_chat.sqlite3"))


def _ensure_parent() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_parent()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_chat_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'web',
                user_agent TEXT,
                ip_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                mode TEXT,
                confidence REAL,
                degraded INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                attempt TEXT,
                history_turns INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
            ON chat_messages(session_id, id);

            CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
            ON chat_sessions(updated_at DESC);
            """
        )


def upsert_session(
    session_id: str,
    created_at: str,
    *,
    source: str = "web",
    user_agent: str | None = None,
    ip_hash: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (
                session_id, source, user_agent, ip_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                source = excluded.source,
                user_agent = COALESCE(excluded.user_agent, chat_sessions.user_agent),
                ip_hash = COALESCE(excluded.ip_hash, chat_sessions.ip_hash),
                updated_at = excluded.updated_at
            """,
            (session_id, source, user_agent, ip_hash, created_at, created_at),
        )


def insert_chat_message(
    *,
    session_id: str,
    role: str,
    content: str | None,
    mode: str | None,
    confidence: float | None,
    degraded: bool,
    reason: str | None,
    attempt: str | None,
    history_turns: int,
    created_at: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                session_id, role, content, mode, confidence, degraded, reason,
                attempt, history_turns, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                mode,
                confidence,
                1 if degraded else 0,
                reason,
                attempt,
                history_turns,
                created_at,
            ),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
            (created_at, session_id),
        )


def load_latest_session() -> dict | None:
    with _connect() as conn:
        latest = conn.execute(
            """
            SELECT session_id, source, user_agent, ip_hash, created_at, updated_at
            FROM chat_sessions
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not latest:
            return None

        turns = conn.execute(
            """
            SELECT id, role, content, mode, confidence, degraded, reason,
                   attempt, history_turns, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (latest["session_id"],),
        ).fetchall()

    return {
        "session_id": latest["session_id"],
        "source": latest["source"],
        "user_agent": latest["user_agent"],
        "ip_hash": latest["ip_hash"],
        "created_at": latest["created_at"],
        "updated_at": latest["updated_at"],
        "turn_count": len(turns),
        "turns": [dict(row) for row in turns],
    }


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]


def expected_debug_key() -> str | None:
    explicit = os.getenv("DEBUG_CHAT_KEY", "").strip()
    if explicit:
        return explicit

    seed = (
        os.getenv("MINIMAX_API_KEY", "").strip()
        or os.getenv("SILICONFLOW_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
    )
    if not seed:
        return None
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
