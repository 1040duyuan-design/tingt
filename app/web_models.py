from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Chat content")


class WebChatRequest(BaseModel):
    session_id: str = Field(..., description="Browser session identifier")
    message: str = Field(..., description="User message")
    history: list[ChatTurn] = Field(default_factory=list, description="Recent browser chat history")


class WebChatResponse(BaseModel):
    ok: bool
    reply: str
    mode: str | None = None
    confidence: float | None = None
    degraded: bool = False
    reason: str | None = None
