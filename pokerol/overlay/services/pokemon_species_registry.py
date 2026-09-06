"""Persistent species/move catalog populated by the POKEROL Pokémon Creator."""

from copy import deepcopy
from uuid import uuid4

from evennia import DefaultScript, create_script, search_script


REGISTRY_BUILD = "0.1.0-species-move-registry"
REGISTRY_KEY = "POKEROL_POKEMON_SPECIES_REGISTRY"


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


def get_species_registry(*, create=False):
    matches = list(search_script(REGISTRY_KEY))
    registry = matches[0] if matches else None
    if registry is None and create:
        registry = create_script(DefaultScript, key=REGISTRY_KEY, persistent=True, autostart=True)
    if registry is not None:
        if registry.db.species is None:
            registry.db.species = {}
        if registry.db.moves is None:
            registry.db.moves = {}
        if registry.db.meta is None:
            registry.db.meta = {}
        registry.db.build = REGISTRY_BUILD
    return registry


def validate_species_set(payload):
    data = _dict(payload)
    species_rows = [row for row in _list(data.get("pokemon")) if _dict(row)]
    move_rows = [row for row in _list(data.get("moves")) if _dict(row)]
    errors = []
    seen_species = set()
    seen_moves = set()

    for row in species_rows:
        item = _dict(row)
        species_id = _text(item.get("species_id"))
        if not species_id:
            errors.append("Pokémon sin species_id")
        elif species_id in seen_species:
            errors.append(f"species_id duplicado: {species_id}")
        seen_species.add(species_id)

    for row in move_rows:
        item = _dict(row)
        move_id = _text(item.get("move_id"))
        if not move_id:
            errors.append("Move sin move_id")
        elif move_id in seen_moves:
            errors.append(f"move_id duplicado: {move_id}")
        seen_moves.add(move_id)

    for row in species_rows:
        item = _dict(row)
        name = _text(item.get("species_name")) or _text(item.get("species_id"))
        refs = []
        refs.extend(_text(value) for value in _list(item.get("known_moves")) if _text(value))
        for learned in _list(item.get("level_up_moves")):
            learned = _dict(learned)
            move_id = _text(learned.get("move_id"))
            if move_id:
                refs.append(move_id)
        for move_id in refs:
            if move_id not in seen_moves:
                errors.append(f"{name}: move inexistente {move_id}")

    return {
        "accepted": not errors,
        "status": "SPECIES_SET_VALID" if not errors else "SPECIES_SET_INVALID",
        "species_count": len(species_rows),
        "move_count": len(move_rows),
        "errors": errors,
        "build": REGISTRY_BUILD,
    }


def import_species_set(payload):
    data = _dict(payload)
    validation = validate_species_set(data)
    if not validation.get("accepted"):
        return validation

    registry = get_species_registry(create=True)
    species_index = _dict(registry.db.species)
    move_index = _dict(registry.db.moves)
    created_species = []
    updated_species = []
    created_moves = []
    updated_moves = []

    for raw in _list(data.get("moves")):
        row = _clone(_dict(raw))
        move_id = _text(row.get("move_id"))
        target = updated_moves if move_id in move_index else created_moves
        move_index[move_id] = row
        target.append(move_id)

    for raw in _list(data.get("pokemon")):
        row = _clone(_dict(raw))
        species_id = _text(row.get("species_id"))
        target = updated_species if species_id in species_index else created_species
        species_index[species_id] = row
        target.append(species_id)

    registry.db.moves = move_index
    registry.db.species = species_index
    registry.db.meta = _clone(_dict(data.get("meta")))
    registry.db.build = REGISTRY_BUILD
    return {
        "accepted": True,
        "status": "SPECIES_SET_IMPORTED",
        "species_count": len(species_index),
        "move_count": len(move_index),
        "created_species": created_species,
        "updated_species": updated_species,
        "created_moves": created_moves,
        "updated_moves": updated_moves,
        "build": REGISTRY_BUILD,
    }


def registry_state():
    registry = get_species_registry(create=False)
    if not registry:
        return {"exists": False, "species_count": 0, "move_count": 0, "build": REGISTRY_BUILD}
    species = _dict(registry.db.species)
    moves = _dict(registry.db.moves)
    return {
        "exists": True,
        "species_count": len(species),
        "move_count": len(moves),
        "meta": _clone(_dict(registry.db.meta)),
        "build": REGISTRY_BUILD,
    }


def move_template(move_id):
    registry = get_species_registry(create=False)
    if not registry:
        return None
    row = _dict(_dict(registry.db.moves).get(_text(move_id)))
    return _clone(row) if row else None


def species_template(species_id):
    registry = get_species_registry(create=False)
    if not registry:
        return None
    row = _dict(_dict(registry.db.species).get(_text(species_id)))
    return _clone(row) if row else None


def _learned_move_ids(species, level):
    ids = []
    for move_id in _list(species.get("known_moves")):
        move_id = _text(move_id)
        if move_id and move_id not in ids:
            ids.append(move_id)
    learned = []
    for raw in _list(species.get("level_up_moves")):
        row = _dict(raw)
        move_id = _text(row.get("move_id"))
        move_level = max(1, _int(row.get("level"), 1))
        if move_id and move_level <= level:
            learned.append((move_level, move_id))
    learned.sort(key=lambda item: item[0])
    for _move_level, move_id in learned:
        if move_id in ids:
            ids.remove(move_id)
        ids.append(move_id)
    limit = max(0, _int(species.get("active_move_limit"), 4))
    return ids[-limit:] if limit else ids


def spawn_species_profile(species_id, *, level=None, wild=True):
    species = species_template(species_id)
    if not species:
        return None
    spawn_level = max(1, _int(level, species.get("level", 1)))
    moves = []
    for move_id in _learned_move_ids(species, spawn_level):
        move = move_template(move_id)
        if move:
            moves.append(move)

    profile = _clone(species)
    profile.pop("editor_id", None)
    profile["entity_id"] = f"WILD-{_text(species_id)}-{uuid4().hex[:10].upper()}" if wild else f"PKMN-{uuid4().hex[:12].upper()}"
    profile["level"] = spawn_level
    profile["moves"] = moves
    profile["resolved_moves"] = _clone(moves)
    profile["wild"] = bool(wild)
    profile["status"] = "OK"
    profile.pop("hp_current", None)
    profile.pop("hp_max", None)
    return profile
