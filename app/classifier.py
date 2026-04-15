from .models import ClassificationResult
from .special_mode import resolve_session_mode


def classify_contact(contact: str, message: str, history: list[dict[str, str]] | None = None) -> ClassificationResult:
    mode = resolve_session_mode(message, history=history)
    return ClassificationResult(
        mode=mode,
        confidence=1.0,
        reason=[
            "locked_intimate_mode_for_current_session"
            if mode == "locked_intimate"
            else "single_tingt_style_for_all_contacts"
        ],
    )
