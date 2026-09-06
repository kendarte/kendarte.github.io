"""Generic POKEROL move-to-world capability checks.

This module does not resolve battle damage and does not mutate world state.
It answers whether an authored Pokémon move can plausibly expose one or more
world effects against an authored target/environment packet.
"""

DELIVERY_TYPES = {
    "CONTACT", "PROJECTILE", "BEAM", "PARABOLA", "ARC", "RAIN", "FALL",
    "GROUND_BURST", "CRAWL", "WAVE", "CONE", "MINE", "FIELD", "SELF",
    "TARGETED", "MOVEMENT",
}

DEFENSE_PROFILES = {
    "NONE", "BARRIER", "SHELTER", "REDIRECT", "REFLECT", "ABSORB", "BRUSH",
}


def _dict(value):
    return dict(value or {}) if hasattr(value or {}, "items") else {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _strings(value):
    return {str(item).strip().upper() for item in _list(value) if str(item).strip()}


def validate_move_capability(move):
    move = _dict(move)
    errors = []
    move_id = str(move.get("move_id") or "").strip()
    if not move_id:
        errors.append("MISSING_MOVE_ID")

    delivery = str(move.get("delivery") or "").strip().upper()
    if delivery not in DELIVERY_TYPES:
        errors.append("INVALID_DELIVERY")

    defense = str(move.get("defense_profile") or "NONE").strip().upper()
    if defense not in DEFENSE_PROFILES:
        errors.append("INVALID_DEFENSE_PROFILE")

    if bool(move.get("world_enabled")) and not _strings(move.get("world_effects")):
        errors.append("WORLD_ENABLED_WITHOUT_EFFECTS")

    return {
        "valid": not errors,
        "errors": errors,
        "move_id": move_id,
        "delivery": delivery,
        "defense_profile": defense,
    }


def known_move_ids(pokemon):
    return _strings(_dict(pokemon).get("known_moves"))


def pokemon_knows_move(pokemon, move):
    move_id = str(_dict(move).get("move_id") or "").strip().upper()
    return bool(move_id and move_id in known_move_ids(pokemon))


def _requirements(move):
    defaults = {
        "line_of_sight": False,
        "ground_contact": False,
        "requires_water": False,
        "requires_airspace": False,
        "requires_target": False,
    }
    defaults.update(_dict(_dict(move).get("requirements")))
    return defaults


def _environment_allows(move, environment, target):
    req = _requirements(move)
    environment = _dict(environment)
    failures = []

    if req["line_of_sight"] and environment.get("line_of_sight") is False:
        failures.append("NO_LINE_OF_SIGHT")
    if req["ground_contact"] and environment.get("ground_contact") is False:
        failures.append("NO_GROUND_CONTACT")
    if req["requires_water"] and not bool(environment.get("water_available")):
        failures.append("WATER_REQUIRED")
    if req["requires_airspace"] and not bool(environment.get("airspace_available", True)):
        failures.append("AIRSPACE_REQUIRED")
    if req["requires_target"] and not target:
        failures.append("TARGET_REQUIRED")

    return failures


def compatible_world_effects(move, target):
    """Return authored effects whose move material vocabulary matches target tags."""
    move = _dict(move)
    target = _dict(target)
    effects = _strings(move.get("world_effects"))
    if not effects:
        return []

    accepted_materials = _strings(move.get("materials"))
    target_tags = _strings(target.get("materials")) | _strings(target.get("tags"))
    if not target and str(move.get("delivery") or "").upper() == "SELF":
        return sorted(effects)

    if not accepted_materials:
        return sorted(effects)
    if not target_tags:
        return []

    return sorted(effects) if accepted_materials & target_tags else []


def evaluate_world_move_use(pokemon, move, target=None, environment=None):
    """Read-only admissibility check for one proposed world use."""
    pokemon = _dict(pokemon)
    move = _dict(move)
    target = _dict(target)
    environment = _dict(environment)

    validation = validate_move_capability(move)
    if not validation["valid"]:
        return {
            "status": "INVALID_MOVE_CAPABILITY",
            "allowed": False,
            "validation": validation,
            "effects": [],
        }

    if not pokemon_knows_move(pokemon, move):
        return {
            "status": "MOVE_NOT_KNOWN",
            "allowed": False,
            "move_id": validation["move_id"],
            "effects": [],
        }

    if not bool(move.get("world_enabled")):
        return {
            "status": "MOVE_NOT_WORLD_ENABLED",
            "allowed": False,
            "move_id": validation["move_id"],
            "effects": [],
        }

    requirement_failures = _environment_allows(move, environment, target)
    if requirement_failures:
        return {
            "status": "REQUIREMENTS_NOT_MET",
            "allowed": False,
            "move_id": validation["move_id"],
            "failures": requirement_failures,
            "effects": [],
        }

    effects = compatible_world_effects(move, target)
    if not effects:
        return {
            "status": "NO_COMPATIBLE_WORLD_EFFECT",
            "allowed": False,
            "move_id": validation["move_id"],
            "delivery": validation["delivery"],
            "effects": [],
        }

    return {
        "status": "WORLD_MOVE_ADMISSIBLE",
        "allowed": True,
        "move_id": validation["move_id"],
        "delivery": validation["delivery"],
        "defense_profile": validation["defense_profile"],
        "effects": effects,
        "target_material_matches": sorted(
            _strings(move.get("materials"))
            & (_strings(target.get("materials")) | _strings(target.get("tags")))
        ),
        "world_rules": _list(move.get("world_rules")),
    }
