"""Unified room-event registry used by the POKEROL editor.

The editor must answer one concrete question: which events can happen in the
player's current room?  This module merges three authorities without moving
world logic into the browser:

* SYSTEM events implemented by code (currently the Oak starter tutorial).
* WORLD_EVENT producer rules already owned by ``world_event_engine``.
* Room-local authored definitions stored on the Room for future handlers.

System events are edited through room-local overrides, so code identity and
handler wiring stay stable while authored text/configuration can change.
"""

from copy import deepcopy
from uuid import uuid4

from services.world_event_engine import inspect_event_sites, refresh_world_event_rules


EVENT_EDITOR_BUILD = "0.1.0-room-event-registry"
ROOM_EVENTS_ATTR = "pokerol_room_events"
ROOM_EVENT_OVERRIDES_ATTR = "pokerol_event_overrides"
OAK_TUTORIAL_EVENT_ID = "PALLET-OAK-START"


OAK_TUTORIAL_DEFAULT = {
    "id": OAK_TUTORIAL_EVENT_ID,
    "name": "Inicio · Profesor Oak y primer Pokémon",
    "source": "SYSTEM",
    "system": True,
    "deletable": False,
    "room_id": "KANTO-PAL-002",
    "event_type": "TUTORIAL",
    "handler": "OAK_STARTER_TUTORIAL",
    "enabled": True,
    "priority": 100,
    "trigger": "INTERACT_NPC",
    "trigger_target": "NPC-KANTO-PAL-OAK",
    "repeat_mode": "PER_CHARACTER",
    "description": (
        "Inicio jugable del laboratorio: hablar con Oak, escoger un starter, "
        "el rival escoge el counter y comienza la primera batalla."
    ),
    "stages": [
        {"id": "MEET_OAK", "label": "Hablar con Oak"},
        {"id": "CHOOSE_STARTER", "label": "Escoger primer Pokémon"},
        {"id": "RIVAL_CHALLENGE", "label": "Reto del rival"},
        {"id": "BATTLE", "label": "Primera batalla"},
        {"id": "COMPLETE", "label": "Tutorial completado"},
    ],
    "settings": {
        "starter_level": 5,
        "starter_choices": ["bulbasaur", "charmander", "squirtle"],
        "rival_pick_mode": "COUNTER",
    },
    "texts": {
        "oak_intro": "Llegaste justo a tiempo. Antes de partir necesitas escoger a tu primer Pokémon. Sobre la mesa tienes a {starters}. Elige uno.",
        "oak_choose_again": "Los tres están listos. {starters}: la decisión es tuya.",
        "oak_after_choice": "Ya tienes compañero. Ahora aprende a darle órdenes: tu rival quiere probarte aquí mismo.",
        "oak_battle": "Concéntrate en tu Pokémon y observa lo que hace el rival. Esta es tu primera batalla como entrenador.",
        "oak_complete": "Bien hecho. Ganar o perder era secundario: ya diste el primer paso como entrenador Pokémon.",
        "rival_wait": "Apúrate. Tú eliges primero; yo sabré cuál tomar después.",
        "rival_challenge": "Yo me quedo con {rival}. Ya que ambos tenemos Pokémon, ¡vamos a ver quién sabe usarlos mejor!",
        "rival_battle": "¡Nada de echarte atrás ahora! La batalla ya empezó.",
        "rival_player_win": "Tch... esta vez ganaste. La próxima no te lo voy a dejar tan fácil.",
        "rival_player_loss": "¿Ves? Tener un Pokémon no basta. Tendrás que entrenar si quieres alcanzarme.",
        "rival_draw": "Eso estuvo más parejo de lo que esperaba. La próxima lo resolvemos de verdad.",
        "oak_starter_chosen": "Entonces {starter} será tu compañero. Trátalo bien y aprende a trabajar con él.",
        "rival_starter_chosen": "Perfecto. Entonces yo elijo a {rival}. ¡Ahora que ambos tenemos Pokémon, te reto a una batalla!",
        "rival_battle_start": "¡Vamos, {rival}! ¡Muéstrale lo que podemos hacer!",
    },
}

SYSTEM_EVENTS = (OAK_TUTORIAL_DEFAULT,)


def _plain_dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _clean(value, limit=None):
    text = str(value or "").strip()
    if limit:
        return text[:limit]
    return text


def _room_id(room):
    return _clean(getattr(getattr(room, "db", None), "room_id", ""))


def _deep_merge(base, override):
    output = deepcopy(base or {})
    for key, value in _plain_dict(override).items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = _deep_merge(output[key], value)
        else:
            output[key] = deepcopy(value)
    return output


def _system_definition(room, event_id):
    rid = _room_id(room)
    wanted = _clean(event_id)
    for definition in SYSTEM_EVENTS:
        if definition.get("id") == wanted and definition.get("room_id") == rid:
            return deepcopy(definition)
    return None


def _overrides(room):
    return _plain_dict(getattr(room.db, ROOM_EVENT_OVERRIDES_ATTR, {})) if room else {}


def _room_events(room):
    output = []
    if not room:
        return output
    for raw in _plain_list(getattr(room.db, ROOM_EVENTS_ATTR, [])):
        row = _plain_dict(raw)
        if row.get("id"):
            output.append(row)
    return output


def _normalize_common(row):
    event = deepcopy(row or {})
    event["id"] = _clean(event.get("id"), 120)
    event["name"] = _clean(event.get("name"), 160) or event["id"] or "Evento"
    event["event_type"] = _clean(event.get("event_type"), 48).upper() or "STORY"
    event["handler"] = _clean(event.get("handler"), 80).upper() or "ROOM_EVENT"
    event["enabled"] = bool(event.get("enabled", True))
    try:
        event["priority"] = max(0, min(999, int(event.get("priority", 50))))
    except (TypeError, ValueError):
        event["priority"] = 50
    event["trigger"] = _clean(event.get("trigger"), 64).upper() or "MANUAL"
    event["trigger_target"] = _clean(event.get("trigger_target"), 160)
    event["repeat_mode"] = _clean(event.get("repeat_mode"), 48).upper() or "PER_CHARACTER"
    event["description"] = _clean(event.get("description"), 6000)
    event["texts"] = {str(k): str(v or "")[:6000] for k, v in _plain_dict(event.get("texts")).items()}
    event["settings"] = _plain_dict(event.get("settings"))
    event["stages"] = [_plain_dict(item) for item in _plain_list(event.get("stages")) if _plain_dict(item)]
    return event


def _effective_system_event(room, definition):
    overrides = _overrides(room)
    override = _plain_dict(overrides.get(definition.get("id")))
    event = _normalize_common(_deep_merge(definition, override))
    event["source"] = "SYSTEM"
    event["system"] = True
    event["deletable"] = False
    event["room_id"] = definition.get("room_id")
    event["handler"] = definition.get("handler")
    event["overridden"] = bool(override)
    return event


def _world_event_rows(room):
    rid = _room_id(room)
    rows = []
    if not rid:
        return rows
    for site_row in inspect_event_sites():
        if _clean(site_row.get("room_id")) != rid:
            continue
        site = site_row.get("site")
        site_dbref = int(getattr(site, "id", 0) or 0) if site else 0
        state = _plain_dict(site_row.get("state"))
        for raw_rule in _plain_list(site_row.get("rules")):
            rule = _plain_dict(raw_rule)
            rule_id = _clean(rule.get("id"))
            if not rule_id:
                continue
            event_id = _clean(rule.get("event_id")) or rule_id
            goal_type = _clean(rule.get("goal_type") or "EVENT").upper()
            event = _normalize_common(
                {
                    "id": "WORLD:" + rule_id,
                    "name": _clean(rule.get("name")) or _clean(rule.get("activity")) or event_id,
                    "event_type": goal_type,
                    "handler": "WORLD_EVENT_RULE",
                    "enabled": bool(rule.get("enabled", True)),
                    "priority": rule.get("priority", 80),
                    "trigger": "STATE",
                    "trigger_target": rule.get("field"),
                    "repeat_mode": rule.get("response_mode") or ("PERSISTENT" if goal_type == "DANGER" else "ACK"),
                    "description": _clean(rule.get("description")) or _clean(rule.get("activity")),
                    "settings": {
                        "event_id": event_id,
                        "rule_id": rule_id,
                        "field": rule.get("field"),
                        "op": rule.get("op") or "eq",
                        "value": rule.get("value"),
                        "activity": rule.get("activity"),
                        "awareness_mode": rule.get("awareness_mode") or "AUDIENCE",
                        "npc_ids": _plain_list(rule.get("npc_ids")),
                        "job_ids": _plain_list(rule.get("job_ids")),
                        "faction_ids": _plain_list(rule.get("faction_ids")),
                        "affected_room_ids": _plain_list(rule.get("affected_room_ids")),
                        "blocks_jobs": bool(rule.get("blocks_jobs", goal_type == "DANGER")),
                        "site_dbref": site_dbref,
                        "site_name": getattr(site, "key", "") if site else "",
                        "current_state": state.get(_clean(rule.get("field"))),
                    },
                }
            )
            event.update(
                {
                    "source": "WORLD_EVENT",
                    "system": False,
                    "deletable": False,
                    "room_id": rid,
                    "world_rule_id": rule_id,
                    "site_dbref": site_dbref,
                }
            )
            rows.append(event)
    return rows


def list_room_events(room):
    if not room:
        return []
    rid = _room_id(room)
    rows = []
    for definition in SYSTEM_EVENTS:
        if definition.get("room_id") == rid:
            rows.append(_effective_system_event(room, definition))
    rows.extend(_world_event_rows(room))
    for raw in _room_events(room):
        event = _normalize_common(raw)
        event.update(
            {
                "source": "ROOM",
                "system": False,
                "deletable": True,
                "room_id": rid,
            }
        )
        rows.append(event)
    rows.sort(key=lambda item: (-int(item.get("priority", 0)), str(item.get("name") or "")))
    return rows


def get_room_event(room, event_id):
    wanted = _clean(event_id)
    for event in list_room_events(room):
        if event.get("id") == wanted:
            return event
    return None


def _editable_system_override(definition, payload):
    allowed = {
        "name",
        "enabled",
        "priority",
        "trigger",
        "trigger_target",
        "repeat_mode",
        "description",
        "texts",
        "settings",
        "stages",
        "event_type",
    }
    override = {key: deepcopy(value) for key, value in _plain_dict(payload).items() if key in allowed}
    merged = _normalize_common(_deep_merge(definition, override))
    # Store only editor-owned fields, never identity/handler/room wiring.
    return {key: deepcopy(merged.get(key)) for key in allowed if key in merged}


def _save_system_event(room, definition, payload):
    overrides = _overrides(room)
    overrides[definition["id"]] = _editable_system_override(definition, payload)
    setattr(room.db, ROOM_EVENT_OVERRIDES_ATTR, overrides)
    return _effective_system_event(room, definition)


def _save_world_event(room, existing, payload):
    rid = _room_id(room)
    settings = _plain_dict(payload.get("settings"))
    site_dbref = int(existing.get("site_dbref") or settings.get("site_dbref") or 0)
    rule_id = _clean(existing.get("world_rule_id") or settings.get("rule_id"))
    if not site_dbref or not rule_id:
        raise ValueError("El evento de mundo no tiene sitio/regla editable.")

    for site_row in inspect_event_sites():
        site = site_row.get("site")
        if int(getattr(site, "id", 0) or 0) != site_dbref:
            continue
        if _clean(site_row.get("room_id")) != rid:
            raise ValueError("La regla ya no pertenece a este cuarto.")
        rules = [_plain_dict(item) for item in _plain_list(site_row.get("rules"))]
        found = False
        for index, rule in enumerate(rules):
            if _clean(rule.get("id")) != rule_id:
                continue
            found = True
            rule["enabled"] = bool(payload.get("enabled", existing.get("enabled", True)))
            rule["goal_type"] = _clean(payload.get("event_type") or existing.get("event_type") or "EVENT").upper()
            try:
                rule["priority"] = max(0, min(999, int(payload.get("priority", existing.get("priority", 80)))))
            except (TypeError, ValueError):
                rule["priority"] = 80
            rule["response_mode"] = _clean(payload.get("repeat_mode") or existing.get("repeat_mode") or "ACK").upper()
            rule["field"] = _clean(settings.get("field") or rule.get("field"), 120)
            rule["op"] = _clean(settings.get("op") or rule.get("op") or "eq", 16)
            if "value" in settings:
                rule["value"] = settings.get("value")
            rule["activity"] = _clean(settings.get("activity") or payload.get("description") or rule.get("activity"), 1000)
            rule["awareness_mode"] = _clean(settings.get("awareness_mode") or rule.get("awareness_mode") or "AUDIENCE", 32).upper()
            for key in ("npc_ids", "job_ids", "faction_ids", "affected_room_ids"):
                if key in settings:
                    rule[key] = [str(v) for v in _plain_list(settings.get(key)) if str(v).strip()]
            if "blocks_jobs" in settings:
                rule["blocks_jobs"] = bool(settings.get("blocks_jobs"))
            rules[index] = rule
            break
        if not found:
            raise ValueError("La regla de evento ya no existe.")
        site.db.world_event_rules = rules
        refresh_world_event_rules()
        return get_room_event(room, existing["id"])
    raise ValueError("El sitio de evento ya no existe.")


def save_room_event(room, payload):
    if not room:
        raise ValueError("No hay cuarto activo.")
    data = _plain_dict(payload)
    event_id = _clean(data.get("id"), 120)
    if not event_id:
        event_id = "ROOM-EVENT-" + uuid4().hex[:12].upper()
        data["id"] = event_id

    definition = _system_definition(room, event_id)
    if definition:
        return _save_system_event(room, definition, data)

    existing = get_room_event(room, event_id)
    if existing and existing.get("source") == "WORLD_EVENT":
        return _save_world_event(room, existing, data)

    events = _room_events(room)
    normalized = _normalize_common(data)
    normalized["id"] = event_id
    normalized["handler"] = _clean(normalized.get("handler") or "ROOM_EVENT", 80).upper()
    replaced = False
    for index, row in enumerate(events):
        if _clean(row.get("id")) == event_id:
            events[index] = normalized
            replaced = True
            break
    if not replaced:
        events.append(normalized)
    setattr(room.db, ROOM_EVENTS_ATTR, events)
    return get_room_event(room, event_id)


def reset_or_delete_room_event(room, event_id):
    if not room:
        raise ValueError("No hay cuarto activo.")
    wanted = _clean(event_id)
    definition = _system_definition(room, wanted)
    if definition:
        overrides = _overrides(room)
        existed = wanted in overrides
        overrides.pop(wanted, None)
        setattr(room.db, ROOM_EVENT_OVERRIDES_ATTR, overrides)
        return {"status": "RESET", "event_id": wanted, "changed": existed}

    existing = get_room_event(room, wanted)
    if existing and existing.get("source") == "WORLD_EVENT":
        raise ValueError("Las reglas WORLD_EVENT se editan o desactivan; no se borran desde este panel.")

    events = _room_events(room)
    filtered = [row for row in events if _clean(row.get("id")) != wanted]
    if len(filtered) == len(events):
        raise ValueError("El evento ya no existe en este cuarto.")
    setattr(room.db, ROOM_EVENTS_ATTR, filtered)
    return {"status": "DELETED", "event_id": wanted, "changed": True}
