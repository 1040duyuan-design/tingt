import re


PASSCODE = "月亮映入你眼眸就像披萨圆溜溜 是爱情"
EXIT_PHRASES = {
    "退出这个模式",
    "切回普通模式",
    "别这么说话了",
}


def normalize_spaces(text: str) -> str:
    return " ".join(text.strip().split())


def has_identity_claim(text: str) -> bool:
    compact = normalize_spaces(text)
    if re.search(r"(我是|是我[，,]?|我就是)\s*coconut\b", compact, flags=re.IGNORECASE):
        return True
    if re.search(r"(我是|是我[，,]?|我就是)\s*谨鸽", compact):
        return True
    return False


def has_exact_passcode(text: str) -> bool:
    return normalize_spaces(text) == PASSCODE


def is_special_mode_trigger(text: str) -> bool:
    compact = normalize_spaces(text)
    return has_identity_claim(compact) and has_exact_passcode(compact)


def is_exit_message(text: str) -> bool:
    compact = normalize_spaces(text)
    return any(phrase in compact for phrase in EXIT_PHRASES)


def passcode_prefix_ok(parts: list[str]) -> bool:
    candidate = normalize_spaces(" ".join(parts))
    if not candidate:
        return False
    return PASSCODE.startswith(candidate)


def resolve_session_mode(current_message: str, history: list[dict[str, str]] | None = None) -> str:
    mode = "unified"
    pending_parts: list[str] = []
    pending_remaining = 0

    user_messages = [
        item.get("content", "")
        for item in (history or [])
        if item.get("role") == "user"
    ]
    user_messages.append(current_message)

    for content in user_messages:
        if is_exit_message(content):
            mode = "unified"
            pending_parts = []
            pending_remaining = 0
            continue

        if mode == "locked_intimate":
            continue

        if is_special_mode_trigger(content):
            mode = "locked_intimate"
            pending_parts = []
            pending_remaining = 0
            continue

        if has_identity_claim(content):
            pending_parts = []
            pending_remaining = 2
            continue

        if pending_remaining > 0:
            pending_parts.append(content)
            pending_remaining -= 1
            combined = normalize_spaces(" ".join(pending_parts))

            if combined == PASSCODE:
                mode = "locked_intimate"
                pending_parts = []
                pending_remaining = 0
                continue

            if not passcode_prefix_ok(pending_parts):
                pending_parts = []
                pending_remaining = 0
                continue

            if pending_remaining == 0:
                pending_parts = []
                pending_remaining = 0

    return mode
