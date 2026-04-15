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
        read_text("persona.md"),
        read_text("relationship_modes.md"),
    ]
    return "\n\n".join(part for part in parts if part.strip())
