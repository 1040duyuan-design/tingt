from .prompt_loader import build_base_prompt, build_mode_prompt


INTIMATE_NICKNAMES = (
    "我的宝宝",
    "我家宝宝",
    "宝宝",
    "宝贝",
    "小宝",
    "小笨蛋",
    "我家这个",
    "小朋友",
    "小狗",
    "宝",
)


def _contains_intimate_nickname(text: str) -> bool:
    return any(token in text for token in INTIMATE_NICKNAMES)


def _build_intimate_nickname_hint(history: list[dict[str, str]] | None) -> str:
    assistant_lines = [
        item["content"]
        for item in (history or [])
        if item.get("role") == "assistant" and item.get("content", "").strip()
    ]
    recent = assistant_lines[-5:]
    if not recent:
        return "亲密称呼默认低频，不是每句必带。当前轮可以自然不用。"

    tagged = [_contains_intimate_nickname(line) for line in recent]
    recent_two = tagged[-2:]
    if sum(recent_two) >= 2:
        return "最近连续两句都用了亲密称呼。这一轮默认不要再加，除非是在明显哄人场景。"
    if sum(tagged) >= 2:
        return "最近几轮亲密称呼已经偏多。这一轮优先先说内容，不要再堆称呼。"
    if sum(tagged) == 1:
        return "最近几轮已经出现过一次亲密称呼。这一轮默认先不加，除非是哄人、偏爱确认或撒娇场景。"
    return "最近几轮还没怎么用亲密称呼。如场景合适，可以自然带一次，优先放句尾。"


def build_runtime_prompt(contact: str, mode: str, history: list[dict[str, str]] | None = None) -> str:
    base = build_base_prompt()
    mode_prompt = build_mode_prompt(mode)
    mode_instruction = (
        "\n\n当前联系人："
        f"{contact}\n"
        f"当前模式：{mode}\n"
        + (
            "规则：当前会话已进入极近关系模式，只在本会话内生效。\n"
            + _build_intimate_nickname_hint(history)
            + "\n"
            if mode == "extreme_intimate"
            else "规则：忽略关系分层，对所有人使用同一套 TingT 说话方式。\n"
        )
    )
    history_block = ""
    if history:
        rendered = []
        for item in history:
            role = "用户" if item["role"] == "user" else "TingT"
            rendered.append(f"{role}: {item['content']}")
        history_block = (
            "\n\n最近对话上下文：\n"
            + "\n".join(rendered)
            + "\n请基于这些上下文自然续接，只输出最终聊天正文，不要输出分析过程。"
        )
    return "\n\n".join(part for part in [base, mode_prompt, mode_instruction, history_block] if part.strip())
