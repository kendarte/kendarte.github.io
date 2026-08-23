from datetime import datetime, timezone
import re
import unicodedata

from evennia import search_tag


OPEN_WORDS = {"abro", "abrir", "abre", "abrimos"}
CLOSE_WORDS = {"cierro", "cerrar", "cierra", "cerramos"}
TALK_WORDS = {
    "hablo", "hablar", "converso", "conversar", "pregunto", "preguntar",
    "saludo", "saludar", "digo", "decir",
}
REMEMBER_WORDS = {"recuerdo", "recordar", "recuerdos", "recuerdame"}


def normalize(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _tokens(text):
    return [token for token in normalize(text).split() if token]


def _plain_dict(value):
    if not value:
        return {}
    try:
        return {str(k): v for k, v in value.items()}
    except Exception:
        return {}


def _plain_list(value):
    if not value:
        return []
    try:
        return list(value)
    except Exception:
        return []


def parse_interaction_intent(raw):
    tokens = set(_tokens(raw))

    if tokens & OPEN_WORDS:
        return {"intent": "DOOR", "action": "open", "raw": raw}
    if tokens & CLOSE_WORDS:
        return {"intent": "DOOR", "action": "close", "raw": raw}
    if tokens & TALK_WORDS:
        return {"intent": "TALK", "raw": raw}
    if tokens & REMEMBER_WORDS or normalize(raw).startswith("que recuerdo"):
        return {"intent": "REMEMBER", "raw": raw}
    return None


def _object_names(obj):
    names = [obj.key]
    try:
        names.extend(obj.aliases.all())
    except Exception:
        pass
    return [str(name) for name in names if name]


def _score_name(raw, obj):
    raw_n = normalize(raw)
    raw_tokens = set(_tokens(raw))
    best = 0
    for name in _object_names(obj):
        name_n = normalize(name)
        if not name_n:
            continue
        if name_n in raw_n:
            best = max(best, 1000 + len(name_n))
            continue
        name_tokens = set(_tokens(name))
        overlap = raw_tokens & name_tokens
        if overlap:
            best = max(best, len(overlap) * 100)
    return best


def _visible_npcs(location):
    if not location:
        return []
    result = []
    for obj in location.contents:
        if getattr(obj.db, "hidden", False):
            continue
        if getattr(obj.db, "is_npc", False):
            result.append(obj)
    return result


def _find_npc(location, raw):
    candidates = _visible_npcs(location)
    if not candidates:
        return None
    scored = sorted(((_score_name(raw, npc), npc) for npc in candidates), key=lambda pair: pair[0], reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _extract_topic(raw, npc=None):
    text = normalize(raw)
    if npc:
        for name in _object_names(npc):
            text = text.replace(normalize(name), " ")
    for marker in (" acerca de ", " sobre ", " por ", " de "):
        if marker in f" {text} ":
            parts = f" {text} ".split(marker, 1)
            if len(parts) == 2:
                return " ".join(parts[1].split())
    stop = TALK_WORDS | {"con", "a", "le", "la", "el", "los", "las", "me", "que", "quiero"}
    words = [token for token in _tokens(text) if token not in stop]
    return " ".join(words)


def _fact_matches_topic(fact, topic):
    if not topic:
        return False
    topic_tokens = set(_tokens(topic))
    aliases = [fact.get("topic", "")] + list(fact.get("aliases", []) or [])
    haystack = set()
    for alias in aliases:
        haystack.update(_tokens(alias))
    return bool(topic_tokens & haystack)


def _append_memory(holder, memory):
    memories = _plain_list(holder.db.memories)
    memories.append(memory)
    holder.db.memories = memories[-100:]


def _relationship_identity(other):
    """Use stable npc_id for NPCs and explicit DBREF identity for other Characters."""
    npc_id = str(getattr(other.db, "npc_id", "") or "").strip()
    if npc_id:
        return npc_id, {
            "target_type": "NPC",
            "target_npc_id": npc_id,
            "target_dbref": int(other.id),
            "target_name": other.key,
        }
    return f"DBREF:{int(other.id)}", {
        "target_type": "CHARACTER",
        "target_dbref": int(other.id),
        "target_name": other.key,
    }


def _update_relationship(holder, other, timestamp):
    relationships = _plain_dict(holder.db.relationships)
    key, identity = _relationship_identity(other)
    current = _plain_dict(relationships.get(key, {}))
    current.update(identity)
    current["name"] = other.key
    current["familiarity"] = int(current.get("familiarity", 0) or 0) + 1
    current["last_interaction"] = timestamp
    relationships[key] = current
    holder.db.relationships = relationships


def _record_conversation(
    character,
    npc,
    topic,
    outcome,
    fact_id=None,
    fact_text=None,
):
    """Store semantic conversation events, not a verbatim transcript."""
    timestamp = datetime.now(timezone.utc).isoformat()
    room = getattr(character, "location", None)
    base = {
        "type": "conversation",
        "schema": 2,
        "timestamp": timestamp,
        "room_id": room.db.room_id if room else None,
        "room_name": room.key if room else None,
        "topic": topic or None,
        "outcome": outcome,
        "fact_id": fact_id,
        "fact_text": fact_text,
    }
    player_memory = dict(base)
    player_memory.update({"with_id": npc.id, "with_name": npc.key})
    npc_memory = dict(base)
    npc_memory.update({"with_id": character.id, "with_name": character.key})
    _append_memory(character, player_memory)
    _append_memory(npc, npc_memory)
    _update_relationship(character, npc, timestamp)
    _update_relationship(npc, character, timestamp)


def resolve_talk(character, intent):
    location = getattr(character, "location", None)
    npc = _find_npc(location, intent.get("raw", ""))
    if not npc:
        return "No identificas a ningún interlocutor visible para esa acción."

    raw = intent.get("raw", "")
    topic = _extract_topic(raw, npc=npc)
    facts = []
    for raw_fact in _plain_list(npc.db.knowledge_facts):
        try:
            fact = {str(k): v for k, v in raw_fact.items()}
        except Exception:
            continue
        if _fact_matches_topic(fact, topic):
            facts.append(fact)

    if not topic:
        greeting = str(npc.db.dialogue_greeting or "").strip()
        text = greeting or f"{npc.key} te presta atención."
        _record_conversation(character, npc, None, outcome="greeting")
        return text

    knowledge = _plain_dict(npc.db.knowledge)
    for fact in facts:
        knowledge_key = str(fact.get("knowledge_key", ""))
        required = int(fact.get("required_level", 1) or 1)
        try:
            level = int(knowledge.get(knowledge_key, 0) or 0)
        except (TypeError, ValueError):
            level = 0
        if level < required:
            continue
        response = str(fact.get("response", "")).strip()
        if not response:
            response = str(fact.get("fact", "")).strip()
        if response:
            _record_conversation(
                character,
                npc,
                topic,
                outcome="knowledge_shared",
                fact_id=str(fact.get("id", "")) or None,
                fact_text=response,
            )
            return response

    text = f"{npc.key} no aporta información concreta sobre {topic}."
    _record_conversation(character, npc, topic, outcome="no_information")
    return text


def _door_candidates(location):
    if not location:
        return []
    return [exit_obj for exit_obj in location.exits if exit_obj.db.door_group_id]


def _find_door(location, raw):
    candidates = _door_candidates(location)
    if not candidates:
        return None
    raw_tokens = set(_tokens(raw))
    scored = []
    for exit_obj in candidates:
        names = _object_names(exit_obj)
        if exit_obj.destination:
            names.append(exit_obj.destination.key)
        if exit_obj.db.door_name:
            names.append(str(exit_obj.db.door_name))
        tokens = set()
        for name in names:
            tokens.update(_tokens(name))
        scored.append((len(raw_tokens & tokens), exit_obj))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_door(character, intent):
    location = getattr(character, "location", None)
    exit_obj = _find_door(location, intent.get("raw", ""))
    if not exit_obj:
        return "No identificas una puerta manipulable asociada a esa acción."

    group_id = str(exit_obj.db.door_group_id)
    linked = list(search_tag(group_id, category="siza_door"))
    if not linked:
        linked = [exit_obj]

    action = intent.get("action")
    current = str(exit_obj.db.door_state or "open")
    door_name = str(exit_obj.db.door_name or "la puerta")

    if action == "close":
        if current == "closed":
            return f"{door_name.capitalize()} ya está cerrada."
        for item in linked:
            item.db.door_state = "closed"
        return f"Cierras {door_name}."

    if action == "open":
        if exit_obj.db.is_locked or current == "locked":
            return f"{door_name.capitalize()} está bloqueada."
        if current == "open":
            return f"{door_name.capitalize()} ya está abierta."
        for item in linked:
            item.db.door_state = "open"
        return f"Abres {door_name}."

    return "La acción sobre la puerta no se pudo resolver."


def _render_memory(mem):
    """Render both schema-v2 semantic memories and old schema-v1 transcript memories."""
    who = str(mem.get("with_name") or "alguien")
    schema = int(mem.get("schema", 1) or 1)

    if schema >= 2:
        outcome = str(mem.get("outcome") or "")
        topic = str(mem.get("topic") or "").strip()
        room_name = str(mem.get("room_name") or "").strip()
        fact_text = str(mem.get("fact_text") or "").strip()
        place = f" en {room_name}" if room_name else ""

        if outcome == "greeting":
            return f"Hablaste con {who}{place}."
        if outcome == "knowledge_shared":
            if fact_text:
                return f"{who} te dio información sobre {topic}: {fact_text}"
            return f"{who} te dio información sobre {topic}{place}."
        if outcome == "no_information":
            return f"Preguntaste a {who} por {topic}, pero no obtuviste información concreta."
        return f"Tuviste una interacción con {who}{place}."

    summary = str(mem.get("summary") or "una conversación")
    return f"Registro anterior con {who}: {summary}"


def resolve_remember(character, intent):
    raw = normalize(intent.get("raw", ""))
    target_words = [
        token for token in _tokens(raw)
        if token not in REMEMBER_WORDS | {"a", "de", "que", "sobre", "mis", "mi", "los", "las"}
    ]
    target_tokens = set(target_words)
    memories = _plain_list(character.db.memories)
    matches = []
    for memory in reversed(memories):
        try:
            mem = {str(k): v for k, v in memory.items()}
        except Exception:
            continue
        haystack = " ".join(
            str(mem.get(key, ""))
            for key in ("with_name", "topic", "fact_text", "summary", "fact_id", "outcome")
        )
        if target_tokens and not (target_tokens & set(_tokens(haystack))):
            continue
        matches.append(mem)
        if len(matches) >= 5:
            break

    if not matches:
        return "No tienes ningún recuerdo registrado que coincida con esa consulta."

    return "\n".join(_render_memory(mem) for mem in matches)


def resolve_interaction(character, intent):
    kind = intent.get("intent")
    if kind == "DOOR":
        return resolve_door(character, intent)
    if kind == "TALK":
        return resolve_talk(character, intent)
    if kind == "REMEMBER":
        return resolve_remember(character, intent)
    return None
