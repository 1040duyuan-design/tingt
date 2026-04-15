import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from .classifier import classify_contact
from .fallbacks import FALLBACK_REPLY
from .generator import generate_reply
from .models import IncomingMessage, ReplyResponse
from .router import build_runtime_prompt
from .safety import safety_gate
from .web_models import WebChatRequest, WebChatResponse


load_dotenv()

app = FastAPI(title="TingT WeChat Clone", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static")), name="static")


@app.get("/health")
def health() -> dict:
    provider = os.getenv("MODEL_PROVIDER", "openai")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    if provider == "siliconflow":
        model = os.getenv("SILICONFLOW_MODEL", model)
    elif provider == "gemini":
        model = os.getenv("GEMINI_MODEL", model)
    elif provider == "minimax":
        model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    return {
        "ok": True,
        "service": "tingt-wechat-clone",
        "provider": provider,
        "model": model,
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "和 TingT 聊聊",
            "subtitle": "这是 TingT 的数字分身测试版。",
        },
    )


@app.post("/generate-reply", response_model=ReplyResponse)
def generate(payload: IncomingMessage) -> ReplyResponse:
    classification = classify_contact(payload.contact, payload.message)
    allowed, blocked_reason = safety_gate(payload.message, classification.confidence)

    if not allowed:
        return ReplyResponse(
            contact=payload.contact,
            mode=classification.mode,
            confidence=classification.confidence,
            allowed_to_send=False,
            blocked_reason=blocked_reason,
            reply=None,
        )

    prompt = build_runtime_prompt(payload.contact, classification.mode)
    try:
        reply = generate_reply(prompt, payload.message)
    except RuntimeError as exc:
        return ReplyResponse(
            contact=payload.contact,
            mode=classification.mode,
            confidence=classification.confidence,
            allowed_to_send=False,
            blocked_reason=str(exc),
            reply=None,
        )

    return ReplyResponse(
        contact=payload.contact,
        mode=classification.mode,
        confidence=classification.confidence,
        allowed_to_send=True,
        blocked_reason=None,
        reply=reply,
    )


@app.post("/chat", response_model=WebChatResponse)
def web_chat(payload: WebChatRequest) -> WebChatResponse:
    # Web MVP has no real contact identity yet, so use a generic browser visitor label.
    contact = "web_visitor"
    classification = classify_contact(contact, payload.message)
    # Web chat should still answer normal low-context questions.
    # Only block clearly sensitive topics here; do not block generic visitors
    # just because relationship confidence is still low.
    allowed, blocked_reason = safety_gate(
        payload.message,
        classification.confidence,
        block_low_confidence=False,
    )

    if not allowed:
        return WebChatResponse(
            ok=True,
            reply=FALLBACK_REPLY,
            mode=classification.mode,
            confidence=classification.confidence,
            degraded=True,
            reason=blocked_reason,
        )

    prompt = build_runtime_prompt(contact, classification.mode)
    try:
        reply = generate_reply(prompt, payload.message)
        return WebChatResponse(
            ok=True,
            reply=reply,
            mode=classification.mode,
            confidence=classification.confidence,
            degraded=False,
            reason=None,
        )
    except RuntimeError as exc:
        return WebChatResponse(
            ok=True,
            reply=FALLBACK_REPLY,
            mode=classification.mode,
            confidence=classification.confidence,
            degraded=True,
            reason=str(exc),
        )
