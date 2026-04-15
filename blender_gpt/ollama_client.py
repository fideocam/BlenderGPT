"""HTTP client for Ollama /api/chat (non-streaming)."""

from __future__ import annotations

import json
import ssl
import threading
import urllib.error
import urllib.request
from typing import Any, Optional


def _normalize_base(url: str) -> str:
    return (url or "").strip().rstrip("/")


def chat_completion(
    base_url: str,
    model: str,
    system: str,
    user: str,
    num_ctx: int = 0,
    cancel_event: Optional[threading.Event] = None,
    timeout: float = 600.0,
) -> str:
    """
    POST /api/chat with stream:false. Returns assistant message content.
    If cancel_event is set and becomes true before the request finishes, raises InterruptedError.
    """
    base = _normalize_base(base_url)
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if num_ctx and num_ctx > 0:
        payload["options"] = {"num_ctx": int(num_ctx)}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Cancelled before read")
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ollama HTTP {e.code}: {err_body or e.reason}") from e

    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Cancelled")

    try:
        obj = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from Ollama: {body[:500]}") from e

    msg = obj.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected Ollama response shape: {str(obj)[:500]}")
    return content


def check_connection(base_url: str, timeout: float = 3.0) -> bool:
    base = _normalize_base(base_url)
    url = f"{base}/api/tags"
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
            code = getattr(resp, "status", None)
            if code is None:
                code = resp.getcode()
            return 200 <= int(code) < 300
    except Exception:
        return False
