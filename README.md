# TingT Web Clone V1

This is the current runnable web MVP for TingT's digital clone.

Current design choices:

- Model provider: MiniMax
- Model: `MiniMax-M2.5`
- Interaction surface: web chat
- Contact scope: all users share one unified TingT style
- Relationship routing: disabled
- Fallback behavior: retry once, then use lightweight network fallback text

Important:

- This is a public-web experimental setup, not a WeChat bridge.
- Keep `.env` local only.
- Do not commit real API keys.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8787
```

## Deploy to Render

This project is Render-ready.

Render file:

- `render.yaml`

Required env vars:

- `MODEL_PROVIDER=minimax`
- `MINIMAX_MODEL=MiniMax-M2.5`
- `MINIMAX_BASE_URL=https://api.minimaxi.com/v1`
- `MINIMAX_API_KEY=<real key>`

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Directory overview

- `persona/`
  - distilled persona assets
- `app/`
  - FastAPI app, prompt loading, generator, safety, routing
- `templates/`
  - Jinja HTML
- `static/`
  - CSS and browser-side JS
- `runtime/`
  - runtime rules and policy docs
- `config/`
  - config placeholders
