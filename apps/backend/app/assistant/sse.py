import json
from typing import Any


def sse(seq: int, event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"id: {seq}\nevent: {event}\ndata: {payload}\n\n"
