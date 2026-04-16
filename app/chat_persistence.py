import hashlib
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(os.getenv("CHAT_DB_PATH", "/tmp/tingt_chat.sqlite3"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = bool(DATABASE_URL)


def _ensure_parent() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect_sqlite() -> sqlite3.Connection:
    _ensure_parent()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_postgres():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is required when DATABASE_URL is set") from exc
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@contextmanager
def _connect():
    conn = _connect_postgres() if IS_POSTGRES else _connect_sqlite()
    try:
        yield conn
    finally:
        conn.close()


def init_chat_db() -> None:
    with _connect() as conn:
        if IS_POSTGRES:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL DEFAULT 'web',
                    user_agent TEXT,
                    ip_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    mode TEXT,
                    confidence DOUBLE PRECISION,
                    degraded INTEGER NOT NULL DEFAULT 0,
                    reason TEXT,
                    attempt TEXT,
                    history_turns INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                ON chat_messages(session_id, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
                ON chat_sessions(updated_at DESC)
                """
            )
            conn.commit()
            return

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
        if IS_POSTGRES:
            conn.execute(
                """
                INSERT INTO chat_sessions (
                    session_id, source, user_agent, ip_hash, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(session_id) DO UPDATE SET
                    source = excluded.source,
                    user_agent = COALESCE(excluded.user_agent, chat_sessions.user_agent),
                    ip_hash = COALESCE(excluded.ip_hash, chat_sessions.ip_hash),
                    updated_at = excluded.updated_at
                """,
                (session_id, source, user_agent, ip_hash, created_at, created_at),
            )
            conn.commit()
            return

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
        if IS_POSTGRES:
            conn.execute(
                """
                INSERT INTO chat_messages (
                    session_id, role, content, mode, confidence, degraded, reason,
                    attempt, history_turns, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                "UPDATE chat_sessions SET updated_at = %s WHERE session_id = %s",
                (created_at, session_id),
            )
            conn.commit()
            return

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


def _rows_to_dicts(rows) -> list[dict]:
    normalized = []
    for row in rows:
        normalized.append(dict(row))
    return normalized


def load_latest_session() -> dict | None:
    with _connect() as conn:
        if IS_POSTGRES:
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
                WHERE session_id = %s
                ORDER BY id ASC
                """,
                (latest["session_id"],),
            ).fetchall()
        else:
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

    latest_dict = dict(latest)
    return {
        "session_id": latest_dict["session_id"],
        "source": latest_dict["source"],
        "user_agent": latest_dict["user_agent"],
        "ip_hash": latest_dict["ip_hash"],
        "created_at": latest_dict["created_at"],
        "updated_at": latest_dict["updated_at"],
        "turn_count": len(turns),
        "turns": _rows_to_dicts(turns),
    }


def load_recent_sessions(limit: int | None = 50) -> list[dict]:
    sql = """
    SELECT
        s.session_id,
        s.source,
        s.user_agent,
        s.ip_hash,
        s.created_at,
        s.updated_at,
        COUNT(m.id) AS turn_count,
        MAX(CASE WHEN m.role = 'user' THEN m.content END) AS last_user_message
    FROM chat_sessions s
    LEFT JOIN chat_messages m
      ON s.session_id = m.session_id
    GROUP BY s.session_id
    ORDER BY s.updated_at DESC
    """
    with _connect() as conn:
        if limit is None:
            rows = conn.execute(sql).fetchall()
        else:
            if IS_POSTGRES:
                rows = conn.execute(sql + "\nLIMIT %s", (limit,)).fetchall()
            else:
                rows = conn.execute(sql + "\nLIMIT ?", (limit,)).fetchall()
    return _rows_to_dicts(rows)


def load_session_by_id(session_id: str) -> dict | None:
    with _connect() as conn:
        if IS_POSTGRES:
            session = conn.execute(
                """
                SELECT session_id, source, user_agent, ip_hash, created_at, updated_at
                FROM chat_sessions
                WHERE session_id = %s
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if not session:
                return None

            turns = conn.execute(
                """
                SELECT id, role, content, mode, confidence, degraded, reason,
                       attempt, history_turns, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        else:
            session = conn.execute(
                """
                SELECT session_id, source, user_agent, ip_hash, created_at, updated_at
                FROM chat_sessions
                WHERE session_id = ?
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if not session:
                return None

            turns = conn.execute(
                """
                SELECT id, role, content, mode, confidence, degraded, reason,
                       attempt, history_turns, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()

    session_dict = dict(session)
    return {
        "session_id": session_dict["session_id"],
        "source": session_dict["source"],
        "user_agent": session_dict["user_agent"],
        "ip_hash": session_dict["ip_hash"],
        "created_at": session_dict["created_at"],
        "updated_at": session_dict["updated_at"],
        "turn_count": len(turns),
        "turns": _rows_to_dicts(turns),
    }


def load_recent_real_messages(limit: int = 2) -> list[dict]:
    sql = """
    SELECT
        m.id,
        m.session_id,
        m.role,
        m.content,
        m.mode,
        m.confidence,
        m.degraded,
        m.reason,
        m.attempt,
        m.history_turns,
        m.created_at
    FROM chat_messages m
    JOIN chat_sessions s
      ON s.session_id = m.session_id
    WHERE s.session_id NOT LIKE 'debug-%'
      AND COALESCE(m.content, '') != ''
    ORDER BY m.id DESC
    """
    with _connect() as conn:
        if IS_POSTGRES:
            rows = conn.execute(sql + "\nLIMIT %s", (limit,)).fetchall()
        else:
            rows = conn.execute(sql + "\nLIMIT ?", (limit,)).fetchall()
    return _rows_to_dicts(rows)


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


def masked_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:16]
