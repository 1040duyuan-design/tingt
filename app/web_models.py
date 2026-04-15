from pydantic import BaseModel, Field


class WebChatRequest(BaseModel):
    session_id: str = Field(..., description="Browser session identifier")
    message: str = Field(..., description="User message")


class WebChatResponse(BaseModel):
    ok: bool
    reply: str
    mode: str | None = None
    confidence: float | None = None
    degraded: bool = False
    reason: str | None = None
