import re
import unicodedata

from services.action_resolution_engine import stat_value
from services.dm_campaign_registry import observe_active_campaign_evidence
from services.object_action_engine import authored_object_actions, begin_object_action


OBJECT_ACTION_INPUT_BUILD = "0.56.0-narrative-object-action-input"
INPUT_STOPWORDS = {
    "a", "al", "de", "del", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "con", "en", "por", "para", "sobre", "quiero", "quisiera", "puedo", "me",
}
NARRATIVE_TEXT_KEYS = (
    "narrative",
    "narrative_text",
    "completion_text",
    "completed_text",
    "result_text",
    "success_text",
    "response_text",
    "observation",
    "visible_result",
    "after_text",
    "text",
)
DESCRIPTION_KEYS = (
    "visible_description",
    "description",
    "desc",
    "summary",
    "look_text",
)


def normalize(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _tokens(text):
    return [
        token
        for token in normalize(text).split()
        if token and token not in INPUT_STOPWORDS
    ]


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _clean_text(value):
    return " ".join(str(value or "").replace("\r", "\n").split()).strip()


def _first_text(container, keys=NARRATIVE_TEXT_KEYS):
    if not isinstance(container, dict):
        return ""
    for key in keys:
        value = container.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_text(value)
    for key in ("result", "results", "completion", "success", "on_complete", "outcome", "metadata"):
        nested = container.get(key)
        if isinstance(nested, dict):
            found = _first_text(nested, keys)
            if found:
                return found
    return ""


def _db_text(obj, keys=DESCRIPTION_KEYS):
    if not obj:
        return ""
    db = getattr(obj, "db", None)
    for key in keys:
        try:
            value = getattr(db, key, None)
        except Exception:
            value = None
        if isinstance(value, str) and value.strip():
            return _clean_text(value)
    try:
        value = getattr(obj, "desc", None)
    except Exception:
        value = None
    if isinstance(value, str) and value.strip():
        return _clean_text(value)
    return ""


def _object_names(obj):
    names = [obj.key]
    try:
        names.extend(obj.aliases.all())
    except Exception:
        pass
    object_id = str(getattr(obj.db, "object_id", "") or "").strip()
    if object_id:
        names.append(object_id)
    return [str(name) for name in names if str(name or "").strip()]


def _action_phrases(action):
    phrases = []
    for value in _plain_list((action or {}).get("input_phrases")):
        text = str(value or "").strip()
        if text:
            phrases.append(text)
    name = str((action or {}).get("name") or "").strip()
    if name:
        phrases.append(name)
    for value in _plain_list((action or {}).get("aliases")):
        text = str(value or "").strip()
        if text:
            phrases.append(text)
    return phrases


def _phrase_score(raw, phrases):
    raw_n = normalize(raw)
    raw_tokens = set(_tokens(raw))
    best = 0
    for phrase in phrases:
        phrase_n = normalize(phrase)
        if not phrase_n:
            continue
        phrase_tokens = set(_tokens(phrase))
        if raw_n == phrase_n:
            best = max(best, 1200 + len(phrase_n))
            continue
        if phrase_n in raw_n:
            best = max(best, 900 + len(phrase_n))
            continue
        if phrase_tokens and phrase_tokens.issubset(raw_tokens):
            best = max(best, 500 + len(phrase_tokens) * 20)
            continue
        overlap = raw_tokens & phrase_tokens
        if overlap:
            best = max(best, len(overlap) * 50)
    return best


def _campaign_tags(action):
    metadata = (action or {}).get("metadata") or {}
    values = metadata.get("campaign_tags") or (action or {}).get("campaign_tags") or []
    return [str(value) for value in _plain_list(values) if str(value or "").strip()]


def _observe_completed_campaign_action(actor, matched, result):
    action = (matched or {}).get("action") or {}
    tags = _campaign_tags(action)
    if not tags:
        return None
    return observe_active_campaign_evidence(
        actor,
        {
            "authority": "WORLD_ENGINE",
            "source": "OBJECT_ACTION_INPUT",
            "action_types": ["OBJECT_ACTION_EXECUTED"],
            "campaign_tags": tags,
            "object_action_id": result.get("object_action_id") or matched.get("object_action_id"),
            "object_id": result.get("object_id") or matched.get("object_id"),
            "object_dbref": result.get("object_dbref") or matched.get("object_dbref"),
            "site_room_id": result.get("site_room_id"),
            "site_dbref": result.get("site_dbref"),
            "outcome": result.get("outcome"),
            "result": {
                "status": result.get("status"),
                "attempt_id": result.get("attempt_id"),
                "object_action_id": result.get("object_action_id") or matched.get("object_action_id"),
            },
        },
    )


def match_object_action_input(actor, raw):
    """Match natural-language input only when both one local object and one authored action are identifiable."""
    location = getattr(actor, "location", None) if actor else None
    if not actor or not location:
        return {"matched": False, "status": "NO_LOCATION", "build": OBJECT_ACTION_INPUT_BUILD}

    candidates = []
    for obj in list(getattr(location, "contents", []) or []):
        if obj is actor:
            continue
        actions = authored_object_actions(obj)
        if not actions:
            continue
        object_score = _phrase_score(raw, _object_names(obj))
        if object_score <= 0:
            continue
        for action in actions:
            if not bool(action.get("enabled", True)):
                continue
            action_score = _phrase_score(raw, _action_phrases(action))
            if action_score <= 0:
                continue
            candidates.append(
                {
                    "score": object_score + action_score,
                    "object": obj,
                    "object_id": str(getattr(obj.db, "object_id", "") or ""),
                    "object_dbref": int(obj.id),
                    "object_name": obj.key,
                    "action": action,
                    "object_action_id": action.get("id"),
                    "object_action_name": action.get("name"),
                }
            )

    if not candidates:
        return {"matched": False, "status": "NO_MATCH", "build": OBJECT_ACTION_INPUT_BUILD}

    candidates.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
    top_score = int(candidates[0].get("score") or 0)
    winners = [row for row in candidates if int(row.get("score") or 0) == top_score]
    identities = {
        (int(row.get("object_dbref") or 0), str(row.get("object_action_id") or ""))
        for row in winners
    }
    if len(identities) > 1:
        return {
            "matched": True,
            "status": "AMBIGUOUS_OBJECT_ACTION",
            "build": OBJECT_ACTION_INPUT_BUILD,
            "options": [
                {
                    "object_name": row.get("object_name"),
                    "object_dbref": row.get("object_dbref"),
                    "object_action_id": row.get("object_action_id"),
                    "object_action_name": row.get("object_action_name"),
                }
                for row in winners
            ],
        }

    winner = winners[0]
    return {
        "matched": True,
        "status": "MATCHED",
        "build": OBJECT_ACTION_INPUT_BUILD,
        **winner,
    }


def route_object_action_input(actor, raw, attempt_id=None):
    """Route one real player/NPC text input into the existing authored object-action pipeline."""
    matched = match_object_action_input(actor, raw)
    if not bool(matched.get("matched")) or matched.get("status") != "MATCHED":
        return matched

    obj = matched.get("object")
    action_id = matched.get("object_action_id")
    result = begin_object_action(actor, obj, action_id, attempt_id=attempt_id)
    if str(result.get("status") or "") == "COMPLETED":
        observation = _observe_completed_campaign_action(actor, matched, result)
        if observation is not None:
            result = {**dict(result), "campaign_observation": observation}
    return {
        **matched,
        "status": result.get("status"),
        "action_result": result,
        "attempt_id": result.get("attempt_id"),
        "resolution_id": result.get("resolution_id"),
        "outcome": result.get("outcome"),
    }


def _human_requirement_message(blockers, object_name):
    kinds = {str(row.get("kind") or "").strip().upper() for row in blockers}
    if kinds and kinds <= {"OBJECT_STATE"}:
        return f"Esa acción ya no está disponible en el estado actual de {object_name}."
    if "OBJECT_NOT_VISIBLE" in kinds:
        return f"No puedes interactuar con {object_name} en su estado actual."
    if "OBJECT_NOT_LOCAL" in kinds:
        return f"{object_name} no está en tu ubicación actual."
    if "SKILL" in kinds:
        return "No tienes la habilidad necesaria para realizar esa acción."
    if "KNOWLEDGE" in kinds:
        return "No tienes el conocimiento necesario para realizar esa acción."
    if kinds & {"WORLD_STATE", "STATE"}:
        return "El estado actual del lugar no permite realizar esa acción."
    return "No cumples los requisitos necesarios para realizar esa acción."


def _visible_name(obj):
    return _clean_text(getattr(obj, "key", ""))


def _room_snapshot_text(site, focus_obj=None):
    if not site:
        return ""

    title = _visible_name(site) or "Ubicación actual"
    desc = _db_text(site)
    lines = [title]
    if desc:
        lines.append(desc)

    objects = []
    people = []
    for obj in list(getattr(site, "contents", []) or []):
        if obj is focus_obj:
            continue
        if getattr(obj, "destination", None):
            continue
        name = _visible_name(obj)
        if not name:
            continue
        if bool(getattr(getattr(obj, "db", None), "is_npc", False)):
            people.append(name)
        else:
            objects.append(name)

    exits = []
    for exit_obj in list(getattr(site, "exits", []) or []):
        name = _visible_name(exit_obj)
        if name:
            exits.append(name)

    if objects:
        lines.append("Ves: " + ", ".join(objects[:10]) + ".")
    if people:
        lines.append("Personas presentes: " + ", ".join(people[:10]) + ".")
    if exits:
        lines.append("Salidas: " + ", ".join(exits[:10]) + ".")
    return "\n".join(line for line in lines if str(line or "").strip())


def _state_after_text(obj):
    state = _plain_dict(getattr(getattr(obj, "db", None), "state", {})) if obj else {}
    truthy = [
        str(key).replace("_", " ")
        for key, value in state.items()
        if isinstance(value, bool) and value is True
    ]
    if not truthy:
        return ""
    return "Estado visible: " + ", ".join(truthy[:4]) + "."


def _fallback_action_sentence(action_name, object_name):
    action_n = normalize(action_name)
    obj = object_name or "el objeto"
    if action_n.startswith("examinar") or action_n.startswith("observar"):
        return f"Examinas {obj} con cuidado. Te acercas lo suficiente para distinguir uso, desgaste y detalles que antes sólo eran parte del ruido del lugar."
    if action_n.startswith("revisar"):
        return f"Revisas {obj}. Apartas lo superficial, sigues marcas de uso reciente y confirmas qué queda realmente disponible."
    if action_n.startswith("abrir"):
        return f"Abres {obj}. El mecanismo cede y el lugar revela una capa más de información útil."
    if action_n.startswith("activar") or action_n.startswith("usar"):
        return f"Usas {obj}. La acción altera el estado inmediato del lugar y deja una consecuencia perceptible."
    return f"Realizas {action_name} sobre {obj}. La acción queda resuelta en el mundo y cambia lo que tu personaje puede percibir desde aquí."


def _render_completed_action(packet, action_name, object_name):
    action = (packet or {}).get("action") or {}
    result = (packet or {}).get("action_result") or {}
    obj = (packet or {}).get("object")
    site = getattr(obj, "location", None) if obj else None

    authored = _first_text(action) or _first_text(result)
    if not authored:
        authored = _fallback_action_sentence(action_name, object_name)

    object_desc = _db_text(obj)
    state_text = _state_after_text(obj)
    room_text = _room_snapshot_text(site, focus_obj=None)

    blocks = []
    if room_text:
        blocks.append(room_text)
    blocks.append(authored)
    if object_desc:
        blocks.append(f"{object_name}: {object_desc}")
    if state_text:
        blocks.append(state_text)
    return "\n\n".join(block for block in blocks if str(block or "").strip())


def render_object_action_input_result(packet):
    """Human-facing deterministic feedback for one routed object action."""
    status = str((packet or {}).get("status") or "")
    if status == "AMBIGUOUS_OBJECT_ACTION":
        options = packet.get("options") or []
        labels = [
            f"{row.get('object_action_name')} -> {row.get('object_name')}"
            for row in options
        ]
        return "La interacción es ambigua. Opciones: " + ", ".join(labels)

    result = (packet or {}).get("action_result") or {}
    object_name = (packet or {}).get("object_name") or result.get("object_name") or "objeto"
    action_name = (packet or {}).get("object_action_name") or result.get("object_action_name") or "acción"

    if status == "OBJECT_NOT_VISIBLE":
        return f"No puedes interactuar con {object_name} en su estado actual."
    if status == "OBJECT_NOT_LOCAL":
        return f"{object_name} no está en tu ubicación actual."
    if status == "OBJECT_ACTION_REQUIREMENTS_UNMET":
        blockers = result.get("blockers") or []
        return _human_requirement_message(blockers, object_name)
    if status == "PENDING_RESOLUTION":
        mode = str(result.get("resolution_mode") or "").upper()
        if mode == "CONFRONT":
            action = (packet or {}).get("action") or {}
            check = action.get("check") or {}
            target_stat = check.get("target_stat")
            target_obj = (packet or {}).get("object")
            target_value = stat_value(target_obj, target_stat) if target_obj and target_stat else None
            return (
                f"Intentas {action_name} sobre {object_name}. La situación exige una confrontación: "
                f"{result.get('actor_stat')} {result.get('actor_stat_value')} contra {target_stat} {target_value}. "
                "Escribe 'tirar' para resolver."
            )
        if mode == "SYNCHRONIZE":
            action = (packet or {}).get("action") or {}
            check = action.get("check") or {}
            metadata = check.get("metadata") or {}
            parity = str(metadata.get("parity") or "").upper()
            parity_text = "PAR" if parity in {"EVEN", "PAR"} else "IMPAR"
            return (
                f"Intentas {action_name} sobre {object_name}. La acción requiere sincronía "
                f"{parity_text}. Escribe 'tirar' para resolver."
            )
        return (
            f"Intentas {action_name} sobre {object_name}. La acción requiere una tirada de "
            f"{result.get('actor_stat')} contra dificultad {result.get('difficulty')}. "
            "Escribe 'tirar' para resolver."
        )
    if status == "COMPLETED":
        return _render_completed_action(packet, action_name, object_name)
    if status == "BLOCKED_CHECK":
        return f"No se pudo preparar la resolución de '{action_name}': {result.get('resolution_status')}"
    return f"La acción '{action_name}' no pudo resolverse ahora ({status or 'UNKNOWN'})."