import json
import os
import urllib.error
import urllib.request

from twisted.internet import threads
from evennia.utils import logger


OLLAMA_URL = os.getenv("SIZA_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("SIZA_OLLAMA_MODEL", "qwen3:8b")
OLLAMA_NUM_CTX = int(os.getenv("SIZA_OLLAMA_NUM_CTX", "8192"))

SYSTEM_PROMPT = """Eres el narrador de Siza. No eres el motor del juego.
El WORLD ENGINE ya resolvio la geometria, el movimiento y el estado.
Narra solamente la consecuencia inmediata contenida en el paquete recibido.
No inventes Rooms, Exits, NPC, objetos, pistas, puertas, resultados ni cambios de estado.
Escribe en espanol natural, concreto e inmersivo. No expliques mecanicas ni menciones el paquete de datos.
"""


def _json_safe(value):
    """Convert Evennia SaverDict/SaverList and nested values into plain JSON data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    # Evennia's persistent _SaverDict is dict-like but is not directly JSON serializable.
    if isinstance(value, dict) or hasattr(value, "items"):
        try:
            return {str(key): _json_safe(item) for key, item in value.items()}
        except Exception:
            pass

    # Covers normal sequences and Evennia's persistent SaverList-like containers.
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [_json_safe(item) for item in value]
        except Exception:
            pass

    # Last-resort safeguard: never let a persistence wrapper kill narration.
    return str(value)


def _visible_contents(room, exclude=None):
    result = []
    if not room:
        return result
    for obj in room.contents:
        if obj == exclude or getattr(obj, "destination", None):
            continue
        result.append(obj.key)
    return result


def build_move_packet(character, source, destination, exit_obj):
    packet = {
        "event": "movement_success",
        "actor": character.key,
        "from": {
            "room_id": source.db.room_id if source else None,
            "name": source.key if source else None,
        },
        "to": {
            "room_id": destination.db.room_id if destination else None,
            "name": destination.key if destination else None,
            "base_description": destination.db.desc if destination else None,
            "sensory_facts": destination.db.sensory_facts if destination else {},
            "visible_contents": _visible_contents(destination, exclude=character),
            "conditions": destination.db.conditions if destination else {},
        },
        "exit": {
            "name": exit_obj.key,
            "exit_id": exit_obj.db.exit_id,
            "door_state": exit_obj.db.door_state,
        },
        "resolution": "SUCCESS",
        "instruction": "Narra la llegada en 60-120 palabras. Usa solo hechos autorizados arriba.",
    }
    return _json_safe(packet)


def _post_chat(payload):
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(_json_safe(payload), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar con Ollama en {OLLAMA_URL}: {exc.reason}") from exc

    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def _request_chat(packet):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(_json_safe(packet), ensure_ascii=False, indent=2)},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.65,
            "num_predict": 220,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }

    try:
        data = _post_chat(payload)
    except RuntimeError as exc:
        # Older Ollama builds may reject the top-level 'think' option.
        if "HTTP 400" in str(exc):
            retry_payload = dict(payload)
            retry_payload.pop("think", None)
            data = _post_chat(retry_payload)
        else:
            raise

    return data.get("message", {}).get("content", "").strip()


def narrate_move_async(character, source, destination, exit_obj):
    packet = build_move_packet(character, source, destination, exit_obj)
    deferred = threads.deferToThread(_request_chat, packet)

    def _ok(text):
        if text:
            character.msg("\n" + text)
        else:
            character.msg(f"\nLlegas a {destination.key}.")

    def _failed(failure):
        reason = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
        logger.log_err(f"SIZA Ollama narrator error: {reason}")
        short_reason = reason.replace("\n", " ")[:220]
        character.msg(f"\nLlegas a {destination.key}. [Ollama error: {short_reason}]")

    deferred.addCallbacks(_ok, _failed)
    return deferred
