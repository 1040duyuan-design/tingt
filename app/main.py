import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from .classifier import classify_contact
from .chat_logging import log_chat_event
from .chat_persistence import (
    expected_debug_key,
    hash_ip,
    init_chat_db,
    insert_chat_message,
    load_latest_session,
    load_recent_real_messages,
    masked_hash,
    upsert_session,
)
from .fallbacks import FALLBACK_REPLY, blocked_reply
from .generator import generate_reply
from .models import IncomingMessage, ReplyResponse
from .router import build_runtime_prompt
from .safety import safety_gate, soft_degrade_gate
from .special_mode import deactivate_special_mode
from .session_memory import (
    append_assistant_message,
    append_user_message,
    get_session_history,
)
from .web_models import WebChatRequest, WebChatResponse


load_dotenv()

app = FastAPI(title="TingT WeChat Clone", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static")), name="static")


@app.on_event("startup")
def startup() -> None:
    init_chat_db()


@app.get("/health")
def health() -> dict:
    provider = os.getenv("MODEL_PROVIDER", "minimax").strip()
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7").strip()

    if provider == "siliconflow":
        model = os.getenv("SILICONFLOW_MODEL", model).strip()
    elif provider == "gemini":
        model = os.getenv("GEMINI_MODEL", model).strip()
    elif provider == "minimax":
        model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7").strip()
    elif provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()

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


@app.get("/__internal/latest-session")
def latest_session(x_debug_key: str | None = Header(default=None)) -> dict:
    expected = expected_debug_key()
    if not expected or x_debug_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    latest = load_latest_session()
    if not latest:
        return {"ok": True, "session": None}
    return {"ok": True, "session": latest}


@app.get("/__internal/recent-real-messages")
def recent_real_messages(
    limit: int = 2,
    x_debug_key: str | None = Header(default=None),
) -> dict:
    expected = expected_debug_key()
    if not expected or x_debug_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    safe_limit = max(1, min(limit, 20))
    return {
        "ok": True,
        "messages": load_recent_real_messages(safe_limit),
    }


@app.get("/__internal/runtime-config")
def runtime_config(x_debug_key: str | None = Header(default=None)) -> dict:
    expected = expected_debug_key()
    if not expected or x_debug_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    provider = os.getenv("MODEL_PROVIDER", "minimax").strip()
    return {
        "ok": True,
        "provider": provider,
        "model": (
            os.getenv("MINIMAX_MODEL", "MiniMax-M2.7").strip()
            if provider == "minimax"
            else os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
        ),
        "minimax_base_url": os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1").strip(),
        "minimax_key_hash": masked_hash(os.getenv("MINIMAX_API_KEY")),
        "debug_key_hash": masked_hash(expected),
    }


@app.post("/generate-reply", response_model=ReplyResponse)
def generate(payload: IncomingMessage) -> ReplyResponse:
    classification = classify_contact(payload.contact, payload.message, history=None)
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
def web_chat(request: Request, payload: WebChatRequest) -> WebChatResponse:
    # Web MVP has no real contact identity yet, so use a generic browser visitor label.
    contact = "web_visitor"
    browser_history = [
        {"role": item.role, "content": item.content}
        for item in payload.history
        if item.role in {"user", "assistant"} and item.content.strip()
    ]
    classification = classify_contact(
        contact,
        payload.message,
        history=browser_history,
        session_id=payload.session_id,
    )
    now = datetime.now(timezone.utc).isoformat()
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    upsert_session(
        payload.session_id,
        now,
        source="web",
        user_agent=request.headers.get("user-agent"),
        ip_hash=hash_ip(client_ip),
    )
    insert_chat_message(
        session_id=payload.session_id,
        role="user",
        content=payload.message,
        mode=classification.mode,
        confidence=classification.confidence,
        degraded=False,
        reason=None,
        attempt=None,
        history_turns=len(browser_history),
        created_at=now,
    )

    soft_degrade_reason = soft_degrade_gate(payload.message)
    if soft_degrade_reason:
        deactivate_special_mode(payload.session_id, reason=soft_degrade_reason)
        classification.mode = "unified"
        reply = blocked_reply(soft_degrade_reason)
        log_chat_event(
            "web_chat_soft_degraded",
            session_id=payload.session_id,
            message=payload.message,
            reason=soft_degrade_reason,
        )
        insert_chat_message(
            session_id=payload.session_id,
            role="assistant",
            content=reply,
            mode="unified",
            confidence=classification.confidence,
            degraded=True,
            reason=soft_degrade_reason,
            attempt="soft_degrade",
            history_turns=len(browser_history),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return WebChatResponse(
            ok=True,
            reply=reply,
            mode="unified",
            confidence=classification.confidence,
            degraded=True,
            reason=soft_degrade_reason,
        )

    # Web chat should still answer normal low-context questions.
    # Only block clearly sensitive topics here; do not block generic visitors
    # just because relationship confidence is still low.
    allowed, blocked_reason = safety_gate(
        payload.message,
        classification.confidence,
        block_low_confidence=False,
        history=browser_history,
    )

    if not allowed:
        deactivate_special_mode(payload.session_id, reason=blocked_reason or "blocked")
        classification.mode = "unified"
        log_chat_event(
            "web_chat_blocked",
            session_id=payload.session_id,
            message=payload.message,
            mode=classification.mode,
            confidence=classification.confidence,
            reason=blocked_reason,
        )
        insert_chat_message(
            session_id=payload.session_id,
            role="assistant",
            content=blocked_reply(blocked_reason),
            mode="unified",
            confidence=classification.confidence,
            degraded=True,
            reason=blocked_reason,
            attempt="blocked",
            history_turns=len(browser_history),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return WebChatResponse(
            ok=True,
            reply=blocked_reply(blocked_reason),
            mode="unified",
            confidence=classification.confidence,
            degraded=True,
            reason=blocked_reason,
        )

    history = browser_history if browser_history else get_session_history(payload.session_id)
    attempts = [
        ("full_context", history),
        ("recent_context", history[-4:]),
        ("no_context", []),
    ]
    last_error = None

    for attempt_name, attempt_history in attempts:
        prompt = build_runtime_prompt(contact, classification.mode, history=attempt_history)
        try:
            reply = generate_reply(prompt, payload.message)
            append_user_message(payload.session_id, payload.message)
            append_assistant_message(payload.session_id, reply)
            log_chat_event(
                "web_chat_reply",
                session_id=payload.session_id,
                message=payload.message,
                reply=reply,
                mode=classification.mode,
                confidence=classification.confidence,
                degraded=False,
                history_turns=len(attempt_history),
                attempt=attempt_name,
            )
            insert_chat_message(
                session_id=payload.session_id,
                role="assistant",
                content=reply,
                mode=classification.mode,
                confidence=classification.confidence,
                degraded=False,
                reason=None,
                attempt=attempt_name,
                history_turns=len(attempt_history),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            return WebChatResponse(
                ok=True,
                reply=reply,
                mode=classification.mode,
                confidence=classification.confidence,
                degraded=False,
                reason=None,
            )
        except RuntimeError as exc:
            last_error = str(exc)
            log_chat_event(
                "web_chat_retry",
                session_id=payload.session_id,
                message=payload.message,
                mode=classification.mode,
                confidence=classification.confidence,
                reason=last_error,
                history_turns=len(attempt_history),
                attempt=attempt_name,
            )
    log_chat_event(
        "web_chat_degraded",
        session_id=payload.session_id,
        message=payload.message,
        mode=classification.mode,
        confidence=classification.confidence,
        degraded=True,
        reason=last_error,
        history_turns=len(history),
    )
    insert_chat_message(
        session_id=payload.session_id,
        role="assistant",
        content=FALLBACK_REPLY,
        mode=classification.mode,
        confidence=classification.confidence,
        degraded=True,
        reason=last_error,
        attempt="degraded_fallback",
        history_turns=len(history),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return WebChatResponse(
        ok=True,
        reply=FALLBACK_REPLY,
        mode=classification.mode,
        confidence=classification.confidence,
        degraded=True,
        reason=last_error,
    )
