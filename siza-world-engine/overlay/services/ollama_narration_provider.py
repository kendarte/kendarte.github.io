import json
import os
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_PROVIDER_BUILD = "0.66.1-local-ollama-grounded-narration"
DEFAULT_OLLAMA_ENDPOINT = os.environ.get("SIZA_OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/chat")
DEFAULT_OLLAMA_MODEL = os.environ.get("SIZA_OLLAMA_MODEL", "qwen3:8b")
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_NUM_PREDICT = 192


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def build_ollama_chat_payload(
    provider_payload,
    model=DEFAULT_OLLAMA_MODEL,
    num_predict=DEFAULT_NUM_PREDICT,
    temperature=0,
):
    """Translate only the grounded provider boundary into Ollama's /api/chat schema."""
    provider = _plain_dict(provider_payload)
    system = str(provider.get("system") or "")
    prompt = str(provider.get("prompt") or "")
    try:
        num_predict = max(1, int(num_predict))
    except (TypeError, ValueError):
        num_predict = DEFAULT_NUM_PREDICT
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.0

    return {
        "model": str(model or DEFAULT_OLLAMA_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }


def parse_ollama_chat_response(raw, http_status=200):
    """Parse one non-streaming Ollama chat response without mutating game state."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {
                "status": "INVALID_ENCODING",
                "http_status": int(http_status or 0),
                "text": "",
                "response": None,
            }
    if isinstance(raw, str):
        try:
            packet = json.loads(raw)
        except (TypeError, ValueError):
            return {
                "status": "INVALID_JSON",
                "http_status": int(http_status or 0),
                "text": "",
                "response": None,
            }
    else:
        packet = _plain_dict(raw)

    if not packet:
        return {
            "status": "INVALID_RESPONSE",
            "http_status": int(http_status or 0),
            "text": "",
            "response": packet,
        }

    message = _plain_dict(packet.get("message"))
    text = str(message.get("content") or "").strip()
    if not message:
        status = "INVALID_RESPONSE"
    elif not text:
        status = "EMPTY_CONTENT"
    else:
        status = "OK"

    return {
        "status": status,
        "http_status": int(http_status or 0),
        "text": text,
        "model": packet.get("model"),
        "done": packet.get("done"),
        "done_reason": packet.get("done_reason"),
        "prompt_eval_count": packet.get("prompt_eval_count"),
        "eval_count": packet.get("eval_count"),
        "response": packet,
    }


def call_ollama_chat(
    provider_payload,
    endpoint=DEFAULT_OLLAMA_ENDPOINT,
    model=DEFAULT_OLLAMA_MODEL,
    timeout=DEFAULT_TIMEOUT_SECONDS,
    num_predict=DEFAULT_NUM_PREDICT,
    temperature=0,
):
    """Call local Ollama synchronously and return a structured status instead of raising transport errors."""
    chat_payload = build_ollama_chat_payload(
        provider_payload,
        model=model,
        num_predict=num_predict,
        temperature=temperature,
    )
    encoded = json.dumps(chat_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(
        str(endpoint or DEFAULT_OLLAMA_ENDPOINT),
        data=encoded,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        timeout_value = max(0.05, float(timeout))
    except (TypeError, ValueError):
        timeout_value = DEFAULT_TIMEOUT_SECONDS

    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_value) as response:
            http_status = int(getattr(response, "status", 200) or 200)
            raw = response.read()
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {
            "status": "HTTP_ERROR",
            "build": OLLAMA_PROVIDER_BUILD,
            "endpoint": str(endpoint),
            "model": str(model),
            "http_status": int(getattr(exc, "code", 0) or 0),
            "error": body or str(exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "request_payload": chat_payload,
            "text": "",
        }
    except (URLError, socket.timeout, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        is_timeout = isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, socket.timeout)
        return {
            "status": "TIMEOUT" if is_timeout else "TRANSPORT_ERROR",
            "build": OLLAMA_PROVIDER_BUILD,
            "endpoint": str(endpoint),
            "model": str(model),
            "http_status": 0,
            "error": str(reason or exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "request_payload": chat_payload,
            "text": "",
        }

    parsed = parse_ollama_chat_response(raw, http_status=http_status)
    parsed.update(
        {
            "build": OLLAMA_PROVIDER_BUILD,
            "endpoint": str(endpoint),
            "requested_model": str(model),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "request_payload": chat_payload,
        }
    )
    return parsed
