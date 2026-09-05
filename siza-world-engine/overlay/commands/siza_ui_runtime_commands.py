from evennia import Command

from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_resolution_engine import adventure_stats
from services.direct_d6_resolution_engine import pending_object_actions
from services.exit_state_gate_engine import inspect_exit_state
from services.object_action_engine import find_object_action
from services.object_visibility_engine import object_visible_in_world_state


SIZA_UI_RUNTIME_BUILD = "0.2.0-map-editor-room-state"
PLACEHOLDER_DESCRIPTIONS = {
    "",
    "the current location will be described here.",
    "the current location will be described here",
    "no hay descripcion escrita para este lugar.",
    "no hay descripción escrita para este lugar.",
    "sin descripcion disponible.",
    "sin descripción disponible.",
}
ROOM_TEXT_ATTRS = (
    "desc",
    "description",
    "long_description",
    "visible_description",
    "look_text",
    "arrival_summary",
    "spatial_answer",
    "current_activity",
)
EDITOR_ROOM_ATTRS = (
    "scene_manifest",
    "sensory_facts",
    "perception_facts",
    "space_profile",
    "state_presentations",
    "conditions",
    "world_state",
)
TEXT_KEYS = (
    "text",
    "description",
    "desc",
    "summary",
    "visible_description",
    "arrival_summary",
    "spatial_answer",
    "current_activity",
    "time_context",
    "observation",
    "narrative",
    "value",
    "label",
)


def _clean(value):
    return str(value or "").strip()


def _clean_inline(value):
    return " ".join(str(value or "").replace("\r", "\n").split()).strip()


def _is_placeholder(value):
    return _clean_inline(value).lower() in PLACEHOLDER_DESCRIPTIONS


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


def _db_value(obj, name, default=""):
    try:
        value = getattr(obj.db, name, default)
    except Exception:
        return default
    return default if value is None else value


def _local_object(actor, dbref):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    return next(
        (obj for obj in list(getattr(location, "contents", []) or []) if getattr(obj, "id", None) == wanted),
        None,
    )


def _text_like(value):
    text = _clean_inline(value)
    if not text or _is_placeholder(text):
        return ""
    if len(text) < 10:
        return ""
    upper_ratio = sum(1 for ch in text if ch.isupper()) / max(1, sum(1 for ch in text if ch.isalpha()))
    if text.startswith(("DH7-", "FA-", "NPC-", "OBJ-", "ROOM-")):
        return ""
    if upper_ratio > 0.85 and len(text) < 40:
        return ""
    return text


def _append_unique(output, value, limit=8):
    text = _text_like(value)
    if text and text not in output:
        output.append(text)
    return len(output) >= limit


def _collect_text(value, output=None, *, depth=0, limit=8):
    if output is None:
        output = []
    if len(output) >= limit or depth > 5:
        return output
    if isinstance(value, str):
        _append_unique(output, value, limit=limit)
        return output
    if isinstance(value, dict):
        for key in TEXT_KEYS:
            if key in value and _append_unique(output, value.get(key), limit=limit):
                return output
        for preferred in (
            "orientation",
            "narrator_answers",
            "visible_details",
            "room_description",
            "sensory_facts",
            "perception_facts",
            "space_profile",
            "state_presentations",
            "conditions",
        ):
            if preferred in value:
                _collect_text(value.get(preferred), output, depth=depth + 1, limit=limit)
                if len(output) >= limit:
                    return output
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text.endswith("_id") or key_text in {"id", "room_id", "object_id", "npc_id", "campaign_tags", "source"}:
                continue
            _collect_text(item, output, depth=depth + 1, limit=limit)
            if len(output) >= limit:
                return output
        return output
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_text(item, output, depth=depth + 1, limit=limit)
            if len(output) >= limit:
                return output
    return output


def _room_description(location):
    for attr in ROOM_TEXT_ATTRS:
        value = _text_like(_db_value(location, attr, ""))
        if value:
            return value

    fragments = []
    for attr in EDITOR_ROOM_ATTRS:
        _collect_text(_db_value(location, attr, None), fragments, limit=8)
    if fragments:
        return "\n\n".join(fragments[:6])

    return "Este lugar todavía no tiene descripción narrativa importada desde el Map Editor."


def _object_description(obj):
    for attr in ("visible_description", "desc", "description", "look_text", "summary"):
        value = _text_like(_db_value(obj, attr, ""))
        if value:
            return value
    fragments = []
    for attr in ("interaction_facts", "state_presentations", "perception_facts", "sensory_facts"):
        _collect_text(_db_value(obj, attr, None), fragments, limit=3)
    return " ".join(fragments[:2])


def _dm_context(location):
    context = {}
    for attr in EDITOR_ROOM_ATTRS:
        value = _db_value(location, attr, None)
        if value not in (None, "", [], {}):
            context[attr] = value
    return context


def _is_visible_world_object(actor, obj):
    location = getattr(actor, "location", None) if actor else None
    if not location or not obj:
        return False
    if obj is actor:
        return False
    if getattr(obj, "destination", None):
        return False
    if bool(_db_value(obj, "hidden", False)):
        return False
    return bool(object_visible_in_world_state(obj, site=location))


def _visible_people_and_objects(actor):
    location = getattr(actor, "location", None) if actor else None
    people = []
    objects = []
    if not location:
        return people, objects
    for obj in list(getattr(location, "contents", []) or []):
        if not _is_visible_world_object(actor, obj):
            continue
        row = {
            "name": str(obj.key),
            "dbref": int(obj.id),
            "object_id": _clean(_db_value(obj, "object_id", "")) or None,
            "npc_id": _clean(_db_value(obj, "npc_id", "")) or None,
            "description": _object_description(obj),
        }
        if bool(_db_value(obj, "is_npc", False)):
            people.append(row)
        else:
            objects.append(row)
    people.sort(key=lambda row: row.get("name") or "")
    objects.sort(key=lambda row: row.get("name") or "")
    return people, objects


def _exit_rows(location):
    rows = []
    if not location:
        return rows
    for exit_obj in list(getattr(location, "exits", []) or []):
        state = inspect_exit_state(exit_obj)
        if bool(_db_value(exit_obj, "hidden", False)):
            continue
        if not bool(state.get("eligible")):
            continue
        if bool(_db_value(exit_obj, "is_locked", False)):
            continue
        if _clean(_db_value(exit_obj, "door_state", "open")).lower() != "open":
            continue
        dest = getattr(exit_obj, "destination", None)
        rows.append(
            {
                "name": str(exit_obj.key),
                "command": str(exit_obj.key),
                "exit_id": _clean(_db_value(exit_obj, "exit_id", "")) or None,
                "target": str(dest.key) if dest else "",
            }
        )
    rows.sort(key=lambda row: row.get("name") or "")
    return rows


def context_action_packet(actor):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return {"location": None, "room_id": None, "actions": [], "pending_roll": False, "build": SIZA_UI_RUNTIME_BUILD}

    actions = []
    exits_by_capability = {}
    for exit_obj in list(getattr(location, "exits", []) or []):
        stable_id = _clean(_db_value(exit_obj, "exit_id", "")) or f"DBREF:{int(exit_obj.id)}"
        exits_by_capability[f"MOVE:{stable_id}"] = exit_obj

    for capability in build_local_capability_catalog(actor):
        kind = _clean(capability.get("kind")).upper()
        target = _local_object(actor, capability.get("target_dbref"))

        if kind == "MOVEMENT":
            exit_obj = exits_by_capability.get(_clean(capability.get("capability_id")))
            state = inspect_exit_state(exit_obj) if exit_obj else {}
            if (
                not exit_obj
                or bool(_db_value(exit_obj, "hidden", False))
                or not bool(state.get("eligible"))
                or bool(_db_value(exit_obj, "is_locked", False))
                or _clean(_db_value(exit_obj, "door_state", "open")).lower() != "open"
            ):
                continue
            command = str(exit_obj.key)
            actions.append({"id": _clean(capability.get("capability_id")), "kind": kind, "label": command, "command": command, "target": str(getattr(getattr(exit_obj, "destination", None), "key", "") or "")})
            continue

        if not target or not _is_visible_world_object(actor, target):
            continue

        if kind == "OBJECT_ACTION":
            action = find_object_action(actor, target, capability.get("object_action_id"), eligible_only=True)
            if not action:
                continue
            phrases = [_clean(value) for value in _plain_list(action.get("input_phrases")) if _clean(value)]
            verb = _clean(phrases[0] if phrases else action.get("name"))
            command = verb if phrases else f"{verb} {target.key}".strip()
            label = _clean(action.get("name")) or verb or f"Usar {target.key}"
            actions.append({
                "id": _clean(capability.get("capability_id")),
                "kind": kind,
                "label": label,
                "command": command,
                "target": str(target.key),
                "object_id": _clean(getattr(target.db, "object_id", "")) or None,
                "requires_roll": bool(action.get("check")),
                "check": action.get("check") or None,
            })
            continue

        if kind == "INTERACTION":
            actions.append({"id": _clean(capability.get("capability_id")), "kind": kind, "label": f"Hablar con {target.key}", "command": f"hablar con {target.key}", "target": str(target.key)})
            continue

        if kind == "PERCEPTION" and not bool(_db_value(target, "is_npc", False)):
            actions.append({"id": _clean(capability.get("capability_id")), "kind": kind, "label": f"Examinar {target.key}", "command": f"observar {target.key}", "target": str(target.key)})

    pending = pending_object_actions(actor)
    if pending:
        current = pending[-1]
        actions.insert(0, {"id": f"ROLL:{current.get('attempt_id')}", "kind": "ROLL", "label": "Tirar d6", "command": "tirar", "target": _clean(current.get("object_name") or current.get("object_action_name"))})

    order = {"ROLL": 0, "OBJECT_ACTION": 10, "INTERACTION": 20, "MOVEMENT": 30, "PERCEPTION": 40}
    actions.sort(key=lambda row: (order.get(_clean(row.get("kind")), 99), _clean(row.get("label"))))
    return {
        "location": str(location.key),
        "room_id": _clean(_db_value(location, "room_id", "")) or None,
        "actions": actions,
        "pending_roll": bool(pending),
        "build": SIZA_UI_RUNTIME_BUILD,
    }


def room_snapshot_packet(actor):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return {"status": "NO_LOCATION", "build": SIZA_UI_RUNTIME_BUILD}
    people, objects = _visible_people_and_objects(actor)
    exits = _exit_rows(location)
    context = context_action_packet(actor)
    return {
        "status": "ROOM_SNAPSHOT",
        "room_name": str(location.key),
        "location": str(location.key),
        "room_id": _clean(_db_value(location, "room_id", "")) or None,
        "room_description": _room_description(location),
        "description": _room_description(location),
        "exits": exits,
        "visible_npcs": people,
        "people": people,
        "visible_objects": objects,
        "objects": objects,
        "available_actions": list(context.get("actions") or []),
        "actions": list(context.get("actions") or []),
        "pending_roll": bool(context.get("pending_roll")),
        "dm_context": _dm_context(location),
        "build": SIZA_UI_RUNTIME_BUILD,
    }


def _names(rows):
    output = []
    for row in list(rows or []):
        name = _clean((row or {}).get("name"))
        if name and name not in output:
            output.append(name)
    return output


def _room_text_block(packet):
    if not packet or packet.get("status") != "ROOM_SNAPSHOT":
        return ""
    location = _clean(packet.get("room_name") or packet.get("location")) or "Ubicación"
    description = _clean(packet.get("room_description") or packet.get("description")) or "Este lugar todavía no tiene descripción narrativa importada desde el Map Editor."
    exits = _names(packet.get("exits"))
    people = _names(packet.get("visible_npcs") or packet.get("people"))
    objects = _names(packet.get("visible_objects") or packet.get("objects"))
    return "\n".join(
        [
            location,
            description,
            "Exits: " + (", ".join(exits) if exits else "—"),
            "Characters: " + (", ".join(people) if people else "—"),
            "You see: " + (", ".join(objects) if objects else "—"),
        ]
    )


def emit_room_snapshot(actor, *, visible_text=False):
    packet = room_snapshot_packet(actor)
    actor.msg(siza_room_snapshot=((packet,), {}))
    actor.msg(siza_context_actions=((context_action_packet(actor),), {}))
    if visible_text:
        text = _room_text_block(packet)
        if text:
            actor.msg("\n" + text)
    return packet


class CmdSizaRoomState(Command):
    key = "siza-room-state"
    aliases = ()
    locks = "cmd:all()"
    help_category = "Siza"

    def func(self):
        emit_room_snapshot(self.caller, visible_text=True)


class CmdSizaUiContext(Command):
    key = "siza-ui-context"
    aliases = ()
    locks = "cmd:all()"
    help_category = "Siza"

    def func(self):
        self.caller.msg(siza_context_actions=((context_action_packet(self.caller),), {}))


class CmdSizaUiStats(Command):
    key = "siza-ui-stats"
    aliases = ()
    locks = "cmd:all()"
    help_category = "Siza"

    def func(self):
        stats = adventure_stats(self.caller)
        self.caller.msg(
            siza_character_stats=(({
                "stats": {key: stats.get(key) for key in ("FUE", "AGI", "COO", "INT", "PER", "PSI")},
                "authored_count": sum(1 for value in stats.values() if value is not None),
                "build": SIZA_UI_RUNTIME_BUILD,
            },), {})
        )
