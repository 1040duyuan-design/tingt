from .prompt_loader import build_base_prompt


def build_runtime_prompt(contact: str, mode: str) -> str:
    base = build_base_prompt()
    mode_instruction = (
        "\n\nCurrent contact: "
        f"{contact}\n"
        "Current mode: unified\n"
        "Instruction: ignore relationship-based routing. "
        "Use one stable TingT voice for all contacts.\n"
    )
    return "\n\n".join(part for part in [base, mode_instruction] if part.strip())
