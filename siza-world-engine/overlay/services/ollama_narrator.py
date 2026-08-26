import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

from twisted.internet import threads
from evennia.utils import logger

from services.narration_queue import run_serialized


NARRATOR_BUILD = "0.4.3-relevant-english-presentation"
OLLAMA_URL = os.getenv("SIZA_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("SIZA_OLLAMA_MODEL", "qwen3:8b")
OLLAMA_NUM_CTX = int(os.getenv("SIZA_OLLAMA_NUM_CTX", "8192"))

SYSTEM_PROMPT = """You are Siza's prose layer. You are NOT the game engine.
The WORLD ENGINE has already decided geometry, movement, state, perception, and discoveries.
Rewrite only authorized facts in concise natural English without adding new facts.
Do not narrate exits, routes, or navigation unless the player's request specifically concerns navigation.
"""


def _normalize(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _json_safe(value):
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
        }
    )


def _first_sensory(room, sense):
    sensory = _plain_dict(room.db.sensory_facts if room else {})
    values = _plain_list(sensory.get(sense, []))
    return str(values[0]) if values else ""


def _clean_fragment(text):
    return str(text or "").strip().rstrip(".")


def _sentence(text):
    text = _clean_fragment(text)
    if not text:
        return ""
    return text[0].upper() + text[1:] + "."


def _contains_basic_verb(fragment):
    words = set(_normalize(fragment).split())
    common_verbs = {
        "is", "are", "occupies", "connects", "organizes", "waits", "receives", "passes", "remains", "leads",
        "es", "son", "esta", "estan", "ocupa", "ocupan", "comunica", "comunican",
        "conecta", "conectan", "organiza", "organizan", "espera", "esperan",
        "recibe", "reciben", "pasa", "pasan", "queda", "quedan", "lleva", "llevan",
    }
    return bool(words & common_verbs)


def _render_focal(fragment):
    fragment = _clean_fragment(fragment)
    if not fragment:
        return ""
    if _contains_basic_verb(fragment):
        return _sentence(fragment)
    return f"One visible feature stands out: {fragment}."


def _render_hearing(fragment):
    fragment = _clean_fragment(fragment)
    if not fragment:
        return ""
    return f"You hear {fragment}."


def _render_room_core(room, include_name=True, include_orientation=False):
    if not room:
        return ""

    profile = _plain_dict(room.db.space_profile)
    geometry = _clean_fragment(profile.get("geometry", ""))
    scale = _clean_fragment(profile.get("scale", ""))
    orientation = _clean_fragment(profile.get("orientation", ""))
    focal_points = [str(item) for item in _plain_list(profile.get("focal_points", [])) if item]
    hearing = _first_sensory(room, "hearing")
    sight = _first_sensory(room, "sight")

    sentences = []
    if geometry:
        if include_name:
            sentences.append(f"In {room.key}, the space is arranged as {geometry}.")
        else:
            sentences.append(f"The space is arranged as {geometry}.")
    elif room.db.desc:
        sentences.append(_sentence(room.db.desc))

    if scale:
        sentences.append(f"The space feels {scale}.")

    if include_orientation and orientation:
        sentences.append(_sentence(orientation))

    if focal_points:
        sentences.append(_render_focal(focal_points[0]))
    elif sight:
        sentences.append(_render_focal(sight))

    if hearing:
        sentences.append(_render_hearing(hearing))

    return " ".join(sentence for sentence in sentences if sentence)


def _render_move_fallback(destination):
    return f"You enter {destination.key}." if destination else "You move on."


def _format_visible_names(names):
    names = [str(name) for name in names if name]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _render_observation(character, result):
    room = getattr(character, "location", None)
    visible = _visible_contents(room, exclude=character)
    known = [str(item) for item in result.get("already_known", []) if item]
    sentences = []
    if visible:
        sentences.append(f"In view: {_format_visible_names(visible)}.")
    if known:
        sentences.extend(_sentence(item) for item in known)
    return " ".join(sentence for sentence in sentences if sentence) or "Nothing else stands out at a glance."


def _render_auto_success(result):
    details = result.get("visible_target_details", []) or []
    if details:
        detail = details[0]
        name = str(detail.get("name", "the target"))
        desc = str(detail.get("desc", "")).strip()
        prefix = f"You can clearly see {name}."
        return f"{prefix} {desc}".strip()

    targets = [str(item) for item in result.get("visible_targets", []) if item]
    if not targets:
        return "The target is already visible without a closer search."
    if len(targets) == 1:
        return f"You can clearly see {targets[0]}."
    return "You can clearly see " + ", ".join(targets[:-1]) + " and " + targets[-1] + "."


def _render_discovery(result):
    discovered = [str(item).strip() for item in result.get("discovered", []) if item]
    if not discovered:
        return "The search reveals nothing new."
    return " ".join(_sentence(item) for item in discovered)


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
        raise RuntimeError(f"Could not connect to Ollama at {OLLAMA_URL}: {exc.reason}") from exc

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
            "temperature": 0.1,
            "num_predict": 100,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    data = _post_chat(payload)
    return data.get("message", {}).get("content", "").strip()


def _threaded_request(packet):
    return threads.deferToThread(_request_chat, packet)


def _narrate_async(character, packet, fallback_text):
    deferred = run_serialized(character, _threaded_request, packet)

    def _ok(text):
        character.msg("\n" + (text or fallback_text))

    def _failed(failure):
        logger.log_err(f"SIZA Ollama narrator error: {failure}")
        character.msg("\n" + fallback_text)

    deferred.addCallbacks(_ok, _failed)
    return deferred


def narrate_move_async(character, source, destination, exit_obj):
    character.msg("\n" + _render_move_fallback(destination))
    return None


def narrate_perception_async(character, result):
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
            character.msg(f"\nYour search reveals no new information about {target}.")
        else:
            character.msg("\nYour search reveals no new information.")
        return None

    if status == "NO_DISCOVERY":
        if target:
            character.msg(f"\nYou search for clues related to {target}, but find nothing new.")
        else:
            character.msg("\nThe search reveals nothing new.")
        return None

    character.msg("\nYou gain no new information from that action.")
    return None
