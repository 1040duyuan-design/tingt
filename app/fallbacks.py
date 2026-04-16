FALLBACK_REPLY = "刚刚卡了一下，你再发一句。"

BLOCKED_REPLIES = {
    "low_confidence": "这句我先不乱接。",
    "sensitive_topic": "这个不聊。",
    "privacy_request": "这个别问我。",
    "search_request": "这个不展开。",
    "political_content": "这类内容我不接，换个别的。",
    "soft_privacy_boundary": "这个我不展开，聊点别的。",
    "dangerous_request": "这类内容我不接。",
    "prompt_injection": "这个别套我。",
    "token_burn_risk": "这段我先不展开了，收短点再说。",
    "history_too_long": "这段太长了，我不展开。",
}


def blocked_reply(reason: str | None) -> str:
    if not reason:
        return FALLBACK_REPLY
    return BLOCKED_REPLIES.get(reason, FALLBACK_REPLY)
