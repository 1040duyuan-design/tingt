FALLBACK_REPLY = "刚刚卡了一下，你再发一句。"

BLOCKED_REPLIES = {
    "low_confidence": "这句我先不乱接，你可以换个更直接的说法。",
    "sensitive_topic": "这类话题我不在这边继续聊，换个别的。",
    "privacy_request": "隐私和后台信息这类内容我不会直接给。",
    "search_request": "这个页面不做联网搜索或外部检索，你直接聊想法就行。",
    "prompt_injection": "这种系统设定或内部规则我不直接往外说。",
    "token_burn_risk": "这条太长或太像批量生成请求了，收短一点再发。",
    "history_too_long": "这一轮上下文太长了，你可以换个新话题，或者重新开一轮聊。",
}


def blocked_reply(reason: str | None) -> str:
    if not reason:
        return FALLBACK_REPLY
    return BLOCKED_REPLIES.get(reason, FALLBACK_REPLY)
