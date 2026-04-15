from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    contact: str = Field(..., description="Human-readable contact name")
    message: str = Field(..., description="Incoming message content")


class ClassificationResult(BaseModel):
    mode: str
    confidence: float
    reason: list[str]


class ReplyResponse(BaseModel):
    contact: str
    mode: str
    confidence: float
    allowed_to_send: bool
    blocked_reason: str | None = None
    reply: str | None = None
