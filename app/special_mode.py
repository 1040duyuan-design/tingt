import re
from datetime import datetime, timedelta, timezone

from .chat_logging import log_chat_event
from .session_memory import SessionState, get_session_state


PASSCODE = "月亮映入你眼眸就像披萨圆溜溜 是爱情"
EXIT_PHRASES = {
    "退出这个模式",
    "切回普通模式",
    "别这么说话了",
}
PENDING_TTL_MINUTES = 5
PENDING_USER_TURNS = 3


def normalize_spaces(text: str) -> str:
    return " ".join(text.strip().split())


def extract_identity(text: str) -> str | None:
    compact = normalize_spaces(text)
    if re.search(r"(我是|是我[，,]?|我就是)\s*coconut\b", compact, flags=re.IGNORECASE):
        return "coconut"
    if re.search(r"(我是|是我[，,]?|我就是)\s*谨鸽", compact):
        return "谨鸽"
    return None


def has_exact_passcode(text: str) -> bool:
    return normalize_spaces(text) == PASSCODE


def is_exit_message(text: str) -> bool:
    compact = normalize_spaces(text)
    return any(phrase in compact for phrase in EXIT_PHRASES)


def passcode_prefix_ok(parts: list[str]) -> bool:
    candidate = normalize_spaces(" ".join(parts))
    if not candidate:
        return False
    return PASSCODE.startswith(candidate)


def _clear_pending(state: SessionState) -> None:
    state.pending_identity = None
    state.pending_identity_expires_at = None
    state.pending_user_turns_remaining = 0
    state.pending_passcode_parts = []


def _pending_expired(state: SessionState, now: datetime) -> bool:
    return bool(
        state.pending_identity
        and state.pending_identity_expires_at
        and now > state.pending_identity_expires_at
    )


def resolve_session_mode(session_id: str, current_message: str) -> str:
    state = get_session_state(session_id)
    now = datetime.now(timezone.utc)
    compact = normalize_spaces(current_message)

    if is_exit_message(compact):
        state.relationship_mode = "unified"
        _clear_pending(state)
        return state.relationship_mode

    if _pending_expired(state, now):
        log_chat_event(
            "pending_identity_expired",
            session_id=session_id,
            pendingIdentity=state.pending_identity,
        )
        _clear_pending(state)

    identity = extract_identity(compact)
    if identity:
        log_chat_event(
            "identity_detected",
            session_id=session_id,
            pendingIdentity=identity,
        )
        state.pending_identity = identity
        state.pending_identity_expires_at = now + timedelta(minutes=PENDING_TTL_MINUTES)
        state.pending_user_turns_remaining = PENDING_USER_TURNS
        state.pending_passcode_parts = []
        log_chat_event(
            "pending_identity_set",
            session_id=session_id,
            pendingIdentity=identity,
            pendingIdentityExpiresAt=state.pending_identity_expires_at.isoformat(),
            turnsRemaining=state.pending_user_turns_remaining,
        )
        return state.relationship_mode

    if state.relationship_mode == "extreme_intimate":
        return state.relationship_mode

    if not state.pending_identity:
        return state.relationship_mode

    if has_exact_passcode(compact):
        log_chat_event(
            "passphrase_matched",
            session_id=session_id,
            pendingIdentity=state.pending_identity,
        )
        state.relationship_mode = "extreme_intimate"
        _clear_pending(state)
        log_chat_event(
            "intimacy_mode_enabled",
            session_id=session_id,
            relationshipMode=state.relationship_mode,
        )
        return state.relationship_mode

    state.pending_user_turns_remaining -= 1
    if state.pending_user_turns_remaining < 0:
        state.pending_user_turns_remaining = 0

    parts = state.pending_passcode_parts + [compact]
    if passcode_prefix_ok(parts):
        state.pending_passcode_parts = parts
        if normalize_spaces(" ".join(parts)) == PASSCODE:
            log_chat_event(
                "passphrase_matched",
                session_id=session_id,
                pendingIdentity=state.pending_identity,
            )
            state.relationship_mode = "extreme_intimate"
            _clear_pending(state)
            log_chat_event(
                "intimacy_mode_enabled",
                session_id=session_id,
                relationshipMode=state.relationship_mode,
            )
            return state.relationship_mode
    else:
        log_chat_event(
            "pending_identity_expired",
            session_id=session_id,
            pendingIdentity=state.pending_identity,
            reason="passphrase_mismatch",
        )
        _clear_pending(state)
        return state.relationship_mode

    if state.pending_user_turns_remaining == 0:
        log_chat_event(
            "pending_identity_expired",
            session_id=session_id,
            pendingIdentity=state.pending_identity,
            reason="turn_window_exhausted",
        )
        _clear_pending(state)

    return state.relationship_mode
