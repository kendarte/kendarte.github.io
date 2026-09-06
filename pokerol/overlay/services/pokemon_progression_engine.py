"""POKEROL Pokémon level/machine learning helpers.

Pure data helpers: they return updated profile copies and never write to Evennia.
"""

from copy import deepcopy


def _dict(value):
    return dict(value or {}) if hasattr(value or {}, "items") else {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _id(value):
    return str(value or "").strip()


def _catalog_by_id(move_catalog):
    return {
        _id(row.get("move_id")): _dict(row)
        for row in _list(move_catalog)
        if _id(_dict(row).get("move_id"))
    }


def level_up_moves_between(pokemon, old_level, new_level):
    rows = []
    for row in _list(_dict(pokemon).get("level_up_moves")):
        row = _dict(row)
        try:
            level = int(row.get("level"))
        except (TypeError, ValueError):
            continue
        move_id = _id(row.get("move_id"))
        if move_id and int(old_level) < level <= int(new_level):
            rows.append({"level": level, "move_id": move_id})
    rows.sort(key=lambda item: (item["level"], item["move_id"]))
    return rows


def set_level(pokemon, new_level, move_catalog=None, auto_learn=True):
    profile = deepcopy(_dict(pokemon))
    old_level = int(profile.get("level") or 1)
    new_level = max(1, int(new_level))
    profile["level"] = new_level

    learned = []
    catalog = _catalog_by_id(move_catalog or [])
    known = list(dict.fromkeys(_id(v) for v in _list(profile.get("known_moves")) if _id(v)))

    if auto_learn and new_level > old_level:
        for row in level_up_moves_between(profile, old_level, new_level):
            move_id = row["move_id"]
            if catalog and move_id not in catalog:
                continue
            if move_id not in known:
                known.append(move_id)
                learned.append({
                    "move_id": move_id,
                    "source": "LEVEL",
                    "level": row["level"],
                })

    profile["known_moves"] = known
    return {
        "status": "LEVEL_UPDATED",
        "old_level": old_level,
        "new_level": new_level,
        "learned": learned,
        "pokemon": profile,
    }


def _machine_kind_and_id(move):
    machine = _dict(_dict(move).get("machine"))
    return (
        _id(machine.get("kind")).upper() or "NONE",
        _id(machine.get("id")),
    )


def can_learn_machine(pokemon, move):
    pokemon = _dict(pokemon)
    move = _dict(move)
    kind, machine_id = _machine_kind_and_id(move)
    if kind not in {"TM", "HM", "TUTOR"} or not machine_id:
        return {
            "allowed": False,
            "status": "MOVE_HAS_NO_MACHINE_SOURCE",
            "kind": kind,
            "machine_id": machine_id,
        }

    if kind == "TM":
        compatible = {_id(v) for v in _list(pokemon.get("tm_compatibility"))}
    elif kind == "HM":
        compatible = {_id(v) for v in _list(pokemon.get("hm_compatibility"))}
    else:
        compatible = {_id(v) for v in _list(pokemon.get("tutor_compatibility"))}

    allowed = machine_id in compatible or _id(move.get("move_id")) in compatible
    return {
        "allowed": allowed,
        "status": "MACHINE_COMPATIBLE" if allowed else "MACHINE_INCOMPATIBLE",
        "kind": kind,
        "machine_id": machine_id,
        "move_id": _id(move.get("move_id")),
    }


def teach_machine_move(pokemon, move):
    gate = can_learn_machine(pokemon, move)
    if not gate["allowed"]:
        return {**gate, "learned": False, "pokemon": deepcopy(_dict(pokemon))}

    profile = deepcopy(_dict(pokemon))
    known = list(dict.fromkeys(_id(v) for v in _list(profile.get("known_moves")) if _id(v)))
    move_id = _id(move.get("move_id"))
    already_known = move_id in known
    if not already_known:
        known.append(move_id)
    profile["known_moves"] = known

    return {
        **gate,
        "learned": not already_known,
        "already_known": already_known,
        "pokemon": profile,
    }
