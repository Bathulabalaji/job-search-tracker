import json
from typing import Any

# A comment line: keeps the connection alive through proxies while a model call is in flight.
# Both clients' parsers ignore it.
PING = ": ping\n\n"


def sse(seq: int, event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"id: {seq}\nevent: {event}\ndata: {payload}\n\n"
