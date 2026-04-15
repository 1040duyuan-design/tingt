from .prompt_loader import build_base_prompt, build_mode_prompt


def build_runtime_prompt(contact: str, mode: str, history: list[dict[str, str]] | None = None) -> str:
    base = build_base_prompt()
    mode_prompt = build_mode_prompt(mode)
    mode_instruction = (
        "\n\n当前联系人："
        f"{contact}\n"
        f"当前模式：{mode}\n"
        + (
            "规则：当前会话已进入极近关系模式，只在本会话内生效。\n"
            if mode == "locked_intimate"
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
