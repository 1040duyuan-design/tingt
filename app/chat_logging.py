import json
import logging


logger = logging.getLogger("tingt_chat")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_chat_event(event: str, **payload) -> None:
    body = {"event": event, **payload}
    logger.info(json.dumps(body, ensure_ascii=False))
