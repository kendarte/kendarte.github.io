"""Persistent trainer bag authority for POKEROL."""

from copy import deepcopy


BAG_BUILD = "0.1.0-persistent-bag"
BALL_MULTIPLIERS = {
    "POKE_BALL": 1.0,
    "GREAT_BALL": 1.5,
    "ULTRA_BALL": 2.0,
    "MASTER_BALL": 99.0,
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
    bag.setdefault("version", 1)
    actor.db.pokerol_bag = bag
    return _clone(bag)


def bag_state(actor):
    bag = ensure_bag(actor)
    return {
        "build": BAG_BUILD,
        "items": _clone(_dict(bag.get("items"))),
    }


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
    if key not in BALL_MULTIPLIERS:
        return {"accepted": False, "status": "NOT_A_CAPTURE_BALL", "item_id": key, "build": BAG_BUILD}
    count = item_count(actor, key)
    if count <= 0:
        return {"accepted": False, "status": "ITEM_NOT_AVAILABLE", "item_id": key, "count": 0, "build": BAG_BUILD}
    return {
        "accepted": True,
        "status": "BALL_READY",
        "item_id": key,
        "count": count,
        "ball_multiplier": BALL_MULTIPLIERS[key],
        "guaranteed": key == "MASTER_BALL",
        "build": BAG_BUILD,
    }
