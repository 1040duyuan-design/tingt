import os
import re
import requests

from openai import OpenAI
from openai import OpenAIError


def clean_reply(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


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
                    "content": f"Incoming message:\n{user_message}\n\nReply as TingT in the correct relationship mode.",
                },
            ],
            max_output_tokens=400,
        )
        return clean_reply(response.output_text)
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
                    "content": f"Incoming message:\n{user_message}\n\nReply as TingT in the correct relationship mode.",
                },
            ],
            temperature=0.8,
            max_tokens=400,
        )
        return clean_reply(response.choices[0].message.content or "")
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
                            f"{prompt}\n\nIncoming message:\n{user_message}\n\n"
                            "Reply as TingT in the correct relationship mode."
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
            return clean_reply(data["candidates"][0]["content"]["parts"][0]["text"])
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
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Incoming message:\n{user_message}\n\nReply as TingT in the correct relationship mode.",
                },
            ],
            temperature=0.8,
            max_tokens=400,
        )
        return clean_reply(response.choices[0].message.content or "")
    except OpenAIError as exc:
        raise RuntimeError(f"minimax_error: {exc}") from exc
