import hashlib
import json
import os
from pathlib import Path


LOG_PATH = Path(os.getenv("CHAT_LOG_PATH", "/tmp/tingt_chat_sessions.jsonl"))


def _ensure_parent() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def append_chat_record(record: dict) -> None:
    _ensure_parent()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_latest_session() -> dict | None:
    if not LOG_PATH.exists():
        return None

    rows: list[dict] = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not rows:
        return None

    latest_session_id = rows[-1].get("session_id")
    if not latest_session_id:
        return None

    session_rows = [row for row in rows if row.get("session_id") == latest_session_id]
    return {
        "session_id": latest_session_id,
        "turns": session_rows,
        "turn_count": len(session_rows),
    }


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
