import json
import os
import urllib.error
import urllib.request

from twisted.internet import threads
from evennia.utils import logger


OLLAMA_URL = os.getenv("SIZA_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("SIZA_OLLAMA_MODEL", "qwen3:8b")
OLLAMA_NUM_CTX = int(os.getenv("SIZA_OLLAMA_NUM_CTX", "8192"))

SYSTEM_PROMPT = """Eres la capa de prosa de Siza. NO eres el motor del juego.
El WORLD ENGINE ya decidio geometria, movimiento, estado, percepcion y descubrimientos.
Tu unica tarea es convertir hechos autorizados en prosa natural, clara y competente.

REGLAS DURAS
- No inventes Rooms, Exits, NPC, muebles, objetos, olores, temperatura, iluminacion, sonidos,
  emociones, pistas, materiales, clima, resultados ni cambios de estado.
- Una lista vacia significa 'no hay datos autorizados', NO significa que esas cosas no existan.
- No completes huecos con atmosfera generica.
- No conviertas ausencia de datos en afirmaciones como 'no hay nadie', 'no hay muebles' o 'esta vacio'.
- No expliques mecanicas ni menciones JSON, paquetes, World Engine o instrucciones internas.
- Si una tirada no descubre nada, no inventes una pista compensatoria.

ESTILO SIZA
- Espanol contemporaneo, fluido y concreto. No arcaico, no grandilocuente, no pseudo-poetico.
- Prioriza orientacion espacial y acciones fisicas que ayuden a imaginar el lugar.
- Evita redundancias y frases mecanicas.
- Evita abusar de 'el ambiente es', 'se percibe', 'se siente', 'parece' y adjetivos emocionales genericos.
- No describas una salida con tautologias.

MAL: 'La unica salida es salir a la plaza.'
BIEN: 'A tu espalda, el acceso devuelve a la Plaza de Recepcion.'
MAL: 'El ambiente es calido y acogedor.' si temperatura y atmosfera no fueron autorizadas.
BIEN: usa solo la forma, elementos y sensaciones que aparezcan expresamente en los datos.
MAL: 'No hay muebles ni personas.' cuando las listas vienen vacias.
BIEN: simplemente no menciones muebles ni personas.

La prosa puede enlazar hechos con naturalidad, pero nunca agregar hechos nuevos.
"""


def _json_safe(value):
    """Convert Evennia persistence wrappers and nested values into plain JSON data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict) or hasattr(value, "items"):
        try:
            return {str(key): _json_safe(item) for key, item in value.items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [_json_safe(item) for item in value]
        except Exception:
            pass
    return str(value)


def _visible_contents(room, exclude=None):
    result = []
    if not room:
        return result
    for obj in room.contents:
        if obj == exclude or getattr(obj, "destination", None):
            continue
        if getattr(obj.db, "hidden", False):
            continue
        result.append(obj.key)
    return result


def _room_exits(room):
    result = []
    if not room:
        return result
    for exit_obj in getattr(room, "exits", []) or []:
        result.append(
            {
                "name": exit_obj.key,
                "destination": exit_obj.destination.key if exit_obj.destination else None,
                "door_state": exit_obj.db.door_state,
                "is_locked": bool(exit_obj.db.is_locked),
            }
        )
    return result


def _room_packet(room, exclude=None):
    if not room:
        return {}
    return _json_safe(
        {
            "room_id": room.db.room_id,
            "name": room.key,
            "base_description": room.db.desc,
            "space_profile": room.db.space_profile or {},
            "sensory_facts": room.db.sensory_facts or {},
            "visible_contents": _visible_contents(room, exclude=exclude),
            "exits": _room_exits(room),
            "conditions": room.db.conditions or {},
        }
    )


def build_move_packet(character, source, destination, exit_obj):
    return _json_safe(
        {
            "mode": "MOVE",
            "event": "movement_success",
            "actor": character.key,
            "from": {
                "room_id": source.db.room_id if source else None,
                "name": source.key if source else None,
            },
            "to": _room_packet(destination, exclude=character),
            "used_exit": {
                "name": exit_obj.key,
                "exit_id": exit_obj.db.exit_id,
                "door_state": exit_obj.db.door_state,
            },
            "resolution": "SUCCESS",
            "instruction": (
                "Narra solamente la llegada inmediata en 45-90 palabras. "
                "Ayuda a orientar al lector en el espacio. No enumeres todas las salidas salvo que sea natural. "
                "No inventes detalle ambiental para llenar espacio."
            ),
        }
    )


def build_perception_packet(character, result):
    room = getattr(character, "location", None)
    status = result.get("status")

    instructions = {
        "OBSERVED": (
            "Describe lo que el personaje puede captar sin tirada. Prioriza forma y orientacion. "
            "Incluye solo hechos obvios, hechos ya descubiertos y datos espaciales autorizados."
        ),
        "AUTO_SUCCESS": (
            "El objetivo solicitado esta claramente visible. Indicalo de manera natural; no inventes detalles del objetivo."
        ),
        "DISCOVERY": (
            "Narra el descubrimiento de los hechos nuevos autorizados. No anadas pistas, causas ni interpretaciones nuevas."
        ),
        "NO_DISCOVERY": (
            "La busqueda no produjo ningun detalle nuevo. Narralo brevemente sin afirmar que el objetivo no existe."
        ),
        "NO_AUTHORIZED_DISCOVERY": (
            "No existe ningun hecho autorizado que esta accion pueda revelar aqui. Narralo brevemente como una busqueda "
            "sin resultado concreto; no inventes una pista y no declares que el objetivo es imposible o inexistente."
        ),
    }

    return _json_safe(
        {
            "mode": "PERCEPTION",
            "actor": character.key,
            "room": _room_packet(room, exclude=character),
            "resolution": result,
            "instruction": instructions.get(status, "Narra solamente los hechos autorizados en 35-85 palabras."),
        }
    )


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
            "temperature": 0.45,
            "num_predict": 190,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }

    try:
        data = _post_chat(payload)
    except RuntimeError as exc:
        if "HTTP 400" in str(exc):
            retry_payload = dict(payload)
            retry_payload.pop("think", None)
            data = _post_chat(retry_payload)
        else:
            raise

    return data.get("message", {}).get("content", "").strip()


def _narrate_async(character, packet, fallback_text):
    deferred = threads.deferToThread(_request_chat, packet)

    def _ok(text):
        if text:
            character.msg("\n" + text)
        else:
            character.msg("\n" + fallback_text)

    def _failed(failure):
        reason = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
        logger.log_err(f"SIZA Ollama narrator error: {reason}")
        short_reason = reason.replace("\n", " ")[:220]
        character.msg(f"\n{fallback_text} [Ollama error: {short_reason}]")

    deferred.addCallbacks(_ok, _failed)
    return deferred


def narrate_move_async(character, source, destination, exit_obj):
    packet = build_move_packet(character, source, destination, exit_obj)
    return _narrate_async(character, packet, f"Llegas a {destination.key}.")


def narrate_perception_async(character, result):
    packet = build_perception_packet(character, result)
    status = result.get("status")
    if status == "DISCOVERY" and result.get("discovered"):
        fallback = "Descubres: " + "; ".join(result["discovered"])
    elif status == "AUTO_SUCCESS" and result.get("visible_targets"):
        fallback = "Ves: " + ", ".join(result["visible_targets"])
    elif status == "OBSERVED":
        fallback = "Observas el lugar sin encontrar nada que requiera una tirada."
    else:
        fallback = "La busqueda no revela ningun detalle nuevo."
    return _narrate_async(character, packet, fallback)
