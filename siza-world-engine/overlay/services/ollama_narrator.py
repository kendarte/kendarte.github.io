import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

from twisted.internet import threads
from evennia.utils import logger

from services.narration_queue import run_serialized


NARRATOR_BUILD = "0.3.0-guard"
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
- No conviertas ausencia de datos en afirmaciones como 'no hay nadie', 'no hay muebles',
  'no esta aqui', 'no existe', 'esta vacio' o equivalentes.
- No inventes posiciones relativas ni cardinales. Palabras como izquierda, derecha, delante,
  detras, norte, sur, este u oeste SOLO pueden aparecer si los datos autorizados las dicen literalmente.
- No conviertas una conexion entre Rooms en una posicion espacial que no haya sido escrita.
- No expliques mecanicas ni menciones JSON, paquetes, World Engine o instrucciones internas.

ESTILO SIZA
- Espanol contemporaneo, fluido y concreto. No arcaico, no grandilocuente, no pseudo-poetico.
- Haz que el lector pueda imaginar el espacio usando unicamente geometria y elementos autorizados.
- Evita redundancias y frases mecanicas.
- Prefiere 2-4 oraciones limpias a rellenar el parrafo con detalles nuevos.

MAL: 'La unica salida es salir a la plaza.'
BIEN: 'El acceso comunica con la Plaza de Recepcion.'
MAL: 'A tu espalda esta la plaza' si esa posicion no fue autorizada.
MAL: 'El ambiente es calido y acogedor' si no hay datos de temperatura o atmosfera.
MAL: 'No hay muebles ni personas' cuando las listas vienen vacias.

La prosa puede enlazar y reformular hechos con naturalidad, pero nunca agregar hechos nuevos.
"""


def _normalize(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


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


def _plain_dict(value):
    if not value:
        return {}
    try:
        return {str(key): _json_safe(item) for key, item in value.items()}
    except Exception:
        return {}


def _plain_list(value):
    if not value:
        return []
    try:
        return [_json_safe(item) for item in value]
    except Exception:
        return []


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
            "used_connection": {
                "name": exit_obj.key,
                "exit_id": exit_obj.db.exit_id,
                "door_state": exit_obj.db.door_state,
            },
            "resolution": "SUCCESS",
            "instruction": (
                "Narra solamente la llegada inmediata en 30-60 palabras. "
                "Usa la forma del lugar y uno o dos elementos autorizados. "
                "No enumeres conexiones ni inventes orientacion o atmosfera."
            ),
        }
    )


def _first_sensory(room, sense):
    sensory = _plain_dict(room.db.sensory_facts if room else {})
    values = _plain_list(sensory.get(sense, []))
    return str(values[0]) if values else ""


def _clean_fragment(text):
    text = str(text or "").strip().rstrip(".")
    return text


def _sentence(text):
    text = _clean_fragment(text)
    if not text:
        return ""
    return text[0].upper() + text[1:] + "."


def _render_room_core(room, include_name=True):
    """Deterministic spatial prose made only from authored Room data."""
    if not room:
        return ""

    profile = _plain_dict(room.db.space_profile)
    geometry = _clean_fragment(profile.get("geometry", ""))
    scale = _clean_fragment(profile.get("scale", ""))
    focal_points = [str(item) for item in _plain_list(profile.get("focal_points", [])) if item]
    hearing = _first_sensory(room, "hearing")
    sight = _first_sensory(room, "sight")

    sentences = []
    if geometry:
        if include_name:
            sentences.append(f"{room.key} esta dispuesto como {geometry}.")
        else:
            sentences.append(f"El lugar esta dispuesto como {geometry}.")
    elif room.db.desc:
        sentences.append(_sentence(room.db.desc))

    if scale and scale.lower() not in _normalize(" ".join(sentences)):
        sentences.append(f"Es de escala {scale}.")

    if focal_points:
        sentences.append(_sentence(focal_points[0]))
    elif sight:
        sentences.append(_sentence(sight))

    if hearing:
        sentences.append(f"Se oyen {hearing.rstrip('.')}.")

    return " ".join(sentence for sentence in sentences if sentence)


def _render_move_fallback(destination):
    core = _render_room_core(destination, include_name=False)
    if core:
        return f"Entras en {destination.key}. {core}"
    return f"Llegas a {destination.key}."


def _render_observation(character, result):
    room = getattr(character, "location", None)
    core = _render_room_core(room, include_name=True)
    known = [str(item) for item in result.get("already_known", []) if item]
    if known:
        core = (core + " " + " ".join(_sentence(item) for item in known)).strip()
    return core or "No hay datos descriptivos adicionales autorizados para este lugar."


def _render_auto_success(result):
    targets = [str(item) for item in result.get("visible_targets", []) if item]
    if not targets:
        return "El objetivo es visible sin necesidad de una busqueda minuciosa."
    if len(targets) == 1:
        return f"A simple vista distingues {targets[0]}."
    return "A simple vista distingues " + ", ".join(targets[:-1]) + " y " + targets[-1] + "."


def _render_discovery(result):
    discovered = [str(item).strip() for item in result.get("discovered", []) if item]
    if not discovered:
        return "La busqueda no descubre ningun detalle nuevo."
    return " ".join(_sentence(item) for item in discovered)


# If Qwen uses one of these concepts without that concept appearing anywhere in
# the authoritative packet, its output is rejected and deterministic prose wins.
GUARDED_TERMS = [
    "a tu espalda", "a sus espaldas", "izquierda", "derecha", "delante", "detras",
    "norte", "sur", "este", "oeste",
    "sombra", "sombras", "luz", "luces", "iluminacion", "reflejo", "reflejos",
    "calido", "calida", "acogedor", "acogedora", "frio", "fria", "temperatura",
    "olor", "huele", "aroma",
]

NEGATIVE_ASSERTIONS = [
    "no hay", "no esta", "no existe", "esta vacio", "esta vacia", "no se ve", "nadie",
]


def _validate_narration(text, packet):
    output = _normalize(text)
    source = _normalize(json.dumps(_json_safe(packet), ensure_ascii=False))

    for term in GUARDED_TERMS:
        normalized_term = _normalize(term)
        if normalized_term in output and normalized_term not in source:
            return False, f"detalle no autorizado: {term}"

    for phrase in NEGATIVE_ASSERTIONS:
        normalized_phrase = _normalize(phrase)
        if normalized_phrase in output and normalized_phrase not in source:
            return False, f"afirmacion negativa no autorizada: {phrase}"

    return True, ""


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
            "temperature": 0.15,
            "num_predict": 120,
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


def _threaded_request(packet):
    return threads.deferToThread(_request_chat, packet)


def _narrate_async(character, packet, fallback_text):
    deferred = run_serialized(character, _threaded_request, packet)

    def _ok(text):
        if text:
            valid, reason = _validate_narration(text, packet)
            if valid:
                character.msg("\n" + text)
                return
            logger.log_err(f"SIZA rejected narrator output ({NARRATOR_BUILD}): {reason}; text={text[:240]}")
        character.msg("\n" + fallback_text)

    def _failed(failure):
        reason = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
        logger.log_err(f"SIZA Ollama narrator error: {reason}")
        character.msg("\n" + fallback_text)

    deferred.addCallbacks(_ok, _failed)
    return deferred


def narrate_move_async(character, source, destination, exit_obj):
    packet = build_move_packet(character, source, destination, exit_obj)
    return _narrate_async(character, packet, _render_move_fallback(destination))


def narrate_perception_async(character, result):
    """Perception prose is deterministic: the LLM never decides what a failed search means."""
    status = result.get("status")
    target = (result.get("target") or "").strip()

    if status == "OBSERVED":
        character.msg("\n" + _render_observation(character, result))
        return None

    if status == "AUTO_SUCCESS":
        character.msg("\n" + _render_auto_success(result))
        return None

    if status == "DISCOVERY":
        character.msg("\n" + _render_discovery(result))
        return None

    if status == "NO_AUTHORIZED_DISCOVERY":
        if target:
            character.msg(f"\nLa busqueda no aporta informacion nueva sobre {target}.")
        else:
            character.msg("\nLa busqueda no aporta informacion nueva.")
        return None

    if status == "NO_DISCOVERY":
        if target:
            character.msg(f"\nBuscas indicios relacionados con {target}, pero no descubres ningun detalle nuevo.")
        else:
            character.msg("\nLa busqueda no descubre ningun detalle nuevo.")
        return None

    character.msg("\nNo obtienes informacion nueva con esa accion.")
    return None
