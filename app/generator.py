import os
import re
import requests

from openai import OpenAI
from openai import OpenAIError


def clean_reply(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = strip_meta_reasoning(cleaned)
    return cleaned.strip()


def normalize_for_echo_check(text: str) -> str:
    cleaned = re.sub(r"[\\s\\u3000]+", "", text)
    cleaned = re.sub(r"[，。！？!?、,.~～…：:；;（）()【】\\[\\]\"'`]+", "", cleaned)
    return cleaned.strip().lower()


def is_echo_reply(user_message: str, reply: str) -> bool:
    user_norm = normalize_for_echo_check(user_message)
    reply_norm = normalize_for_echo_check(reply)
    if not user_norm or not reply_norm:
        return False
    if len(user_norm) > 24:
        return False
    return user_norm == reply_norm


def strip_meta_reasoning(text: str) -> str:
    cleaned = text.strip()
    lower = cleaned.lower()
    meta_markers = [
        "the user sent",
        "according to the",
        "good responses would be",
        "i should respond",
        "let me try",
        "actually,",
        "the unified style rule",
    ]
    if any(marker in lower for marker in meta_markers):
        quoted = re.findall(r"[\"“”'`]?([\u4e00-\u9fff][^\"“”'`\n]{1,80})[\"“”'`]?", cleaned)
        quoted = [q.strip(" ：:，,。. ") for q in quoted if re.search(r"[\u4e00-\u9fff]", q)]
        if quoted:
            return quoted[-1]

        chinese_lines = [
            line.strip(" -•*")
            for line in cleaned.splitlines()
            if re.search(r"[\u4e00-\u9fff]", line) and not re.search(r"[A-Za-z]{4,}", line)
        ]
        if chinese_lines:
            return chinese_lines[-1]

        return ""

    return cleaned


def ensure_non_empty_reply(text: str, provider: str) -> str:
    cleaned = clean_reply(text)
    if not cleaned:
        raise RuntimeError(f"{provider}_empty_reply")
    return cleaned


def build_user_prompt(user_message: str) -> str:
    return (
        f"Incoming message:\n{user_message}\n\n"
        "Reply as TingT in one unified voice.\n"
        "Do not reflexively ask the user back.\n"
        "Prefer 1-3 short spoken-Chinese sentences.\n"
        "First give your own reaction, state, judgment, or a small real-life fragment.\n"
        "Only ask a follow-up question if missing context truly blocks a natural reply.\n"
        "If you do ask, keep it secondary rather than making the whole reply just a question.\n"
        "Never repeat the user's exact wording as the whole reply.\n"
        "If the user throws out a short call, exclamation, or name, react to it rather than echoing it.\n"
        "Avoid habitual endings like '你呢' '咋了' '找我啥事' unless really necessary.\n"
        "Output only the final Chinese reply text. Do not show analysis, policy, reasoning, or candidate responses."
    )


def generate_reply(prompt: str, user_message: str) -> str:
    provider = os.getenv("MODEL_PROVIDER", "openai").lower()

    if provider == "siliconflow":
        return generate_reply_siliconflow(prompt, user_message)

    if provider == "minimax":
        return generate_reply_minimax(prompt, user_message)

    if provider == "gemini":
        return generate_reply_gemini(prompt, user_message)

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
            max_output_tokens=400,
        )
        return ensure_non_empty_reply(response.output_text, "openai")
    except OpenAIError as exc:
        raise RuntimeError(f"openai_error: {exc}") from exc


def generate_reply_siliconflow(prompt: str, user_message: str) -> str:
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-72B-Instruct")

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
            max_tokens=400,
        )
        return ensure_non_empty_reply(response.choices[0].message.content or "", "siliconflow")
    except OpenAIError as exc:
        raise RuntimeError(f"siliconflow_error: {exc}") from exc


def generate_reply_gemini(prompt: str, user_message: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
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
            }
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
            return ensure_non_empty_reply(
                data["candidates"][0]["content"]["parts"][0]["text"],
                "gemini",
            )
        except Exception as exc:
            raise RuntimeError(f"gemini_parse_error[{model}]: {data}") from exc

    raise RuntimeError(last_error or "gemini_error: unknown")


def generate_reply_minimax(prompt: str, user_message: str) -> str:
    api_key = os.getenv("MINIMAX_API_KEY")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is missing")

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        user_prompt = build_user_prompt(user_message)
        for attempt in range(2):
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
                max_tokens=400,
            )
            reply = ensure_non_empty_reply(response.choices[0].message.content or "", "minimax")
            if not is_echo_reply(user_message, reply):
                return reply
            user_prompt = (
                build_user_prompt(user_message)
                + "\nThis time do not echo the user's exact wording. "
                + "Reply with reaction, stance, or one short continuation fragment."
            )
        raise RuntimeError("minimax_echo_reply")
    except OpenAIError as exc:
        raise RuntimeError(f"minimax_error: {exc}") from exc
