"""Authoritative generic Room-event lifecycle for POKEROL.

Authored ROOM events can now actually run. The browser only renders packets. This
service owns trigger eligibility, once-per-visit chance, persistent lifecycle,
completion conditions, snoozing and idempotent trainer memories/history.

Specialized handlers such as Oak keep their own authority; WORLD_EVENT rules keep
using the world-event engine. This runtime intentionally executes only ROOM_EVENT.
"""

import random
import re
from copy import deepcopy

from services.pokerol_event_editor_service import get_room_event, list_room_events
from services.pokerol_event_progress import complete_event, event_progress, mark_event_active, snooze_event
from services.pokerol_player_progress import badges, event_history, memories, record_event, remember
from services.pokemon_party_engine import party_state


ROOM_EVENT_RUNTIME_BUILD = "0.1.0-generic-room-event-lifecycle"
TERMINAL_REPEAT_MODES = {"ONCE", "PER_CHARACTER"}
REPEATABLE_MODES = {"REPEATABLE", "ALWAYS", "ACK", "PERSISTENT"}
VALID_SNOOZE_POLICIES = {"UNTIL_REENTRY", "MANUAL", "NONE"}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _text(value, limit=None):
    result = str(value or "").strip()
    return result[:limit] if limit else result


def _room_id(room):
    return _text(getattr(getattr(room, "db", None), "room_id", "")) if room else ""


def _repeat_mode(event):
    mode = _text(_dict(event).get("repeat_mode")).upper() or "PER_CHARACTER"
    return mode if mode in TERMINAL_REPEAT_MODES | REPEATABLE_MODES else "PER_CHARACTER"


def _settings(event):
    return _dict(_dict(event).get("settings"))


def _policy(event):
    return _dict(_dict(event).get("scene_policy"))


def _presentation(event):
    value = _dict(_dict(event).get("presentation"))
    if value:
        return value
    return _dict(_settings(event).get("presentation"))


def _memory_spec(event, phase):
    phase = _text(phase).lower()
    direct = _dict(_dict(event).get("memory_on_" + phase))
    if direct:
        return direct
    return _dict(_settings(event).get("memory_on_" + phase))


def _bool_setting(event, key, default=False):
    if key in _dict(event):
        return bool(_dict(event).get(key))
    settings = _settings(event)
    if key in settings:
        return bool(settings.get(key))
    return bool(default)


def _int_setting(event, key, default=0, low=0, high=100):
    raw = _dict(event).get(key, _settings(event).get(key, default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(low, min(high, value))


def _event_is_generic(event):
    row = _dict(event)
    return bool(
        row.get("enabled", True)
        and _text(row.get("source")).upper() == "ROOM"
        and _text(row.get("handler")).upper() in {"ROOM_EVENT", "GENERIC_ROOM_EVENT"}
    )


def _event_history_has(actor, event_id):
    wanted = _text(event_id)
    return any(_text(row.get("event_id")) == wanted for row in event_history(actor))


def _memory_has(actor, event_id):
    wanted = _text(event_id)
    return any(_text(row.get("event_id")) == wanted for row in memories(actor))


def _owned_pokemon_species(actor):
    result = set()
    state = party_state(actor)
    for row in _list(state.get("party")):
        species = _text(_dict(row).get("species_id")).upper()
        if species:
            result.add(species)
    for row in _list(getattr(actor.db, "pokerol_pc_storage", [])) if actor else []:
        species = _text(_dict(row).get("species_id")).upper()
        if species:
            result.add(species)
    return result


def _flag_value(actor, key):
    flags = _dict(getattr(actor.db, "pokerol_flags", {})) if actor else {}
    return flags.get(key)


def _coerce_literal(value):
    raw = _text(value)
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"none", "null"}:
        return None
    if re.fullmatch(r"-?\d+", raw):
        try:
            return int(raw)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        try:
            return float(raw)
        except ValueError:
            pass
    return raw


def condition_result(actor, condition):
    """Evaluate one deliberately small persistent-fact condition language."""
    raw = _text(condition)
    upper = raw.upper()
    if not raw:
        return {"condition": raw, "met": True, "reason": "EMPTY"}
    if upper == "ALWAYS":
        return {"condition": raw, "met": True, "reason": "ALWAYS"}

    prefix, sep, body = raw.partition(":")
    kind = prefix.strip().upper()
    body = body.strip() if sep else ""

    if kind == "ROOM":
        current = _room_id(getattr(actor, "location", None))
        return {"condition": raw, "met": current.upper() == body.upper(), "actual": current}
    if kind == "BADGE":
        wanted = body.upper()
        found = any(_text(row.get("id")).upper() == wanted for row in badges(actor))
        return {"condition": raw, "met": found}
    if kind == "MEMORY":
        wanted = body.upper()
        found = any(_text(row.get("event_id")).upper() == wanted or _text(row.get("id")).upper() == wanted for row in memories(actor))
        return {"condition": raw, "met": found}
    if kind == "EVENT":
        wanted = body.upper()
        found = any(_text(row.get("event_id")).upper() == wanted for row in event_history(actor))
        return {"condition": raw, "met": found}
    if kind in {"EVENT_COMPLETE", "EVENT_COMPLETED"}:
        progress = event_progress(actor, body)
        return {"condition": raw, "met": progress.get("status") == "COMPLETED", "actual": progress.get("status")}
    if kind == "POKEMON":
        return {"condition": raw, "met": body.upper() in _owned_pokemon_species(actor)}
    if kind == "BATTLE_OUTCOME":
        last = _dict(getattr(actor.db, "last_pokemon_battle", {})) if actor else {}
        actual = _text(last.get("outcome")).upper()
        return {"condition": raw, "met": actual == body.upper(), "actual": actual}
    if kind == "FLAG":
        key, eq, expected = body.partition("=")
        key = key.strip()
        actual = _flag_value(actor, key)
        if not eq:
            return {"condition": raw, "met": bool(actual), "actual": actual}
        wanted = _coerce_literal(expected)
        return {"condition": raw, "met": actual == wanted, "actual": actual, "expected": wanted}

    return {"condition": raw, "met": False, "reason": "UNSUPPORTED_CONDITION"}


def conditions_result(actor, conditions):
    rows = [condition_result(actor, value) for value in _list(conditions) if _text(value)]
    return {
        "met": all(bool(row.get("met")) for row in rows) if rows else True,
        "results": rows,
    }


def _start_conditions(event):
    direct = _list(_dict(event).get("start_conditions"))
    return direct or _list(_settings(event).get("start_conditions"))


def _completion_conditions(event):
    direct = _list(_dict(event).get("completion_conditions"))
    if direct:
        return direct
    return _list(_policy(event).get("completion_conditions"))


def _visit_serial(actor):
    try:
        return max(0, int(getattr(actor.db, "pokerol_room_visit_serial", 0) or 0))
    except (TypeError, ValueError):
        return 0


def note_room_visit(actor, room=None):
    """Increment the persistent visit token only after a real room transition."""
    if not actor:
        return 0
    serial = _visit_serial(actor) + 1
    actor.db.pokerol_room_visit_serial = serial
    actor.db.pokerol_last_visited_room_id = _room_id(room or getattr(actor, "location", None))
    return serial


def _trigger_key(actor, event, trigger, token=None):
    base = _text(trigger).upper() or "MANUAL"
    if base == "ENTER_ROOM":
        value = token if token is not None else _visit_serial(actor)
        return "ENTER_ROOM:{}:{}".format(_room_id(getattr(actor, "location", None)), value)
    return "{}:{}".format(base, _text(token) or "NOW")


def _eligible_for_trigger(event, trigger, trigger_target=""):
    row = _dict(event)
    wanted = _text(row.get("trigger")).upper() or "MANUAL"
    actual = _text(trigger).upper() or "MANUAL"
    if wanted != actual:
        return False
    authored_target = _text(row.get("trigger_target"))
    if authored_target and trigger_target and authored_target.upper() != _text(trigger_target).upper():
        return False
    return True


def _should_resume_snoozed(progress, event, trigger_key):
    if _text(progress.get("status")).upper() != "SNOOZED":
        return True
    facts = _dict(progress.get("facts"))
    previous = _text(facts.get("last_trigger_key"))
    policy = _text(_dict(event).get("snooze_policy") or _settings(event).get("snooze_policy") or "UNTIL_REENTRY").upper()
    if policy not in VALID_SNOOZE_POLICIES:
        policy = "UNTIL_REENTRY"
    if policy == "NONE":
        return True
    if policy == "MANUAL":
        return False
    return bool(trigger_key and trigger_key != previous)


def _chance_passes(actor, event, progress, trigger_key, rng=None):
    chance = _int_setting(event, "chance_percent", 100, 0, 100)
    facts = _dict(progress.get("facts"))
    if _text(facts.get("chance_trigger_key")) == trigger_key:
        return bool(facts.get("chance_passed")), int(facts.get("chance_roll", 100) or 100), False
    if chance >= 100:
        return True, 100, True
    if chance <= 0:
        return False, 100, True
    roller = rng or random.SystemRandom()
    roll = int(roller.randint(1, 100))
    return roll <= chance, roll, True


def _occurrence(progress, new_trigger=False):
    facts = _dict(progress.get("facts"))
    current = max(0, int(facts.get("occurrence", 0) or 0))
    if new_trigger:
        return current + 1
    return max(1, current)


def _memory_defaults(event, phase):
    phase = _text(phase).lower()
    name = _text(_dict(event).get("name")) or _text(_dict(event).get("id")) or "Evento"
    description = _text(_dict(event).get("description"))
    return {
        "enabled": bool(_policy(event).get("memory_on_complete", False)) if phase == "complete" else False,
        "title": name,
        "text": description,
        "category": "EVENTO COMPLETADO" if phase == "complete" else "EVENTO",
        "image": "",
        "importance": 7 if phase == "complete" else 5,
    }


def _normalize_memory(event, phase):
    defaults = _memory_defaults(event, phase)
    raw = _memory_spec(event, phase)
    if raw:
        defaults.update(raw)
    elif phase == "start" and _bool_setting(event, "memory_start_enabled", False):
        defaults["enabled"] = True
    elif phase == "complete" and _bool_setting(event, "memory_complete_enabled", defaults.get("enabled", False)):
        defaults["enabled"] = True
    defaults["enabled"] = bool(defaults.get("enabled", False))
    defaults["title"] = _text(defaults.get("title"), 160) or _text(_dict(event).get("name"), 160)
    defaults["text"] = _text(defaults.get("text"), 5000)
    defaults["category"] = _text(defaults.get("category"), 64) or "EVENTO"
    defaults["image"] = _text(defaults.get("image"), 1000)
    try:
        defaults["importance"] = max(0, min(10, int(defaults.get("importance", 5) or 5)))
    except (TypeError, ValueError):
        defaults["importance"] = 5
    return defaults


def _record_milestone(actor, event, phase, occurrence, result=""):
    event_id = _text(_dict(event).get("id"))
    room_id = _room_id(getattr(actor, "location", None))
    suffix = "{}:{}".format(_text(phase).upper(), occurrence)
    milestone_id = "{}:{}".format(event_id, suffix)
    spec = _normalize_memory(event, phase)
    if not _event_history_has(actor, milestone_id):
        record_event(
            actor,
            event_id=milestone_id,
            title=spec.get("title") or _text(_dict(event).get("name")),
            result=_text(result) or _text(phase).upper(),
            room_id=room_id,
            data={"event_id": event_id, "phase": phase, "occurrence": occurrence},
            create_memory=False,
        )
    if spec.get("enabled") and not _memory_has(actor, milestone_id):
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", event_id)[:60] or "ROOM-EVENT"
        remember(
            actor,
            memory_id="MEM-{}-{}-{}".format(safe_id, _text(phase).upper(), occurrence),
            title=spec.get("title"),
            text=spec.get("text"),
            category=spec.get("category"),
            event_id=milestone_id,
            room_id=room_id,
            image=spec.get("image"),
            importance=spec.get("importance", 5),
        )


def _modal_packet(event, occurrence):
    row = _dict(event)
    presentation = _presentation(row)
    if not presentation and not _bool_setting(row, "autorun", False):
        return None
    title = _text(presentation.get("title")) or _text(row.get("name"))
    speaker = _text(presentation.get("speaker")) or "NARRADOR"
    body = _text(presentation.get("text")) or _text(_dict(row.get("texts")).get("intro")) or _text(row.get("description"))
    media_src = _text(presentation.get("media_src"))
    media_type = _text(presentation.get("media_type")).lower() or ("video" if media_src.lower().endswith((".mp4", ".webm", ".ogg")) else "image")
    blocking = bool(presentation.get("blocking", _bool_setting(row, "blocking", False)))
    allow_snooze = bool(presentation.get("allow_snooze", _bool_setting(row, "allow_snooze", True)))
    acknowledge = bool(presentation.get("acknowledge_completes", not bool(_completion_conditions(row))))
    event_id = _text(row.get("id"))
    buttons = []
    if acknowledge:
        buttons.append({"label": _text(presentation.get("continue_label")) or "CONTINUAR", "command": "pokerol-room-event complete " + event_id, "primary": True})
    if allow_snooze:
        buttons.append({"label": _text(presentation.get("snooze_label")) or "AHORA NO", "command": "pokerol-room-event snooze " + event_id})
    return {
        "event_id": event_id,
        "modal_id": "ROOM-EVENT:{}:{}".format(event_id, occurrence),
        "kind": "ROOM_EVENT",
        "title": title,
        "speaker": speaker,
        "text": body,
        "caption": _text(presentation.get("caption")),
        "media_type": media_type,
        "media_src": media_src,
        "autoplay": bool(presentation.get("autoplay", True)),
        "muted": bool(presentation.get("muted", True)),
        "blocking": blocking,
        "allow_close": not blocking,
        "buttons": buttons,
        "occurrence": occurrence,
        "build": ROOM_EVENT_RUNTIME_BUILD,
    }


def _emit_modal(actor, event, occurrence):
    packet = _modal_packet(event, occurrence)
    if not packet:
        return None
    actor.msg(pokerol_event_modal=((packet,), {}))
    return packet


def start_room_event(actor, event, *, trigger="MANUAL", trigger_target="", trigger_token=None, rng=None):
    row = _dict(event)
    event_id = _text(row.get("id"))
    if not actor or not event_id or not _event_is_generic(row):
        return {"accepted": False, "status": "EVENT_NOT_GENERIC_OR_DISABLED", "event_id": event_id, "build": ROOM_EVENT_RUNTIME_BUILD}
    if not _eligible_for_trigger(row, trigger, trigger_target=trigger_target):
        return {"accepted": False, "status": "TRIGGER_MISMATCH", "event_id": event_id, "build": ROOM_EVENT_RUNTIME_BUILD}

    progress = event_progress(actor, event_id)
    repeat = _repeat_mode(row)
    if progress.get("status") == "COMPLETED" and repeat in TERMINAL_REPEAT_MODES:
        return {"accepted": False, "status": "EVENT_ALREADY_COMPLETED", "event_id": event_id, "progress": progress, "build": ROOM_EVENT_RUNTIME_BUILD}

    trigger_key = _trigger_key(actor, row, trigger, trigger_token)
    if not _should_resume_snoozed(progress, row, trigger_key):
        return {"accepted": False, "status": "EVENT_SNOOZED", "event_id": event_id, "progress": progress, "build": ROOM_EVENT_RUNTIME_BUILD}

    start_gate = conditions_result(actor, _start_conditions(row))
    if not start_gate.get("met"):
        return {"accepted": False, "status": "START_CONDITIONS_NOT_MET", "event_id": event_id, "conditions": start_gate, "build": ROOM_EVENT_RUNTIME_BUILD}

    facts = _dict(progress.get("facts"))
    new_trigger = _text(facts.get("last_trigger_key")) != trigger_key
    passed, roll, newly_rolled = _chance_passes(actor, row, progress, trigger_key, rng=rng)
    occurrence = _occurrence(progress, new_trigger=new_trigger)
    chance_facts = {
        "last_trigger_key": trigger_key,
        "chance_trigger_key": trigger_key,
        "chance_roll": roll,
        "chance_passed": passed,
        "chance_percent": _int_setting(row, "chance_percent", 100, 0, 100),
        "occurrence": occurrence,
        "trigger": _text(trigger).upper(),
        "trigger_target": _text(trigger_target),
    }
    if not passed:
        progress = snooze_event(actor, event_id, stage="CHANCE_MISSED", facts=chance_facts)
        return {"accepted": False, "status": "CHANCE_MISSED", "event_id": event_id, "progress": progress, "roll": roll, "new_roll": newly_rolled, "build": ROOM_EVENT_RUNTIME_BUILD}

    # Do not emit the same autorun modal repeatedly for snapshots inside one visit.
    already_presented = _text(facts.get("last_presented_trigger")) == trigger_key and progress.get("status") == "ACTIVE"
    chance_facts["last_presented_trigger"] = trigger_key
    progress = mark_event_active(actor, event_id, stage="ACTIVE", facts=chance_facts)
    if new_trigger:
        _record_milestone(actor, row, "start", occurrence, result="STARTED")
    modal = None if already_presented else _emit_modal(actor, row, occurrence)
    return {
        "accepted": True,
        "status": "EVENT_ACTIVE" if not already_presented else "EVENT_ALREADY_ACTIVE_THIS_TRIGGER",
        "event_id": event_id,
        "occurrence": occurrence,
        "progress": progress,
        "modal": modal,
        "build": ROOM_EVENT_RUNTIME_BUILD,
    }


def snooze_room_event(actor, event_id):
    room = getattr(actor, "location", None) if actor else None
    event = get_room_event(room, event_id) if room else None
    if not event or not _event_is_generic(event):
        return {"accepted": False, "status": "ROOM_EVENT_NOT_FOUND", "event_id": _text(event_id), "build": ROOM_EVENT_RUNTIME_BUILD}
    progress = event_progress(actor, event_id)
    facts = _dict(progress.get("facts"))
    progress = snooze_event(actor, event_id, stage=progress.get("stage") or "ACTIVE", facts={"last_trigger_key": facts.get("last_trigger_key")})
    return {"accepted": True, "status": "EVENT_SNOOZED", "event_id": event_id, "progress": progress, "build": ROOM_EVENT_RUNTIME_BUILD}


def complete_room_event(actor, event_id, *, reason="PLAYER_ACK", force=False):
    room = getattr(actor, "location", None) if actor else None
    event = get_room_event(room, event_id) if room else None
    if not event or not _event_is_generic(event):
        return {"accepted": False, "status": "ROOM_EVENT_NOT_FOUND", "event_id": _text(event_id), "build": ROOM_EVENT_RUNTIME_BUILD}
    progress = event_progress(actor, event_id)
    checks = conditions_result(actor, _completion_conditions(event))
    if not force and _completion_conditions(event) and not checks.get("met"):
        return {"accepted": False, "status": "COMPLETION_CONDITIONS_NOT_MET", "event_id": event_id, "conditions": checks, "progress": progress, "build": ROOM_EVENT_RUNTIME_BUILD}

    occurrence = _occurrence(progress)
    _record_milestone(actor, event, "complete", occurrence, result=_text(reason).upper() or "COMPLETED")
    facts = _dict(progress.get("facts"))
    facts.update({"last_completion_reason": _text(reason).upper(), "last_completed_occurrence": occurrence})
    if _repeat_mode(event) in TERMINAL_REPEAT_MODES:
        next_progress = complete_event(actor, event_id, stage="COMPLETE", reason=reason, facts=facts)
    else:
        # Repeatable events finish this occurrence without becoming terminal.
        next_progress = snooze_event(actor, event_id, stage="COMPLETE", facts=facts)
    return {"accepted": True, "status": "EVENT_COMPLETED", "event_id": event_id, "occurrence": occurrence, "progress": next_progress, "build": ROOM_EVENT_RUNTIME_BUILD}


def reconcile_room_events(actor):
    """Complete active generic events whose persistent completion facts are now true."""
    room = getattr(actor, "location", None) if actor else None
    if not room:
        return []
    output = []
    for event in list_room_events(room):
        if not _event_is_generic(event):
            continue
        progress = event_progress(actor, event.get("id"))
        if progress.get("status") != "ACTIVE":
            continue
        conditions = _completion_conditions(event)
        if conditions and conditions_result(actor, conditions).get("met"):
            output.append(complete_room_event(actor, event.get("id"), reason="CONDITIONS_MET"))
    return output


def process_room_event_trigger(actor, trigger, *, trigger_target="", trigger_token=None, rng=None):
    """Process all authored generic events matching one authoritative Room trigger."""
    room = getattr(actor, "location", None) if actor else None
    if not room:
        return []
    reconcile_room_events(actor)
    rows = []
    for event in list_room_events(room):
        if not _event_is_generic(event):
            continue
        if not _eligible_for_trigger(event, trigger, trigger_target=trigger_target):
            continue
        if _text(trigger).upper() == "ENTER_ROOM" and not _bool_setting(event, "autorun", True):
            continue
        rows.append(start_room_event(actor, event, trigger=trigger, trigger_target=trigger_target, trigger_token=trigger_token, rng=rng))
    return rows


def runtime_event_packet(actor):
    """Small read-only packet for UI/debug; no triggering happens here."""
    room = getattr(actor, "location", None) if actor else None
    if not room:
        return {"build": ROOM_EVENT_RUNTIME_BUILD, "events": []}
    rows = []
    for event in list_room_events(room):
        if not _event_is_generic(event):
            continue
        progress = event_progress(actor, event.get("id"))
        rows.append({
            "id": event.get("id"),
            "name": event.get("name"),
            "trigger": event.get("trigger"),
            "repeat_mode": event.get("repeat_mode"),
            "progress": deepcopy(progress),
            "start_conditions": deepcopy(_start_conditions(event)),
            "completion_conditions": deepcopy(_completion_conditions(event)),
            "autorun": _bool_setting(event, "autorun", False),
            "chance_percent": _int_setting(event, "chance_percent", 100, 0, 100),
            "blocking": _bool_setting(event, "blocking", False),
        })
    return {"build": ROOM_EVENT_RUNTIME_BUILD, "events": rows}
