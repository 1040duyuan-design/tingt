from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PERSONA_DIR = ROOT / "persona"


def read_text(name: str) -> str:
    path = PERSONA_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_base_prompt() -> str:
    parts = [
        read_text("system_prompt.md"),
        read_text("resume_memory.md"),
        read_text("self_memory.md"),
        read_text("runtime_persona.md"),
        read_text("runtime_scene.md"),
        read_text("name_guard.md"),
    ]
    return "\n\n".join(part for part in parts if part.strip())


def build_mode_prompt(mode: str) -> str:
    if mode == "extreme_intimate":
        parts = [
            read_text("locked_intimate_mode.md"),
            read_text("intimate_mode_grounding.md"),
        ]
        return "\n\n".join(part for part in parts if part.strip())
    return ""
