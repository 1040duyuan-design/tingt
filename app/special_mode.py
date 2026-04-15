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
    return PASSCODE in normalize_spaces(text)


def is_special_mode_trigger(text: str) -> bool:
    compact = normalize_spaces(text)
    return has_identity_claim(compact) and has_exact_passcode(compact)


def is_exit_message(text: str) -> bool:
    compact = normalize_spaces(text)
    return any(phrase in compact for phrase in EXIT_PHRASES)


def resolve_session_mode(current_message: str, history: list[dict[str, str]] | None = None) -> str:
    mode = "unified"
    turns = list(history or []) + [{"role": "user", "content": current_message}]
    for item in turns:
        if item.get("role") != "user":
            continue
        content = item.get("content", "")
        if is_exit_message(content):
            mode = "unified"
            continue
        if is_special_mode_trigger(content):
            mode = "locked_intimate"
    return mode
