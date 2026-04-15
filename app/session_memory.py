from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime


MAX_TURNS = 6
_session_memory: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=MAX_TURNS * 2))


@dataclass
class SessionState:
    pending_identity: str | None = None
    pending_identity_expires_at: datetime | None = None
    pending_user_turns_remaining: int = 0
    pending_passcode_parts: list[str] = field(default_factory=list)
    relationship_mode: str = "unified"


_session_states: dict[str, SessionState] = defaultdict(SessionState)


def get_session_history(session_id: str) -> list[dict[str, str]]:
    return list(_session_memory[session_id])


def append_user_message(session_id: str, message: str) -> None:
    _session_memory[session_id].append({"role": "user", "content": message})


def append_assistant_message(session_id: str, message: str) -> None:
    _session_memory[session_id].append({"role": "assistant", "content": message})


def get_session_state(session_id: str) -> SessionState:
    return _session_states[session_id]
