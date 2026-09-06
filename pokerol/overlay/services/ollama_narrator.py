import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

from twisted.internet import threads
from evennia.utils import logger

from services.narration_queue import run_serialized
from services.player_language_contract import (
    get_actor_turn_language,
    language_instruction,
    localize,
    normalize_player_language,
)


NARRATOR_BUILD = "0.4.4-bilingual-turn-presentation"
OLLAMA_URL = os.getenv("SIZA_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("SIZA_OLLAMA_MODEL", "qwen3:8b")
OLLAMA_NUM_CTX = int(os.getenv("SIZA_OLLAMA_NUM_CTX", "8192"))


def _system_prompt(language):
    language = normalize_player_language(language)
    return (
        "You are Siza's prose layer. You are NOT the game engine.\n"
        "The WORLD ENGINE has already decided geometry, movement, state, perception, and discoveries.\n"
        "Rewrite only authorized facts without adding new facts. Authorized source text may be Spanish or English; preserve its meaning exactly.\n"
        "Do not narrate exits, routes, or navigation unless the player's request specifically concerns navigation.\n"
        + language_instruction(language)
    )


SYSTEM_PROMPT = _system_prompt("es")


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


def _format_visible_names(names, language="es"):
    names = [str(name) for name in names if name]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    conjunction = " and " if normalize_player_language(language) == "en" else " y "
    return ", ".join(names[:-1]) + conjunction + names[-1]


def _render_move_fallback(destination, language="es"):
    language = normalize_player_language(language)
    if destination:
        return f"You enter {destination.key}." if language == "en" else f"Entras en {destination.key}."
    return "You move on." if language == "en" else "Sigues adelante."


def _safe_perception_packet(character, result, language):
    status = str((result or {}).get("status") or "")
    room = getattr(character, "location", None)
    packet = {
        "mode": "PERCEPTION",
        "status": status,
        "player_language": normalize_player_language(language),
        "target": str((result or {}).get("target") or "").strip(),
    }
    if status == "OBSERVED":
        packet["visible_contents"] = _visible_contents(room, exclude=character)
        packet["already_known"] = [str(item) for item in (result.get("already_known", []) or []) if item]
    elif status == "AUTO_SUCCESS":
        packet["visible_targets"] = [str(item) for item in (result.get("visible_targets", []) or []) if item]
        packet["visible_target_details"] = [
            {
                "name": str((item or {}).get("name") or ""),
                "desc": str((item or {}).get("desc") or ""),
            }
            for item in (result.get("visible_target_details", []) or [])
            if isinstance(item, dict)
        ]
    elif status == "DISCOVERY":
        packet["discovered"] = [str(item).strip() for item in (result.get("discovered", []) or []) if item]
    return packet


def _perception_fallback(character, result, language):
    language = normalize_player_language(language)
    status = str((result or {}).get("status") or "")
    if status == "OBSERVED":
        visible = _visible_contents(getattr(character, "location", None), exclude=character)
        if visible:
            prefix = "In view" if language == "en" else "A la vista"
            return f"{prefix}: {_format_visible_names(visible, language)}."
        return localize("nothing_stands_out", language)
    if status == "AUTO_SUCCESS":
        targets = [str(item) for item in (result.get("visible_targets", []) or []) if item]
        if targets:
            names = _format_visible_names(targets, language)
            return f"You can clearly see {names}." if language == "en" else f"Puedes ver claramente {names}."
        return "The target is already visible." if language == "en" else "El objetivo ya está a la vista."
    if status == "DISCOVERY":
        discovered = [item for item in (result.get("discovered", []) or []) if item]
        if discovered:
            return "You discover new information." if language == "en" else "Descubres información nueva."
        return localize("search_nothing_new", language)
    return localize("no_new_information", language)


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
    safe_packet = dict(packet or {})
    language = normalize_player_language(safe_packet.get("player_language"))
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt(language)},
            {"role": "user", "content": json.dumps(_json_safe(safe_packet), ensure_ascii=False, indent=2)},
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
    language = get_actor_turn_language(character)
    character.msg("\n" + _render_move_fallback(destination, language))
    return None


def narrate_perception_async(character, result):
    language = get_actor_turn_language(character)
    status = str((result or {}).get("status") or "")
    target = str((result or {}).get("target") or "").strip()

    if status in {"OBSERVED", "AUTO_SUCCESS", "DISCOVERY"}:
        packet = _safe_perception_packet(character, result, language)
        return _narrate_async(character, packet, _perception_fallback(character, result, language))

    if status == "NO_AUTHORIZED_DISCOVERY":
        if target:
            text = (
                f"Your search reveals no new information about {target}."
                if language == "en"
                else f"Tu búsqueda no revela información nueva sobre {target}."
            )
        else:
            text = "Your search reveals no new information." if language == "en" else "Tu búsqueda no revela información nueva."
        character.msg("\n" + text)
        return None

    if status == "NO_DISCOVERY":
        if target:
            text = (
                f"You search for clues related to {target}, but find nothing new."
                if language == "en"
                else f"Buscas pistas relacionadas con {target}, pero no encuentras nada nuevo."
            )
        else:
            text = localize("search_nothing_new", language)
        character.msg("\n" + text)
        return None

    character.msg("\n" + localize("no_new_information", language))
    return None
