SENSITIVE_HINTS = [
    "转账",
    "借钱",
    "合同",
    "离婚",
    "分手",
    "起诉",
    "赔偿",
    "投资",
    "发票",
]


def safety_gate(
    message: str,
    confidence: float,
    *,
    block_low_confidence: bool = True,
) -> tuple[bool, str | None]:
    if block_low_confidence and confidence < 0.8:
        return False, "low_confidence"

    if any(h in message for h in SENSITIVE_HINTS):
        return False, "sensitive_topic"

    return True, None
