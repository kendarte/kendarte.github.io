"""Persistent trainer bag authority and battle-item rules for POKEROL."""

from copy import deepcopy


BAG_BUILD = "0.2.0-battle-items"
BALL_MULTIPLIERS = {
    "POKE_BALL": 1.0,
    "GREAT_BALL": 1.5,
    "ULTRA_BALL": 2.0,
}
RESERVED_CAPTURE_ITEMS = {"MASTER_BALL"}

ITEM_PROFILES = {
    "POKE_BALL": {"kind": "CAPTURE", "battle_usable": True, "label": "POKé BALL"},
    "GREAT_BALL": {"kind": "CAPTURE", "battle_usable": True, "label": "GREAT BALL"},
    "ULTRA_BALL": {"kind": "CAPTURE", "battle_usable": True, "label": "ULTRA BALL"},
    "MASTER_BALL": {"kind": "CAPTURE_RESERVED", "battle_usable": False, "label": "MASTER BALL"},
    "POTION": {"kind": "HEAL", "amount": 20, "battle_usable": True, "label": "POTION"},
    "SUPER_POTION": {"kind": "HEAL", "amount": 50, "battle_usable": True, "label": "SUPER POTION"},
    "HYPER_POTION": {"kind": "HEAL", "amount": 120, "battle_usable": True, "label": "HYPER POTION"},
    "ANTIDOTE": {"kind": "CURE", "status": "POISON", "battle_usable": True, "label": "ANTIDOTE"},
    "BURN_HEAL": {"kind": "CURE", "status": "BURN", "battle_usable": True, "label": "BURN HEAL"},
    "PARALYZE_HEAL": {"kind": "CURE", "status": "PARALYSIS", "battle_usable": True, "label": "PARALYZE HEAL"},
    "AWAKENING": {"kind": "CURE", "status": "SLEEP", "battle_usable": True, "label": "AWAKENING"},
    "ICE_HEAL": {"kind": "CURE", "status": "FREEZE", "battle_usable": True, "label": "ICE HEAL"},
    "FULL_HEAL": {"kind": "CURE_ALL", "battle_usable": True, "label": "FULL HEAL"},
    "REVIVE": {"kind": "REVIVE", "fraction": 0.5, "battle_usable": True, "label": "REVIVE"},
    "ETHER": {"kind": "PP", "amount": 10, "battle_usable": True, "requires_move": True, "label": "ETHER"},
    "MAX_ETHER": {"kind": "PP_FULL", "battle_usable": True, "requires_move": True, "label": "MAX ETHER"},
}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _clone(value):
    return deepcopy(value)


def _text(value):
    return str(value or "").strip().upper()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def ensure_bag(actor):
    if not actor:
        return {}
    bag = _dict(getattr(actor.db, "pokerol_bag", {}))
    items = _dict(bag.get("items"))
    bag["items"] = {str(key).upper(): max(0, _int(value, 0)) for key, value in items.items()}
    bag.setdefault("version", 2)
    actor.db.pokerol_bag = bag
    return _clone(bag)


def item_profile(item_id):
    row = ITEM_PROFILES.get(_text(item_id))
    return _clone(row) if row else None


def bag_state(actor):
    bag = ensure_bag(actor)
    items = _clone(_dict(bag.get("items")))
    profiles = {key: _clone(ITEM_PROFILES.get(key, {"kind": "UNKNOWN", "battle_usable": False, "label": key.replace("_", " ")})) for key in items.keys()}
    return {"build": BAG_BUILD, "items": items, "profiles": profiles}


def item_count(actor, item_id):
    bag = ensure_bag(actor)
    return max(0, _int(_dict(bag.get("items")).get(_text(item_id)), 0))


def add_item(actor, item_id, amount=1):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": BAG_BUILD}
    key = _text(item_id)
    qty = _int(amount, 0)
    if not key or qty == 0:
        return {"accepted": False, "status": "INVALID_ITEM_DELTA", "build": BAG_BUILD}
    bag = ensure_bag(actor)
    items = _dict(bag.get("items"))
    items[key] = max(0, _int(items.get(key), 0) + qty)
    bag["items"] = items
    actor.db.pokerol_bag = bag
    return {"accepted": True, "status": "ITEM_UPDATED", "item_id": key, "count": items[key], "build": BAG_BUILD}


def consume_item(actor, item_id, amount=1):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": BAG_BUILD}
    key = _text(item_id)
    qty = max(1, _int(amount, 1))
    bag = ensure_bag(actor)
    items = _dict(bag.get("items"))
    current = max(0, _int(items.get(key), 0))
    if current < qty:
        return {"accepted": False, "status": "ITEM_NOT_AVAILABLE", "item_id": key, "count": current, "build": BAG_BUILD}
    items[key] = current - qty
    bag["items"] = items
    actor.db.pokerol_bag = bag
    return {"accepted": True, "status": "ITEM_CONSUMED", "item_id": key, "count": items[key], "build": BAG_BUILD}


def capture_ball_profile(actor, item_id):
    key = _text(item_id) or "POKE_BALL"
    if key in RESERVED_CAPTURE_ITEMS:
        return {"accepted": False, "status": "SPECIAL_CAPTURE_RULE_NOT_IMPLEMENTED", "item_id": key, "build": BAG_BUILD}
    if key not in BALL_MULTIPLIERS:
        return {"accepted": False, "status": "NOT_A_CAPTURE_BALL", "item_id": key, "build": BAG_BUILD}
    count = item_count(actor, key)
    if count <= 0:
        return {"accepted": False, "status": "ITEM_NOT_AVAILABLE", "item_id": key, "count": 0, "build": BAG_BUILD}
    return {"accepted": True, "status": "BALL_READY", "item_id": key, "count": count, "ball_multiplier": BALL_MULTIPLIERS[key], "guaranteed": False, "build": BAG_BUILD}


def _move_ref(pokemon, move_id):
    wanted = _text(move_id)
    moves = pokemon.get("moves") if isinstance(pokemon, dict) else None
    for move in moves if isinstance(moves, list) else []:
        if isinstance(move, dict) and _text(move.get("move_id")) == wanted:
            return move
    return None


def apply_battle_item(item_id, pokemon, *, move_id=""):
    """Pure item effect. Does not consume inventory; runtime consumes only after success."""
    key = _text(item_id)
    profile = item_profile(key)
    if not profile:
        return {"accepted": False, "status": "UNKNOWN_ITEM", "item_id": key, "build": BAG_BUILD}
    if not profile.get("battle_usable") or profile.get("kind") in {"CAPTURE", "CAPTURE_RESERVED"}:
        return {"accepted": False, "status": "ITEM_NOT_USABLE_AS_SUPPORT", "item_id": key, "build": BAG_BUILD}
    target = _clone(_dict(pokemon))
    if not target:
        return {"accepted": False, "status": "NO_ITEM_TARGET", "item_id": key, "build": BAG_BUILD}

    name = str(target.get("nickname") or target.get("species_name") or target.get("name") or "Pokémon")
    kind = profile.get("kind")
    hp = max(0, _int(target.get("hp_current"), 0))
    hp_max = max(1, _int(target.get("hp_max"), 1))

    if kind == "HEAL":
        if hp <= 0:
            return {"accepted": False, "status": "TARGET_FAINTED", "item_id": key, "build": BAG_BUILD}
        if hp >= hp_max:
            return {"accepted": False, "status": "HP_ALREADY_FULL", "item_id": key, "build": BAG_BUILD}
        amount = min(max(1, _int(profile.get("amount"), 1)), hp_max - hp)
        target["hp_current"] = hp + amount
        text = f"{name} recupera {amount} HP."
    elif kind == "CURE":
        wanted = _text(profile.get("status"))
        current = _text(target.get("status")) or "OK"
        if current != wanted:
            return {"accepted": False, "status": "STATUS_NOT_PRESENT", "item_id": key, "required_status": wanted, "current_status": current, "build": BAG_BUILD}
        target["status"] = "OK"
        target["status_turns"] = 0
        text = f"{name} se recupera de {wanted}."
    elif kind == "CURE_ALL":
        current = _text(target.get("status")) or "OK"
        if current == "OK":
            return {"accepted": False, "status": "NO_STATUS_TO_CURE", "item_id": key, "build": BAG_BUILD}
        target["status"] = "OK"
        target["status_turns"] = 0
        text = f"{name} queda libre de problemas de estado."
    elif kind == "REVIVE":
        if hp > 0:
            return {"accepted": False, "status": "TARGET_NOT_FAINTED", "item_id": key, "build": BAG_BUILD}
        restored = max(1, int(hp_max * float(profile.get("fraction", 0.5))))
        target["hp_current"] = restored
        target["status"] = "OK"
        target["status_turns"] = 0
        text = f"{name} vuelve con {restored} HP."
    elif kind in {"PP", "PP_FULL"}:
        move = _move_ref(target, move_id)
        if not move:
            return {"accepted": False, "status": "MOVE_NOT_FOUND_FOR_ITEM", "item_id": key, "move_id": _text(move_id), "build": BAG_BUILD}
        pp_max = max(0, _int(move.get("pp_max"), move.get("pp", 0)))
        pp_current = max(0, min(pp_max, _int(move.get("pp_current"), pp_max)))
        if pp_current >= pp_max:
            return {"accepted": False, "status": "PP_ALREADY_FULL", "item_id": key, "move_id": move.get("move_id"), "build": BAG_BUILD}
        restored = pp_max - pp_current if kind == "PP_FULL" else min(max(1, _int(profile.get("amount"), 10)), pp_max - pp_current)
        move["pp_current"] = pp_current + restored
        text = f"{move.get('name') or move.get('move_id')} recupera {restored} PP."
    else:
        return {"accepted": False, "status": "ITEM_EFFECT_NOT_IMPLEMENTED", "item_id": key, "build": BAG_BUILD}

    return {"accepted": True, "status": "ITEM_EFFECT_APPLIED", "item_id": key, "pokemon": target, "text": text, "build": BAG_BUILD}
