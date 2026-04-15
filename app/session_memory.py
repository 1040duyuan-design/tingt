from collections import defaultdict, deque


MAX_TURNS = 6
_session_memory: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=MAX_TURNS * 2))


def get_session_history(session_id: str) -> list[dict[str, str]]:
    return list(_session_memory[session_id])


def append_user_message(session_id: str, message: str) -> None:
    _session_memory[session_id].append({"role": "user", "content": message})


def append_assistant_message(session_id: str, message: str) -> None:
    _session_memory[session_id].append({"role": "assistant", "content": message})
