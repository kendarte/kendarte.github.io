"""Persistent Fakemon/Skill catalog for the POKEROL world-combat contract.

Legacy Pokemon Creator payloads remain readable. New rows are normalized to the
PKM -> Skill -> Environment -> Resolver -> Narrative/Tsubasa schema before they
become authoritative registry data.
"""

from copy import deepcopy
from uuid import uuid4

from evennia import DefaultScript, create_script, search_script

from services.pokemon_move_capability_engine import (
    RANGE_TYPES,
    TRAJECTORY_TYPES,
    canonical_range,
    canonical_trajectory,
)

REGISTRY_BUILD = "0.2.0-fakemon-skill-world-narrative-schema"
REGISTRY_KEY = "POKEROL_POKEMON_SPECIES_REGISTRY"
SCHEMA_NAME = "PKM-SKILL-ENV-NARRATIVE-v2"
WORLD_STATS = ("FUE", "AGI", "COO", "INT", "PER", "PSI")
BASE_STATS = ("HP", "ATK", "DEF", "SPA", "SPD", "SPE")
BODY_STYLES = {"BIPED", "QUADRUPED", "SERPENT", "FLYING", "FLOATING", "AQUATIC", "INSECT", "AMORPHOUS"}
SIZE_CLASSES = {"TINY", "SMALL", "MEDIUM", "LARGE", "HUGE"}
RESOLUTION_MODES = {"DIRECT", "CONFRONT", "ACCUMULATE", "SYNCHRONIZE"}
POSE_FAMILIES = {"NEUTRAL", "ATTACK_PHYSICAL", "ATTACK_SPECIAL", "CHARGE", "DEFEND", "DODGE", "MOVEMENT", "STATUS"}
SHOT_POSES = ("neutral", "attack_physical", "attack_special", "charge", "hit", "defend", "dodge", "ko")


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


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _rating(value, default=3):
    return max(0, min(5, _int(value, default)))


def _strings(value):
    output = []
    for raw in _list(value):
        item = _text(raw)
        if item and item not in output:
            output.append(item)
    return output


def _pose(raw=None):
    row = _dict(raw)
    return {
        "image": _text(row.get("image") or row.get("src")),
        "video": _text(row.get("video")),
        "scale": max(0.25, min(4.0, _float(row.get("scale"), 1.0))),
        "anchor_x": max(0.0, min(100.0, _float(row.get("anchor_x"), 50.0))),
        "anchor_y": max(0.0, min(100.0, _float(row.get("anchor_y"), 100.0))),
    }


def normalize_move_template(raw):
    row = _clone(_dict(raw))
    combat = _dict(row.get("combat_profile"))
    resolution = _dict(row.get("resolution"))
    requirements = _dict(row.get("requirements"))
    machine = _dict(row.get("machine"))
    visual = _dict(row.get("visual"))
    cinematic = {**_dict(row.get("cinematic_media")), **_dict(visual.get("cinematic_media"))}

    trajectory = _text(row.get("trajectory")).upper()
    if trajectory not in TRAJECTORY_TYPES:
        trajectory = canonical_trajectory(row)
    range_band = _text(row.get("range") or row.get("range_band")).upper()
    if range_band not in RANGE_TYPES:
        range_band = canonical_range(row)

    modes = [value.upper() for value in _strings(resolution.get("modes"))]
    modes = [value for value in modes if value in RESOLUTION_MODES] or ["CONFRONT"]
    default_stat = _text(resolution.get("default_stat") or "COO").upper()
    if default_stat not in WORLD_STATS:
        default_stat = "COO"

    pose_family = _text(visual.get("pose_family")).upper()
    if pose_family not in POSE_FAMILIES:
        damage_class = _text(row.get("damage_class") or "PHYSICAL").upper()
        pose_family = "ATTACK_SPECIAL" if damage_class == "SPECIAL" else "STATUS" if damage_class == "STATUS" else "ATTACK_PHYSICAL"

    row.update({
        "move_id": _text(row.get("move_id")),
        "name": _text(row.get("name")) or _text(row.get("move_id")) or "Skill",
        "pokemon_type": _text(row.get("pokemon_type") or row.get("type") or "Normal"),
        "category": _text(row.get("category") or "ATTACK").upper(),
        "damage_class": _text(row.get("damage_class") or "PHYSICAL").upper(),
        "power": max(0, _int(row.get("power"), 0)),
        "accuracy": max(1, min(100, _int(row.get("accuracy"), 100))),
        "pp": max(0, _int(row.get("pp"), 20)),
        "priority": max(-10, min(10, _int(row.get("priority"), 0))),
        "description": _text(row.get("description")),
        "combat_profile": {
            "power": _rating(combat.get("power"), 3 if _int(row.get("power"), 0) else 0),
            "control": _rating(combat.get("control"), 3),
            "speed": _rating(combat.get("speed"), 3),
        },
        "trajectory": trajectory,
        "delivery": _text(row.get("delivery") or trajectory).upper(),
        "range": range_band,
        "area": _text(row.get("area") or "SINGLE").upper(),
        "target_mode": _text(row.get("target_mode") or "SINGLE").upper(),
        "defense_profile": _text(row.get("defense_profile") or "NONE").upper(),
        "properties": _strings(row.get("properties") or row.get("combat_tags")),
        "world_enabled": bool(row.get("world_enabled", False)),
        "world_effects": _strings(row.get("world_effects")),
        "materials": _strings(row.get("materials")),
        "requirements": {
            "line_of_sight": bool(requirements.get("line_of_sight", False)),
            "ground_contact": bool(requirements.get("ground_contact", False)),
            "requires_water": bool(requirements.get("requires_water", False)),
            "requires_airspace": bool(requirements.get("requires_airspace", False)),
            "requires_target": bool(requirements.get("requires_target", False)),
        },
        "resolution": {
            "default_stat": default_stat,
            "modes": modes,
            "max_checks": max(0, min(2, _int(resolution.get("max_checks"), 1))),
            "difficulty_bias": max(-5, min(5, _int(resolution.get("difficulty_bias"), 0))),
        },
        "effect_rules": [_clone(_dict(value)) for value in _list(row.get("effect_rules")) if _dict(value)],
        "world_rules": [_clone(_dict(value)) for value in _list(row.get("world_rules")) if _dict(value)],
        "machine": {"kind": _text(machine.get("kind") or "NONE").upper(), "id": _text(machine.get("id")), "reusable": bool(machine.get("reusable", False))},
        "visual": {
            "pose_family": pose_family,
            "effect_asset": _text(visual.get("effect_asset")),
            "impact_asset": _text(visual.get("impact_asset")),
            "sound_asset": _text(visual.get("sound_asset")),
            "cinematic_media": {"type": _text(cinematic.get("type")).lower(), "src": _text(cinematic.get("src"))},
        },
        "cinematic_media": {"type": _text(cinematic.get("type")).lower(), "src": _text(cinematic.get("src"))},
        "tags": _strings(row.get("tags")),
    })
    return row


def normalize_species_template(raw):
    row = _clone(_dict(raw))
    base = _dict(row.get("base_stats"))
    world = _dict(row.get("world_stats"))
    body = _dict(row.get("body_profile"))
    narrative = _dict(row.get("narrative_profile"))
    legacy_sprite = _dict(row.get("sprite"))
    visuals = _dict(row.get("combat_visuals"))
    battle = {**legacy_sprite, **_dict(visuals.get("battle"))}
    shots_raw = _dict(visuals.get("shots"))

    body_style = _text(body.get("style") or row.get("body_style") or "BIPED").upper()
    if body_style not in BODY_STYLES:
        body_style = "BIPED"
    size_class = _text(body.get("size_class") or row.get("size_class") or "SMALL").upper()
    if size_class not in SIZE_CLASSES:
        size_class = "SMALL"

    sprite = {
        "front": _text(battle.get("front")), "back": _text(battle.get("back")),
        "icon": _text(battle.get("icon")), "portrait": _text(battle.get("portrait")),
        "scale": max(0.25, min(4.0, _float(battle.get("scale"), 1.25))),
    }
    shots = {name: _pose(shots_raw.get(name)) for name in SHOT_POSES}

    row.update({
        "species_id": _text(row.get("species_id")),
        "species_name": _text(row.get("species_name") or row.get("name")) or _text(row.get("species_id")) or "Fakemon",
        "dex_number": max(0, _int(row.get("dex_number"), 0)),
        "form": _text(row.get("form")),
        "types": _strings(row.get("types")) or ["Normal"],
        "description": _text(row.get("description")),
        "temperament": _text(row.get("temperament")),
        "level": max(1, min(100, _int(row.get("level"), 5))),
        "experience": max(0, _int(row.get("experience"), 0)),
        "growth_rate": _text(row.get("growth_rate") or "MEDIUM").upper(),
        "base_stats": {key: max(1, min(255, _int(base.get(key), 45))) for key in BASE_STATS},
        "world_stats": {key: max(0, min(10, _int(world.get(key), 2))) for key in WORLD_STATS},
        "body_profile": {"style": body_style, "size_class": size_class, "height_m": max(0.01, _float(body.get("height_m"), 0.7)), "weight_kg": max(0.01, _float(body.get("weight_kg"), 10.0))},
        "body_style": body_style,
        "size_class": size_class,
        "locomotion": _strings(row.get("locomotion")) or ["WALK"],
        "senses": _strings(row.get("senses")) or ["VISION"],
        "body_tags": _strings(row.get("body_tags")),
        "environment_tags": _strings(row.get("environment_tags")),
        "narrative_profile": {
            "personality_tags": _strings(narrative.get("personality_tags")),
            "behavior_tags": _strings(narrative.get("behavior_tags")),
            "combat_instincts": _strings(narrative.get("combat_instincts")),
            "vocalization": _text(narrative.get("vocalization")),
            "dm_notes": _text(narrative.get("dm_notes")),
        },
        "known_moves": _strings(row.get("known_moves")),
        "level_up_moves": [_clone(_dict(value)) for value in _list(row.get("level_up_moves")) if _dict(value)],
        "tm_compatibility": _strings(row.get("tm_compatibility")),
        "hm_compatibility": _strings(row.get("hm_compatibility")),
        "active_move_limit": max(0, min(12, _int(row.get("active_move_limit"), 4))),
        "evolution": [_clone(_dict(value)) for value in _list(row.get("evolution")) if _dict(value)],
        "sprite": sprite,
        "combat_visuals": {"battle": _clone(sprite), "shots": shots},
        "notes": _text(row.get("notes")),
    })
    return row


def normalize_species_set(payload):
    data = _dict(payload)
    meta = _dict(data.get("meta"))
    return {
        "version": 2,
        "meta": {**_clone(meta), "name": _text(meta.get("name")) or "POKEROL Fakemon Set", "schema": SCHEMA_NAME},
        "pokemon": [normalize_species_template(row) for row in _list(data.get("pokemon")) if _dict(row)],
        "moves": [normalize_move_template(row) for row in _list(data.get("moves")) if _dict(row)],
    }


def get_species_registry(*, create=False):
    matches = list(search_script(REGISTRY_KEY))
    registry = matches[0] if matches else None
    if registry is None and create:
        registry = create_script(DefaultScript, key=REGISTRY_KEY, persistent=True, autostart=True)
    if registry is not None:
        if registry.db.species is None: registry.db.species = {}
        if registry.db.moves is None: registry.db.moves = {}
        if registry.db.meta is None: registry.db.meta = {}
        registry.db.build = REGISTRY_BUILD
    return registry


def validate_species_set(payload):
    data = normalize_species_set(payload)
    species_rows, move_rows = data["pokemon"], data["moves"]
    errors, warnings, seen_species, seen_moves = [], [], set(), set()

    for item in move_rows:
        move_id = _text(item.get("move_id"))
        if not move_id: errors.append("Skill sin move_id")
        elif move_id in seen_moves: errors.append(f"move_id duplicado: {move_id}")
        seen_moves.add(move_id)
        if item.get("trajectory") not in TRAJECTORY_TYPES: errors.append(f"{item.get('name')}: trajectory inválida")
        if item.get("range") not in RANGE_TYPES: errors.append(f"{item.get('name')}: range inválido")
        for key in ("power", "control", "speed"):
            value = _int(_dict(item.get("combat_profile")).get(key), -1)
            if not 0 <= value <= 5: errors.append(f"{item.get('name')}: combat_profile.{key} fuera de 0..5")
        resolution = _dict(item.get("resolution"))
        if not _list(resolution.get("modes")): errors.append(f"{item.get('name')}: sin modo de resolución")
        if _int(resolution.get("max_checks"), 1) > 2: errors.append(f"{item.get('name')}: max_checks supera 2")
        if bool(item.get("world_enabled")) and not _list(item.get("world_effects")): warnings.append(f"{item.get('name')}: world_enabled sin world_effects")
        machine = _dict(item.get("machine"))
        if _text(machine.get("kind")).upper() != "NONE" and not _text(machine.get("id")): errors.append(f"{item.get('name')}: machine sin id")

    for item in species_rows:
        species_id = _text(item.get("species_id")); name = _text(item.get("species_name")) or species_id
        if not species_id: errors.append("Fakemon sin species_id")
        elif species_id in seen_species: errors.append(f"species_id duplicado: {species_id}")
        seen_species.add(species_id)
        if not _text(item.get("species_name")): errors.append(f"{species_id}: sin species_name")
        if _text(_dict(item.get("body_profile")).get("style")).upper() not in BODY_STYLES: errors.append(f"{name}: body style inválido")
        refs = _strings(item.get("known_moves"))
        refs.extend(_text(_dict(row).get("move_id")) for row in _list(item.get("level_up_moves")) if _text(_dict(row).get("move_id")))
        for move_id in refs:
            if move_id not in seen_moves: errors.append(f"{name}: Skill inexistente {move_id}")
        sprite = _dict(item.get("sprite"))
        if not _text(sprite.get("front")) or not _text(sprite.get("back")): warnings.append(f"{name}: faltan battle_front/back")
        shots = _dict(_dict(item.get("combat_visuals")).get("shots"))
        missing = [pose for pose in SHOT_POSES if not (_text(_dict(shots.get(pose)).get("image")) or _text(_dict(shots.get(pose)).get("video")))]
        if missing: warnings.append(f"{name}: faltan tomas {', '.join(missing)}")

    return {"accepted": not errors, "status": "SPECIES_SET_VALID" if not errors else "SPECIES_SET_INVALID", "schema": SCHEMA_NAME, "species_count": len(species_rows), "move_count": len(move_rows), "errors": errors, "warnings": warnings, "build": REGISTRY_BUILD}


def import_species_set(payload):
    data = normalize_species_set(payload)
    validation = validate_species_set(data)
    if not validation.get("accepted"):
        return validation
    registry = get_species_registry(create=True)
    species_index, move_index = _dict(registry.db.species), _dict(registry.db.moves)
    created_species, updated_species, created_moves, updated_moves = [], [], [], []
    for row in data["moves"]:
        move_id = row["move_id"]; (updated_moves if move_id in move_index else created_moves).append(move_id); move_index[move_id] = _clone(row)
    for row in data["pokemon"]:
        species_id = row["species_id"]; (updated_species if species_id in species_index else created_species).append(species_id); species_index[species_id] = _clone(row)
    registry.db.moves, registry.db.species, registry.db.meta, registry.db.build = move_index, species_index, _clone(data["meta"]), REGISTRY_BUILD
    return {"accepted": True, "status": "SPECIES_SET_IMPORTED", "schema": SCHEMA_NAME, "species_count": len(species_index), "move_count": len(move_index), "created_species": created_species, "updated_species": updated_species, "created_moves": created_moves, "updated_moves": updated_moves, "warnings": validation.get("warnings") or [], "build": REGISTRY_BUILD}


def registry_state():
    registry = get_species_registry(create=False)
    if not registry:
        return {"exists": False, "species_count": 0, "move_count": 0, "schema": SCHEMA_NAME, "build": REGISTRY_BUILD}
    species, moves = _dict(registry.db.species), _dict(registry.db.moves)
    return {"exists": True, "species_count": len(species), "move_count": len(moves), "meta": _clone(_dict(registry.db.meta)), "schema": SCHEMA_NAME, "build": REGISTRY_BUILD}


def move_template(move_id):
    registry = get_species_registry(create=False)
    if not registry: return None
    row = _dict(_dict(registry.db.moves).get(_text(move_id)))
    return normalize_move_template(row) if row else None


def species_template(species_id):
    registry = get_species_registry(create=False)
    if not registry: return None
    row = _dict(_dict(registry.db.species).get(_text(species_id)))
    return normalize_species_template(row) if row else None


def _learned_move_ids(species, level):
    ids = []
    for move_id in _list(species.get("known_moves")):
        move_id = _text(move_id)
        if move_id and move_id not in ids: ids.append(move_id)
    learned = []
    for raw in _list(species.get("level_up_moves")):
        row = _dict(raw); move_id = _text(row.get("move_id")); move_level = max(1, _int(row.get("level"), 1))
        if move_id and move_level <= level: learned.append((move_level, move_id))
    learned.sort(key=lambda item: item[0])
    for _move_level, move_id in learned:
        if move_id in ids: ids.remove(move_id)
        ids.append(move_id)
    limit = max(0, _int(species.get("active_move_limit"), 4))
    return ids[-limit:] if limit else ids


def spawn_species_profile(species_id, *, level=None, wild=True):
    species = species_template(species_id)
    if not species: return None
    spawn_level = max(1, _int(level, species.get("level", 1)))
    moves = [move for move_id in _learned_move_ids(species, spawn_level) if (move := move_template(move_id))]
    profile = _clone(species)
    profile.pop("editor_id", None)
    profile["entity_id"] = f"WILD-{_text(species_id)}-{uuid4().hex[:10].upper()}" if wild else f"PKMN-{uuid4().hex[:12].upper()}"
    profile["level"], profile["moves"], profile["resolved_moves"], profile["wild"], profile["status"], profile["schema"] = spawn_level, moves, _clone(moves), bool(wild), "OK", SCHEMA_NAME
    profile.pop("hp_current", None); profile.pop("hp_max", None)
    return profile
