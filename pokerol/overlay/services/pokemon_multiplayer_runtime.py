"""Persistent runtime for POKEROL shared multiplayer battles."""

from copy import deepcopy
from time import time

from services.pokemon_battle_engine import normalize_pokemon
from services.pokemon_multibattle_engine import human_order_requirements, resolve_locked_round, validate_order
from services.pokemon_multiplayer_session_engine import actor_from_dbref, emit_session, public_session, session_for_actor
from services.pokemon_party_engine import (
    able_party_slots,
    active_slot,
    battle_profile_for_slot,
    set_active_slot,
    update_owned_from_battle,
)
from typeclasses.pokemon_battle_session import participant_id


MULTI_RUNTIME_BUILD = "0.2.0-outcome-switch-runtime"


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


def _text(value):
    return str(value or "").strip()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clone(value):
    return deepcopy(value)


def _combatant_ref(session, participant_id_value):
    wanted = _text(participant_id_value)
    rows = _list(session.db.combatants)
    for index, raw in enumerate(rows):
        row = _dict(raw)
        if _text(row.get("controller_kind")).upper() != "HUMAN":
            continue
        if _text(row.get("controller_participant_id")) == wanted:
            return rows, index, row
    return rows, -1, None


def _write_state_to_session(session, state):
    session.db.combatants = _clone(_list(state.get("combatants")))
    session.db.pending_orders = _clone(_dict(state.get("pending_orders")))
    session.db.turn = max(1, _int(state.get("turn"), 1))
    session.db.phase = _text(state.get("phase")).upper() or "COMMAND"
    session.db.status = _text(state.get("status")).upper() or "ACTIVE"
    session.db.log = _clone(_list(state.get("log"))[-220:])
    session.db.outcome = _text(state.get("outcome")).upper()
    session.db.winning_team = _text(state.get("winning_team")).upper()
    session.db.updated_at = int(time())
    if _text(session.db.status).upper() == "COMPLETE":
        session.db.completed_at = int(time())


def _persist_human_combatants(session):
    persisted = []
    for raw in _list(session.db.combatants):
        row = _dict(raw)
        if _text(row.get("controller_kind")).upper() != "HUMAN":
            continue
        actor = actor_from_dbref(row.get("actor_dbref"))
        pokemon = _dict(row.get("pokemon"))
        if actor and pokemon:
            persisted.append({
                "actor_dbref": int(actor.id),
                "entity_id": pokemon.get("entity_id"),
                "persisted": bool(update_owned_from_battle(actor, pokemon)),
            })
    return persisted


def _mark_forced_switches(session):
    """Mark fainted human actives that still have able reserves."""
    combatants = _list(session.db.combatants)
    required = []
    was_complete = _text(session.db.status).upper() == "COMPLETE"
    for index, raw in enumerate(combatants):
        row = _dict(raw)
        if _text(row.get("controller_kind")).upper() != "HUMAN":
            continue
        pokemon = _dict(row.get("pokemon"))
        if _int(pokemon.get("hp_current"), 0) > 0:
            row["needs_switch"] = False
            combatants[index] = row
            continue
        actor = actor_from_dbref(row.get("actor_dbref"))
        if not actor:
            continue
        slots = able_party_slots(actor, exclude_slot=active_slot(actor))
        if not slots:
            row["needs_switch"] = False
            combatants[index] = row
            continue
        row["needs_switch"] = True
        row["available_switch_slots"] = slots
        combatants[index] = row
        pid = _text(row.get("controller_participant_id"))
        if pid:
            required.append(pid)
    session.db.combatants = combatants
    if required:
        if was_complete:
            session.db.turn = max(1, _int(session.db.turn, 1)) + 1
        session.db.status = "ACTIVE"
        session.db.phase = "SWITCH"
        session.db.outcome = ""
        session.db.winning_team = ""
        session.db.completed_at = None
        session.db.pending_orders = {}
        session.db.updated_at = int(time())
        session.append_log("FORCED_SWITCH", "Se requieren reemplazos antes de continuar.", participant_ids=required)
    return required


def _cleanup_completed_session(session):
    if _text(session.db.status).upper() != "COMPLETE":
        return
    for row in _list(session.db.participants):
        actor = actor_from_dbref(_dict(row).get("actor_dbref"))
        if actor:
            actor.db.last_pokerol_multiplayer_battle = public_session(session, actor)
            actor.db.pokerol_battle_session_id = None


def submit_multiplayer_order(actor, order):
    session = session_for_actor(actor)
    if not session:
        return {"accepted": False, "status": "NO_BATTLE_SESSION", "build": MULTI_RUNTIME_BUILD}
    if _text(session.db.status).upper() != "ACTIVE":
        return {"accepted": False, "status": "SESSION_NOT_ACTIVE", "build": MULTI_RUNTIME_BUILD}
    if _text(session.db.phase).upper() != "COMMAND":
        return {"accepted": False, "status": "NOT_COMMAND_PHASE", "phase": session.db.phase, "build": MULTI_RUNTIME_BUILD}
    pid = participant_id(actor)
    validation = validate_order(session.snapshot(), pid, order)
    if not validation.get("accepted"):
        return {**validation, "build": MULTI_RUNTIME_BUILD}
    pending = _dict(session.db.pending_orders)
    pending[pid] = _clone(validation.get("order"))
    session.write_orders(pending)
    participants = _list(session.db.participants)
    for index, raw in enumerate(participants):
        row = _dict(raw)
        if _text(row.get("participant_id")) == pid:
            row["submitted_turn"] = max(1, _int(session.db.turn, 1))
            participants[index] = row
            break
    session.write_participants(participants)
    session.append_log("ORDER_LOCKED", f"{actor.key} fija su orden.", participant_id=pid, turn=session.db.turn)
    required = human_order_requirements(session.snapshot())
    missing = [required_pid for required_pid in required if not _dict(pending.get(required_pid))]
    if missing:
        emit_session(session, event="ORDER_LOCKED")
        return {
            "accepted": True,
            "status": "ORDER_LOCKED_WAITING",
            "missing_participant_ids": missing,
            "session": public_session(session, actor),
            "build": MULTI_RUNTIME_BUILD,
        }
    result = resolve_locked_round(session.snapshot(), pending)
    if not result.get("accepted"):
        emit_session(session, event="STATE")
        return {**result, "build": MULTI_RUNTIME_BUILD}
    _write_state_to_session(session, _dict(result.get("state")))
    persisted = _persist_human_combatants(session)
    switches = _mark_forced_switches(session)
    event = "SWITCH_REQUIRED" if switches else ("END" if _text(session.db.status).upper() == "COMPLETE" else "ROUND")
    emit_session(session, event=event)
    if not switches:
        _cleanup_completed_session(session)
    return {
        "accepted": True,
        "status": "SWITCH_REQUIRED" if switches else result.get("status"),
        "required_switch_participant_ids": switches,
        "persisted": persisted,
        "session": public_session(session, actor),
        "build": MULTI_RUNTIME_BUILD,
    }


def submit_multiplayer_switch(actor, slot):
    session = session_for_actor(actor)
    if not session:
        return {"accepted": False, "status": "NO_BATTLE_SESSION", "build": MULTI_RUNTIME_BUILD}
    if _text(session.db.status).upper() != "ACTIVE" or _text(session.db.phase).upper() != "SWITCH":
        return {"accepted": False, "status": "SWITCH_NOT_REQUIRED", "build": MULTI_RUNTIME_BUILD}
    pid = participant_id(actor)
    combatants, index, row = _combatant_ref(session, pid)
    if index < 0 or not row or not bool(row.get("needs_switch")):
        return {"accepted": False, "status": "THIS_PLAYER_DOES_NOT_NEED_SWITCH", "build": MULTI_RUNTIME_BUILD}
    target_slot = _int(slot, -1)
    if target_slot not in [int(value) for value in _list(row.get("available_switch_slots"))]:
        return {"accepted": False, "status": "INVALID_SWITCH_SLOT", "valid_slots": _list(row.get("available_switch_slots")), "build": MULTI_RUNTIME_BUILD}
    profile = battle_profile_for_slot(actor, target_slot)
    if not profile or _int(profile.get("hp_current"), 0) <= 0:
        return {"accepted": False, "status": "POKEMON_NOT_ABLE", "build": MULTI_RUNTIME_BUILD}
    switched = set_active_slot(actor, target_slot, require_able=True)
    if not switched.get("accepted"):
        return {"accepted": False, "status": switched.get("status"), "build": MULTI_RUNTIME_BUILD}
    incoming = normalize_pokemon(profile, side=row.get("team") or "A")
    old_name = _text(_dict(row.get("pokemon")).get("name"))
    row["combatant_id"] = _text(incoming.get("entity_id"))
    row["pokemon"] = incoming
    row["active"] = True
    row["needs_switch"] = False
    row.pop("available_switch_slots", None)
    combatants[index] = row
    session.write_combatants(combatants)
    participants = _list(session.db.participants)
    for pindex, raw in enumerate(participants):
        participant = _dict(raw)
        if _text(participant.get("participant_id")) == pid:
            participant["active_entity_id"] = row["combatant_id"]
            participants[pindex] = participant
            break
    session.write_participants(participants)
    session.append_log("SWITCH", f"{actor.key} reemplaza a {old_name} por {incoming.get('name')}.", participant_id=pid, combatant_id=row["combatant_id"])
    remaining = [
        _text(_dict(raw).get("controller_participant_id"))
        for raw in _list(session.db.combatants)
        if bool(_dict(raw).get("needs_switch"))
    ]
    if not remaining:
        session.db.phase = "COMMAND"
        session.db.status = "ACTIVE"
        session.db.outcome = ""
        session.db.winning_team = ""
        session.db.pending_orders = {}
        session.db.updated_at = int(time())
        session.append_log("COMMAND", "Todos los reemplazos están listos. Continúa el turno compartido.")
        emit_session(session, event="ROUND")
        return {"accepted": True, "status": "ALL_SWITCHES_RESOLVED", "session": public_session(session, actor), "build": MULTI_RUNTIME_BUILD}
    emit_session(session, event="SWITCH_REQUIRED")
    return {"accepted": True, "status": "SWITCH_LOCKED_WAITING", "remaining_participant_ids": remaining, "session": public_session(session, actor), "build": MULTI_RUNTIME_BUILD}
