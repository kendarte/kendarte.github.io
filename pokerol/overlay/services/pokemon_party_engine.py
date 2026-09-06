"""Persistent trainer party/storage authority for POKEROL."""

from copy import deepcopy
from uuid import uuid4


PARTY_BUILD = "0.1.0-persistent-party"
PARTY_LIMIT = 6


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


def _derived_hp(profile):
    level = max(1, _int(profile.get("level"), 1))
    base = _dict(profile.get("base_stats"))
    return max(1, int((2 * max(1, _int(base.get("HP"), 40)) * level) / 100) + level + 10)


def normalize_owned_pokemon(profile, *, owner_id=""):
    p = _clone(_dict(profile))
    instance_id = _text(p.get("instance_id") or p.get("entity_id")) or f"POKEMON-{uuid4().hex[:14].upper()}"
    p["instance_id"] = instance_id
    p["entity_id"] = instance_id
    p["owner_id"] = _text(owner_id)
    p["wild"] = False
    p["species_id"] = _text(p.get("species_id"))
    p["species_name"] = _text(p.get("species_name") or p.get("name")) or "Pokémon"
    p["nickname"] = _text(p.get("nickname"))
    p["level"] = max(1, _int(p.get("level"), 1))
    hp_max = max(1, _int(p.get("hp_max"), _derived_hp(p)))
    p["hp_max"] = hp_max
    p["hp_current"] = max(0, min(hp_max, _int(p.get("hp_current"), hp_max)))
    p["status"] = _text(p.get("status")).upper() or "OK"
    p.setdefault("experience", 0)
    p.setdefault("bond", 0)
    p.setdefault("trust", 0)
    p.setdefault("captured_at", None)
    return p


def _owner_id(actor):
    if not actor:
        return ""
    explicit = _text(getattr(actor.db, "player_id", ""))
    return explicit or f"PLAYER:DBREF:{int(actor.id)}"


def _party(actor):
    return [normalize_owned_pokemon(row, owner_id=_owner_id(actor)) for row in _list(getattr(actor.db, "pokerol_party", [])) if _dict(row)] if actor else []


def _storage(actor):
    return [normalize_owned_pokemon(row, owner_id=_owner_id(actor)) for row in _list(getattr(actor.db, "pokerol_pc_storage", [])) if _dict(row)] if actor else []


def _write_party(actor, rows):
    actor.db.pokerol_party = [_clone(row) for row in rows]


def _write_storage(actor, rows):
    actor.db.pokerol_pc_storage = [_clone(row) for row in rows]


def active_slot(actor):
    party = _party(actor)
    if not party:
        return -1
    raw = _int(getattr(actor.db, "pokerol_active_slot", 0), 0)
    if raw < 0 or raw >= len(party):
        raw = 0
        actor.db.pokerol_active_slot = 0
    return raw


def active_pokemon(actor):
    party = _party(actor)
    slot = active_slot(actor)
    if slot < 0 or slot >= len(party):
        return None
    p = _clone(party[slot])
    p["party_slot"] = slot
    return p


def party_state(actor):
    party = _party(actor)
    slot = active_slot(actor)
    public = []
    for index, row in enumerate(party):
        item = _clone(row)
        item["party_slot"] = index
        item["active"] = index == slot
        public.append(item)
    return {
        "build": PARTY_BUILD,
        "limit": PARTY_LIMIT,
        "active_slot": slot,
        "party": public,
        "storage_count": len(_storage(actor)),
    }


def add_pokemon(actor, profile, *, prefer_party=True):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": PARTY_BUILD}
    owned = normalize_owned_pokemon(profile, owner_id=_owner_id(actor))
    party = _party(actor)
    storage = _storage(actor)
    if prefer_party and len(party) < PARTY_LIMIT:
        party.append(owned)
        _write_party(actor, party)
        if len(party) == 1:
            actor.db.pokerol_active_slot = 0
        return {"accepted": True, "status": "ADDED_TO_PARTY", "pokemon": _clone(owned), "slot": len(party) - 1, "build": PARTY_BUILD}
    storage.append(owned)
    _write_storage(actor, storage)
    return {"accepted": True, "status": "SENT_TO_STORAGE", "pokemon": _clone(owned), "storage_index": len(storage) - 1, "build": PARTY_BUILD}


def set_active_slot(actor, slot, *, require_able=True):
    party = _party(actor)
    index = _int(slot, -1)
    if index < 0 or index >= len(party):
        return {"accepted": False, "status": "INVALID_PARTY_SLOT", "build": PARTY_BUILD}
    if require_able and _int(party[index].get("hp_current"), 0) <= 0:
        return {"accepted": False, "status": "POKEMON_FAINTED", "build": PARTY_BUILD}
    actor.db.pokerol_active_slot = index
    return {"accepted": True, "status": "ACTIVE_SLOT_SET", "slot": index, "pokemon": _clone(party[index]), "build": PARTY_BUILD}


def battle_profile_for_slot(actor, slot):
    party = _party(actor)
    index = _int(slot, -1)
    if index < 0 or index >= len(party):
        return None
    p = _clone(party[index])
    p["party_slot"] = index
    return p


def update_owned_from_battle(actor, battle_pokemon):
    """Persist HP/status/level/moves for the exact owned instance represented in battle."""
    if not actor:
        return False
    battle = _dict(battle_pokemon)
    entity_id = _text(battle.get("entity_id"))
    if not entity_id:
        return False
    party = _party(actor)
    changed = False
    for index, current in enumerate(party):
        if _text(current.get("entity_id")) != entity_id:
            continue
        next_row = _clone(current)
        for key in ("level", "hp_max", "hp_current", "status"):
            if key in battle:
                next_row[key] = _clone(battle[key])
        if battle.get("moves"):
            next_row["moves"] = _clone(battle.get("moves"))
            next_row["resolved_moves"] = _clone(battle.get("moves"))
        party[index] = next_row
        changed = True
        break
    if changed:
        _write_party(actor, party)
    return changed


def able_party_slots(actor, *, exclude_slot=None):
    party = _party(actor)
    output = []
    for index, row in enumerate(party):
        if exclude_slot is not None and index == _int(exclude_slot, -99):
            continue
        if _int(row.get("hp_current"), 0) > 0:
            output.append(index)
    return output
