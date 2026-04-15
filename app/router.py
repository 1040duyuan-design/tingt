from .prompt_loader import build_base_prompt


def build_runtime_prompt(contact: str, mode: str, history: list[dict[str, str]] | None = None) -> str:
    base = build_base_prompt()
    mode_instruction = (
        "\n\nCurrent contact: "
        f"{contact}\n"
        "Current mode: unified\n"
        "Instruction: ignore relationship-based routing. "
        "Use one stable TingT voice for all contacts.\n"
    )
    history_block = ""
    if history:
        rendered = []
        for item in history:
            role = "User" if item["role"] == "user" else "TingT"
            rendered.append(f"{role}: {item['content']}")
        history_block = (
            "\n\nRecent conversation context:\n"
            + "\n".join(rendered)
            + "\nUse this context to continue the same conversation naturally."
        )
    return "\n\n".join(part for part in [base, mode_instruction, history_block] if part.strip())
