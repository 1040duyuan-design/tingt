from .models import ClassificationResult


def classify_contact(contact: str, message: str) -> ClassificationResult:
    return ClassificationResult(
        mode="unified",
        confidence=1.0,
        reason=["single_tingt_style_for_all_contacts"],
    )
