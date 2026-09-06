"""Persistent TM/HM teaching authority for POKEROL.

Machines are teaching sources only. The learned move keeps all battle/world
capabilities from the species registry; HM/TM status never owns world physics.
"""

from copy import deepcopy

from services.pokemon_bag_engine import consume_item, item_count
from services.pokemon_party_engine import battle_profile_for_slot, set_party_slot_profile
from services.pokemon_progression_engine import can_learn_machine
from services.pokemon_species_registry import get_species_registry


MACHINE_BUILD = "0.1.0-persistent-machines"


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


def _clone(value):
    return deepcopy(value)


def _text(value):
    return str(value or "").strip()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _machine_packet(move):
    move = _dict(move)
    machine = _dict(move.get("machine"))
    return {
        "kind": _text(machine.get("kind")).upper(),
        "machine_id": _text(machine.get("id")).upper(),
        "reusable": bool(machine.get("reusable", False)),
        "move_id": _text(move.get("move_id")),
        "move_name": _text(move.get("name")) or _text(move.get("move_id")),
    }


def machine_move(machine_id):
    wanted = _text(machine_id).upper()
    if not wanted:
        return None
    registry = get_species_registry(create=False)
    if not registry:
        return None
    for raw in _dict(registry.db.moves).values():
        move = _dict(raw)
        packet = _machine_packet(move)
        if packet["machine_id"] == wanted:
            result = _clone(move)
            result["machine_resolved"] = packet
            return result
    return None


def machine_state(machine_id):
    move = machine_move(machine_id)
    if not move:
        return {"exists": False, "machine_id": _text(machine_id).upper(), "build": MACHINE_BUILD}
    packet = _machine_packet(move)
    return {"exists": True, **packet, "build": MACHINE_BUILD}


def _active_moves(profile):
    rows = []
    for raw in _list(_dict(profile).get("moves") or _dict(profile).get("resolved_moves")):
        move = _clone(_dict(raw))
        if not _text(move.get("move_id")):
            continue
        pp_max = max(0, _int(move.get("pp_max"), move.get("pp", 20)))
        move["pp"] = pp_max
        move["pp_max"] = pp_max
        move["pp_current"] = max(0, min(pp_max, _int(move.get("pp_current"), pp_max)))
        rows.append(move)
    return rows


def _hydrated_machine_move(move):
    row = _clone(_dict(move))
    pp_max = max(0, _int(row.get("pp_max"), row.get("pp", 20)))
    row["pp"] = pp_max
    row["pp_max"] = pp_max
    row["pp_current"] = pp_max
    return row


def teach_party_machine(actor, slot, machine_id, *, replace_move_id=""):
    """Teach one machine move to an owned Pokémon and persist the result.

    known_moves is the long-term learned library. moves/resolved_moves is the
    active battle loadout. A full loadout does not erase old knowledge: teaching
    succeeds into known_moves and reports that a loadout choice is still needed.
    """
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": MACHINE_BUILD}
    target_slot = _int(slot, -1)
    pokemon = battle_profile_for_slot(actor, target_slot)
    if not pokemon:
        return {"accepted": False, "status": "INVALID_PARTY_SLOT", "slot": target_slot, "build": MACHINE_BUILD}

    wanted = _text(machine_id).upper()
    move = machine_move(wanted)
    if not move:
        return {"accepted": False, "status": "MACHINE_NOT_IN_REGISTRY", "machine_id": wanted, "build": MACHINE_BUILD}
    source = _machine_packet(move)
    if source["kind"] not in {"TM", "HM"}:
        return {"accepted": False, "status": "UNSUPPORTED_MACHINE_KIND", **source, "build": MACHINE_BUILD}
    if item_count(actor, wanted) <= 0:
        return {"accepted": False, "status": "MACHINE_NOT_OWNED", "machine_id": wanted, "build": MACHINE_BUILD}

    gate = can_learn_machine(pokemon, move)
    if not gate.get("allowed"):
        return {"accepted": False, "status": gate.get("status") or "MACHINE_INCOMPATIBLE", **source, "slot": target_slot, "build": MACHINE_BUILD}

    profile = _clone(_dict(pokemon))
    move_id = source["move_id"]
    known = []
    for value in _list(profile.get("known_moves")):
        value = _text(value)
        if value and value not in known:
            known.append(value)
    active = _active_moves(profile)
    active_ids = [_text(row.get("move_id")) for row in active]
    already_known = move_id in known or move_id in active_ids

    if move_id not in known:
        known.append(move_id)
    profile["known_moves"] = known

    equipped = move_id in active_ids
    replaced = ""
    limit = max(1, _int(profile.get("active_move_limit"), 4))
    if not equipped and len(active) < limit:
        active.append(_hydrated_machine_move(move))
        equipped = True
    elif not equipped and replace_move_id:
        wanted_replace = _text(replace_move_id)
        for index, current in enumerate(active):
            if _text(current.get("move_id")) == wanted_replace:
                replaced = wanted_replace
                active[index] = _hydrated_machine_move(move)
                equipped = True
                break
        if not equipped:
            return {
                "accepted": False,
                "status": "REPLACE_MOVE_NOT_ACTIVE",
                "machine_id": wanted,
                "move_id": move_id,
                "replace_move_id": wanted_replace,
                "active_move_ids": active_ids,
                "build": MACHINE_BUILD,
            }

    profile["moves"] = active
    profile["resolved_moves"] = _clone(active)
    stored = set_party_slot_profile(actor, target_slot, profile)
    if not stored.get("accepted"):
        return {"accepted": False, "status": stored.get("status"), "machine_id": wanted, "build": MACHINE_BUILD}

    consumed = None
    if not source["reusable"] and not already_known:
        consumed = consume_item(actor, wanted, 1)
        if not consumed.get("accepted"):
            return {"accepted": False, "status": consumed.get("status"), "machine_id": wanted, "build": MACHINE_BUILD}

    needs_loadout_choice = not equipped
    status = "MACHINE_ALREADY_KNOWN" if already_known else ("MACHINE_LEARNED_LOADOUT_FULL" if needs_loadout_choice else "MACHINE_LEARNED")
    return {
        "accepted": True,
        "status": status,
        "machine_id": wanted,
        "kind": source["kind"],
        "reusable": source["reusable"],
        "move_id": move_id,
        "move_name": source["move_name"],
        "slot": target_slot,
        "learned": not already_known,
        "already_known": already_known,
        "equipped": equipped,
        "replaced_move_id": replaced or None,
        "needs_loadout_choice": needs_loadout_choice,
        "active_move_ids": [_text(row.get("move_id")) for row in active],
        "consumed": _clone(consumed),
        "build": MACHINE_BUILD,
    }
