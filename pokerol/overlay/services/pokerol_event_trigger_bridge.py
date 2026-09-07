"""Safe trigger bridge from authoritative world actions into generic ROOM events."""

from services.pokerol_event_editor_service import list_room_events
from services.pokerol_event_progress import event_progress
from services.pokerol_room_event_runtime import start_room_event


EVENT_TRIGGER_BRIDGE_BUILD = "0.1.0-authoritative-world-trigger-bridge"


def _text(value):
    return str(value or "").strip()


def _aliases(obj):
    values = []
    if not obj:
        return values
    for attr in ("npc_id", "object_id"):
        value = _text(getattr(obj.db, attr, ""))
        if value:
            values.append(value)
    values.append(_text(getattr(obj, "key", "")))
    if getattr(obj, "id", None) is not None:
        values.append("DBREF:{}".format(int(obj.id)))
    try:
        values.extend(_text(value) for value in obj.aliases.all())
    except Exception:
        pass
    return [value for value in values if value]


def _target_matches(event, obj):
    wanted = _text((event or {}).get("trigger_target"))
    if not wanted:
        return True
    normalized = wanted.casefold()
    return any(value.casefold() == normalized for value in _aliases(obj))


def trigger_object_event(actor, obj, trigger, *, token=""):
    """Trigger only inactive matching ROOM_EVENT definitions for one concrete object/NPC."""
    room = getattr(actor, "location", None) if actor else None
    if not room or not obj or getattr(obj, "location", None) is not room:
        return []
    trigger_name = _text(trigger).upper()
    rows = []
    for event in list_room_events(room):
        if _text(event.get("source")).upper() != "ROOM":
            continue
        if _text(event.get("handler")).upper() not in {"ROOM_EVENT", "GENERIC_ROOM_EVENT"}:
            continue
        if not bool(event.get("enabled", True)) or _text(event.get("trigger")).upper() != trigger_name:
            continue
        if not _target_matches(event, obj):
            continue
        progress = event_progress(actor, event.get("id"))
        if progress.get("status") == "ACTIVE":
            rows.append({"accepted": True, "status": "EVENT_ALREADY_ACTIVE", "event_id": event.get("id"), "build": EVENT_TRIGGER_BRIDGE_BUILD})
            continue
        if progress.get("status") == "COMPLETED" and _text(event.get("repeat_mode")).upper() in {"ONCE", "PER_CHARACTER"}:
            continue
        target = _text(getattr(obj.db, "npc_id", "")) or _text(getattr(obj.db, "object_id", "")) or _text(getattr(obj, "key", ""))
        result = start_room_event(
            actor,
            event,
            trigger=trigger_name,
            trigger_target=target,
            trigger_token=token or "{}:{}".format(trigger_name, int(obj.id)),
        )
        rows.append(result)
    return rows


def trigger_npc_interaction(actor, npc, *, token=""):
    return trigger_object_event(actor, npc, "INTERACT_NPC", token=token)


def trigger_object_interaction(actor, obj, *, token=""):
    return trigger_object_event(actor, obj, "INTERACT_OBJECT", token=token)
