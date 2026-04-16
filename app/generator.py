import os
import re
import requests

from openai import OpenAI
from openai import OpenAIError


def clean_reply(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = strip_meta_reasoning(cleaned)
    return cleaned.strip()


def english_ratio(text: str) -> float:
    letters = len(re.findall(r"[A-Za-z]", text))
    meaningful = len(re.findall(r"[\u4e00-\u9fffA-Za-z]", text))
    if meaningful == 0:
        return 0.0
    return letters / meaningful


def normalize_for_echo_check(text: str) -> str:
    cleaned = re.sub(r"[\\s\\u3000]+", "", text)
    cleaned = re.sub(r"[，。！？!?、,.~～…：:；;（）()【】\\[\\]\"'`]+", "", cleaned)
    return cleaned.strip().lower()


def is_echo_reply(user_message: str, reply: str) -> bool:
    user_norm = normalize_for_echo_check(user_message)
    reply_norm = normalize_for_echo_check(reply)
    if not user_norm or not reply_norm:
        return False
    if reply_norm in {"在"} and user_norm in {"在吗", "在嘛", "在不", "在?"}:
        return False
    if len(user_norm) > 24:
        if reply_norm and user_norm.endswith(reply_norm) and len(reply_norm) <= 8:
            return True
        return False
    if user_norm == reply_norm:
        return True
    if len(reply_norm) >= 2 and reply_norm in user_norm and len(reply_norm) / max(len(user_norm), 1) >= 0.6:
        return True
    return False


def strip_meta_reasoning(text: str) -> str:
    cleaned = text.strip()
    lower = cleaned.lower()
    meta_markers = [
        "the user sent",
        "the user said",
        "the user just said",
        "according to the",
        "good responses would be",
        "i should respond",
        "good response would be",
        "let me try",
        "let me analyze",
        "actually,",
        "the unified style rule",
        "the conversation so far",
        "looking at the conversation flow",
        "i'll capture the raw",
        "current contact:",
        "current mode:",
        "which means",
        "now tingt should",
        "in response to",
    ]
    if any(marker in lower for marker in meta_markers):
        chinese_lines = [
            line.strip(" -•*\"“”'`")
            for line in cleaned.splitlines()
            if re.search(r"[\u4e00-\u9fff]", line)
            and not re.search(r"[A-Za-z]{4,}", line)
            and not line.strip().startswith("-")
            and len(line.strip()) <= 40
        ]
        if chinese_lines:
            return chinese_lines[-1]

        return ""

    return cleaned


def has_meta_leak(text: str) -> bool:
    lower = text.lower()
    markers = [
        "the user said",
        "the user just said",
        "the user sent",
        "which means",
        "now tingt should",
        "in response to",
        "let me analyze",
        "the conversation so far",
        "current contact:",
        "current mode:",
    ]
    if any(marker in lower for marker in markers):
        return True
    if english_ratio(text) > 0.35 and len(re.findall(r"[A-Za-z]", text)) >= 12:
        return True
    if re.search(r"\b(step|scene|label|reasoning|analysis)\b", lower):
        return True
    return False


def looks_viewpoint_message(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "怎么看",
        "怎么理解",
        "你觉得",
        "判断",
        "分析",
        "详细阐述",
        "展开",
        "利大于弊",
        "利弊",
        "本质",
        "趋势",
        "现象",
        "行业",
        "工作",
        "宏观",
        "ai",
        "策略",
        "公检法",
        "为什么",
    ]
    return any(token in text for token in keywords) or any(token in lowered for token in keywords)


def looks_assistantish_structure(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        r"(^|\n)\s*\d+\.",
        r"(^|\n)\s*[一二三四五六七八九十]+[、.]",
        r"首先",
        r"其次",
        r"最后",
        r"综合来看",
        r"先说结论",
        r"可以从.{0,8}角度",
        r"本质上这是",
        r"建议从以下",
    ]
    if any(re.search(pattern, text) for pattern in patterns):
        return True
    if text.count("\n\n") >= 2 and len(text) >= 180:
        return True
    if text.count("**") >= 4:
        return True
    return "利大于弊" in text and len(text) >= 120


def needs_persona_rewrite(user_message: str, reply: str) -> bool:
    if looks_assistantish_structure(reply):
        return True
    if looks_viewpoint_message(user_message) and len(reply) >= 140:
        return True
    return False


def ensure_non_empty_reply(text: str, provider: str) -> str:
    cleaned = clean_reply(text)
    if not cleaned:
        raise RuntimeError(f"{provider}_empty_reply")
    if has_meta_leak(cleaned):
        raise RuntimeError(f"{provider}_meta_leak")
    return cleaned


def build_rewrite_prompt(user_message: str, draft_reply: str) -> str:
    return (
        f"用户原话：\n{user_message}\n\n"
        f"草稿回复：\n{draft_reply}\n\n"
        "把这段草稿改写成 TingT 本人会发出的微信回复。\n"
        "要求：\n"
        "- 保留原本判断和信息，不要扩写\n"
        "- 先给立场，再补一句\n"
        "- 像聊天，不像分析报告\n"
        "- 不要总分总\n"
        "- 不要编号列点\n"
        "- 不要首先/其次/最后\n"
        "- 不要像通用 assistant\n"
        "- 1到3句，中文口语，短一点\n"
        "- 只输出最终聊天正文\n"
    )


def rewrite_reply_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    user_message: str,
    draft_reply: str,
    max_output_tokens: int,
    provider_name: str,
) -> str:
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": build_rewrite_prompt(user_message, draft_reply)},
        ],
        temperature=0.8,
        max_tokens=max_output_tokens,
    )
    rewritten = ensure_non_empty_reply(response.choices[0].message.content or "", provider_name)
    if looks_assistantish_structure(rewritten):
        raise RuntimeError(f"{provider_name}_structured_reply_after_rewrite")
    return rewritten


def build_user_prompt(user_message: str) -> str:
    return (
        f"Incoming message:\n{user_message}\n\n"
        "Reply as TingT in one unified voice.\n"
        "Do not reflexively ask the user back.\n"
        "Prefer 1-3 short spoken-Chinese sentences.\n"
        "First give your own reaction, state, judgment, or a small real-life fragment.\n"
        "If the user is asking for a view, judgment, tradeoff, or work analysis, still keep TingT persona first.\n"
        "For those questions: start with a stance, then add one or two reasons.\n"
        "Do not use numbered lists, standard essay structure, or assistant-style total-summary writing.\n"
        "Only ask a follow-up question if missing context truly blocks a natural reply.\n"
        "If you do ask, keep it secondary rather than making the whole reply just a question.\n"
        "Never repeat the user's exact wording as the whole reply.\n"
        "If the user throws out a short call, exclamation, or name, react to it rather than echoing it.\n"
        "Avoid habitual endings like '你呢' '咋了' '找我啥事' unless really necessary.\n"
        "只输出最终聊天正文。\n"
        "不输出英文说明。\n"
        "不输出用户语义解释。\n"
        "不输出步骤、标签、推理、场景判断。\n"
        "Output only the final Chinese reply text. Do not show analysis, policy, reasoning, labels, scene judgments, or candidate responses."
    )


def generate_reply(prompt: str, user_message: str, *, max_output_tokens: int = 400) -> str:
    provider = os.getenv("MODEL_PROVIDER", "minimax").strip().lower()

    if provider == "siliconflow":
        return generate_reply_siliconflow(prompt, user_message, max_output_tokens=max_output_tokens)

    if provider == "minimax":
        return generate_reply_minimax(prompt, user_message, max_output_tokens=max_output_tokens)

    if provider == "gemini":
        return generate_reply_gemini(prompt, user_message, max_output_tokens=max_output_tokens)

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": build_user_prompt(user_message),
                },
            ],
            max_output_tokens=max_output_tokens,
        )
        reply = ensure_non_empty_reply(response.output_text, "openai")
        if needs_persona_rewrite(user_message, reply):
            reply = rewrite_reply_openai_compatible(
                api_key=api_key,
                base_url="https://api.openai.com/v1",
                model=model,
                prompt=prompt,
                user_message=user_message,
                draft_reply=reply,
                max_output_tokens=max_output_tokens,
                provider_name="openai",
            )
        return reply
    except OpenAIError as exc:
        raise RuntimeError(f"openai_error: {exc}") from exc


def generate_reply_siliconflow(prompt: str, user_message: str, *, max_output_tokens: int = 400) -> str:
    api_key = os.getenv("SILICONFLOW_API_KEY", "").strip()
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").strip()
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-72B-Instruct").strip()

    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY is missing")

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": build_user_prompt(user_message),
                },
            ],
            temperature=0.8,
            max_tokens=max_output_tokens,
        )
        reply = ensure_non_empty_reply(response.choices[0].message.content or "", "siliconflow")
        if needs_persona_rewrite(user_message, reply):
            reply = rewrite_reply_openai_compatible(
                api_key=api_key,
                base_url=base_url,
                model=model,
                prompt=prompt,
                user_message=user_message,
                draft_reply=reply,
                max_output_tokens=max_output_tokens,
                provider_name="siliconflow",
            )
        return reply
    except OpenAIError as exc:
        raise RuntimeError(f"siliconflow_error: {exc}") from exc


def generate_reply_gemini(prompt: str, user_message: str, *, max_output_tokens: int = 400) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    fallback_models = [
        m.strip()
        for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",")
        if m.strip()
    ]
    models = [primary_model, *fallback_models]

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            f"{prompt}\n\n{build_user_prompt(user_message)}"
                        )
                    }
                ]
            },
            {"parts": [{"text": f"Keep the reply within about {max_output_tokens} tokens."}]},
        ]
    }

    last_error = None
    for model in models:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code >= 400:
            last_error = f"gemini_error[{model}]: {resp.status_code} {resp.text}"
            if resp.status_code == 503:
                continue
            raise RuntimeError(last_error)

        data = resp.json()
        try:
            reply = ensure_non_empty_reply(
                data["candidates"][0]["content"]["parts"][0]["text"],
                "gemini",
            )
            return reply
        except Exception as exc:
            raise RuntimeError(f"gemini_parse_error[{model}]: {data}") from exc

    raise RuntimeError(last_error or "gemini_error: unknown")


def generate_reply_minimax(prompt: str, user_message: str, *, max_output_tokens: int = 400) -> str:
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1").strip()
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7").strip()

    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is missing")

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        user_prompt = build_user_prompt(user_message)
        for attempt in range(3):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0.8,
                max_tokens=max_output_tokens,
            )
            try:
                reply = ensure_non_empty_reply(response.choices[0].message.content or "", "minimax")
            except RuntimeError as exc:
                if str(exc) in {"minimax_meta_leak", "minimax_empty_reply"} and attempt < 2:
                    user_prompt = (
                        build_user_prompt(user_message)
                        + "\n只输出最终中文聊天正文。"
                        + " 不要英文，不要分析，不要解释，不要标签。"
                    )
                    continue
                raise
            if not is_echo_reply(user_message, reply):
                if needs_persona_rewrite(user_message, reply):
                    try:
                        reply = rewrite_reply_openai_compatible(
                            api_key=api_key,
                            base_url=base_url,
                            model=model,
                            prompt=prompt,
                            user_message=user_message,
                            draft_reply=reply,
                            max_output_tokens=max_output_tokens,
                            provider_name="minimax",
                        )
                    except RuntimeError:
                        pass
                return reply
            user_prompt = (
                build_user_prompt(user_message)
                + "\nThis time do not echo the user's exact wording. "
                + "Reply with reaction, stance, or one short continuation fragment."
            )
        raise RuntimeError("minimax_echo_reply")
    except OpenAIError as exc:
        raise RuntimeError(f"minimax_error: {exc}") from exc
