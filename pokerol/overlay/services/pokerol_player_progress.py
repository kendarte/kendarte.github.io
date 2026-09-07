from datetime import datetime, timezone
from uuid import uuid4

from services.action_resolution_engine import ADVENTURE_STATS, adventure_stats
from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts, knowledge_levels
from services.pokemon_party_engine import party_state


PLAYER_PROGRESS_BUILD = "0.1.0-player-sheet-memory-core"
MEMORY_LIMIT = 200
EVENT_LIMIT = 200
BADGE_LIMIT = 32


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _text(value, limit=None):
    value = str(value or "").strip()
    return value[:limit] if limit else value


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalize_memory(raw):
    row = _dict(raw)
    return {
        "id": _text(row.get("id"), 96) or f"MEM-{uuid4().hex[:12].upper()}",
        "title": _text(row.get("title") or row.get("name"), 160) or "Recuerdo",
        "text": _text(row.get("text") or row.get("description"), 5000),
        "category": _text(row.get("category") or row.get("type"), 64) or "EVENTO",
        "event_id": _text(row.get("event_id"), 96),
        "room_id": _text(row.get("room_id"), 96),
        "image": _text(row.get("image"), 1000),
        "created_at": _text(row.get("created_at"), 64) or _now(),
        "importance": max(0, min(10, int(row.get("importance", 5) or 5))),
    }


def _normalize_event(raw):
    row = _dict(raw)
    return {
        "id": _text(row.get("id"), 96) or f"EVLOG-{uuid4().hex[:12].upper()}",
        "event_id": _text(row.get("event_id"), 96),
        "title": _text(row.get("title") or row.get("name"), 160) or "Evento",
        "result": _text(row.get("result"), 96),
        "room_id": _text(row.get("room_id"), 96),
        "created_at": _text(row.get("created_at"), 64) or _now(),
        "data": _dict(row.get("data")),
    }


def _normalize_badge(raw):
    row = _dict(raw)
    return {
        "id": _text(row.get("id"), 96) or f"BADGE-{uuid4().hex[:12].upper()}",
        "name": _text(row.get("name") or row.get("title"), 120) or "Medalla",
        "region": _text(row.get("region"), 96) or "Kanto",
        "image": _text(row.get("image"), 1000),
        "obtained_at": _text(row.get("obtained_at"), 64),
        "description": _text(row.get("description"), 1000),
    }


def memories(actor):
    if not actor:
        return []
    return [_normalize_memory(row) for row in _list(getattr(actor.db, "pokerol_memories", [])) if _dict(row)]


def event_history(actor):
    if not actor:
        return []
    return [_normalize_event(row) for row in _list(getattr(actor.db, "pokerol_event_history", [])) if _dict(row)]


def badges(actor):
    if not actor:
        return []
    return [_normalize_badge(row) for row in _list(getattr(actor.db, "pokerol_badges", [])) if _dict(row)]


def remember(actor, *, title, text="", category="EVENTO", event_id="", room_id="", image="", importance=5, memory_id=""):
    if not actor:
        return None
    row = _normalize_memory({
        "id": memory_id,
        "title": title,
        "text": text,
        "category": category,
        "event_id": event_id,
        "room_id": room_id,
        "image": image,
        "importance": importance,
        "created_at": _now(),
    })
    rows = memories(actor)
    rows = [item for item in rows if item.get("id") != row["id"]]
    rows.append(row)
    actor.db.pokerol_memories = rows[-MEMORY_LIMIT:]
    return row


def record_event(actor, *, event_id, title="", result="", room_id="", data=None, create_memory=False, memory_text="", memory_image=""):
    if not actor:
        return None
    row = _normalize_event({
        "event_id": event_id,
        "title": title or event_id,
        "result": result,
        "room_id": room_id,
        "data": _dict(data),
        "created_at": _now(),
    })
    rows = event_history(actor)
    rows.append(row)
    actor.db.pokerol_event_history = rows[-EVENT_LIMIT:]
    if create_memory:
        remember(
            actor,
            title=title or event_id,
            text=memory_text or result,
            category="EVENTO",
            event_id=event_id,
            room_id=room_id,
            image=memory_image,
        )
    return row


def award_badge(actor, *, badge_id, name, region="Kanto", image="", description=""):
    if not actor:
        return None
    row = _normalize_badge({
        "id": badge_id,
        "name": name,
        "region": region,
        "image": image,
        "description": description,
        "obtained_at": _now(),
    })
    rows = badges(actor)
    if any(item.get("id") == row["id"] for item in rows):
        return next(item for item in rows if item.get("id") == row["id"])
    rows.append(row)
    actor.db.pokerol_badges = rows[-BADGE_LIMIT:]
    return row


def player_sheet_state(actor):
    if not actor:
        return {"status": "NO_PLAYER", "build": PLAYER_PROGRESS_BUILD}

    location = getattr(actor, "location", None)
    stats = adventure_stats(actor)
    levels = knowledge_levels(actor)
    known_facts = []
    for fact in knowledge_facts(actor):
        state = fact_knowledge_state(actor, fact)
        if not state.get("known"):
            continue
        known_facts.append({
            "id": _text(fact.get("id"), 96),
            "topic": _text(fact.get("topic") or fact.get("title") or fact.get("name"), 160) or _text(fact.get("id"), 96),
            "knowledge_key": state.get("knowledge_key"),
            "level": state.get("level"),
            "required_level": state.get("required_level"),
            "canon_status": _text(fact.get("canon_status") or fact.get("status"), 64) or "prototype",
        })

    party = party_state(actor)
    party_rows = []
    for row in list(party.get("party") or []):
        sprite = _dict(row.get("sprite"))
        party_rows.append({
            "species_id": _text(row.get("species_id"), 96),
            "name": _text(row.get("nickname") or row.get("species_name"), 120) or "Pokémon",
            "level": int(row.get("level", 1) or 1),
            "active": bool(row.get("active")),
            "icon": _text(sprite.get("icon") or sprite.get("front"), 1000),
        })

    return {
        "status": "PLAYER_SHEET",
        "build": PLAYER_PROGRESS_BUILD,
        "name": str(actor.key),
        "dbref": int(actor.id),
        "player_id": _text(getattr(actor.db, "player_id", ""), 96) or f"PLAYER:DBREF:{int(actor.id)}",
        "full_body_image": _text(getattr(actor.db, "profile_fullbody_image", ""), 1000),
        "scene_sprite": _text(getattr(actor.db, "scene_sprite", ""), 1000),
        "room": {
            "name": str(getattr(location, "key", "") or ""),
            "room_id": _text(getattr(getattr(location, "db", None), "room_id", ""), 96) if location else "",
        },
        "stats": {key: stats.get(key) for key in ADVENTURE_STATS},
        "knowledge_levels": levels,
        "knowledge_facts": known_facts,
        "badges": badges(actor),
        "memories": list(reversed(memories(actor))),
        "events": list(reversed(event_history(actor))),
        "party": party_rows,
        "storage_count": int(party.get("storage_count", 0) or 0),
    }
