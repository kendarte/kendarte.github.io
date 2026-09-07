"""Generic POKEROL move-to-world capability and combat-profile checks.

Legacy delivery/defense labels remain accepted for authored content, but battle
logic consumes a smaller POKEROL vocabulary: trajectory + range + power/control/
speed + properties. The AI DM may interpret creative use; this module defines
what the move can actually do.
"""

DELIVERY_TYPES = {
    "CONTACT", "PROJECTILE", "BEAM", "PARABOLA", "ARC", "RAIN", "FALL",
    "GROUND_BURST", "CRAWL", "WAVE", "CONE", "MINE", "FIELD", "SELF",
    "TARGETED", "MOVEMENT",
}

TRAJECTORY_TYPES = {
    "CONTACT", "DIRECT", "BALLISTIC", "CURVED", "VERTICAL", "GROUND", "ZONE",
    "SELF", "MOVEMENT",
}

LEGACY_TRAJECTORY_ALIASES = {
    "CONTACT": "CONTACT",
    "PROJECTILE": "DIRECT",
    "BEAM": "DIRECT",
    "WAVE": "DIRECT",
    "CONE": "DIRECT",
    "TARGETED": "DIRECT",
    "PARABOLA": "BALLISTIC",
    "ARC": "CURVED",
    "RAIN": "VERTICAL",
    "FALL": "VERTICAL",
    "GROUND_BURST": "GROUND",
    "CRAWL": "GROUND",
    "MINE": "ZONE",
    "FIELD": "ZONE",
    "SELF": "SELF",
    "MOVEMENT": "MOVEMENT",
}

RANGE_TYPES = {"SELF", "SHORT", "MID", "LONG"}

DEFENSE_PROFILES = {
    "NONE", "BARRIER", "SHELTER", "REDIRECT", "REFLECT", "ABSORB", "BRUSH",
}
DEFENSE_FUNCTION_ALIASES = {
    "NONE": "NONE",
    "BARRIER": "BLOCK",
    "SHELTER": "BLOCK_ALL",
    "REDIRECT": "DEFLECT",
    "REFLECT": "REFLECT",
    "ABSORB": "ABSORB",
    "BRUSH": "DEFLECT",
}

# Generic anime-physics semantics. Explicit move.effect_rules override these.
EFFECT_MATERIAL_DEFAULTS = {
    "BURN": {"CREATURE", "VEGETATION", "WOOD", "ROPE", "FABRIC", "PAPER", "DRY_GRASS", "LEAF_LITTER"},
    "IGNITE": {"VEGETATION", "WOOD", "ROPE", "FABRIC", "PAPER", "DRY_GRASS", "LEAF_LITTER"},
    "HEAT": {"CREATURE", "VEGETATION", "WOOD", "ROPE", "FABRIC", "PAPER", "DRY_GRASS", "LEAF_LITTER", "ICE", "WATER", "GLASS", "METAL", "STONE", "CERAMIC", "ELECTRICAL_DEVICE", "HEAVY_OBJECT", "FRAGILE_STRUCTURE"},
    "MELT": {"ICE", "METAL", "GLASS", "PLASTIC", "WAX"},
    "WATER": {"CREATURE", "FIRE", "SOIL", "SAND", "STONE", "GLASS", "METAL", "VEGETATION", "WOOD", "ELECTRICAL_DEVICE", "DRY_GRASS", "LEAF_LITTER"},
    "SOAK": {"CREATURE", "SOIL", "SAND", "VEGETATION", "WOOD", "ROPE", "FABRIC", "PAPER", "DRY_GRASS", "LEAF_LITTER"},
    "COOL": {"CREATURE", "FIRE", "SOIL", "SAND", "STONE", "GLASS", "METAL", "VEGETATION", "WOOD", "ELECTRICAL_DEVICE", "ICE", "WATER", "CERAMIC", "HEAVY_OBJECT", "FRAGILE_STRUCTURE"},
    "FREEZE": {"WATER", "PUDDLE", "POND", "STREAM", "RIVER", "LAKE", "CREATURE", "WET_SURFACE"},
    "ERODE": {"SOIL", "SAND", "STONE", "CERAMIC", "FRAGILE_STRUCTURE"},
    "ELECTRIFY": {"CREATURE", "WATER", "PUDDLE", "POND", "STREAM", "RIVER", "LAKE", "METAL", "ELECTRICAL_DEVICE"},
    "SHORT_CIRCUIT": {"WATER", "PUDDLE", "POND", "STREAM", "RIVER", "LAKE", "METAL", "ELECTRICAL_DEVICE"},
    "POWER_DEVICE": {"METAL", "ELECTRICAL_DEVICE"},
    "CUT": {"CREATURE", "VEGETATION", "WOOD", "ROPE", "FABRIC"},
    "CUT_VEGETATION": {"VEGETATION", "WOOD", "VINE", "BRUSH"},
    "PIERCE": {"CREATURE", "FABRIC", "FRAGILE_STRUCTURE"},
    "BREAK": {"FRAGILE_STRUCTURE", "BRITTLE_STRUCTURE", "STONE", "WOOD", "GLASS", "CERAMIC"},
    "BLUNT": {"CREATURE", "FRAGILE_STRUCTURE", "BRITTLE_STRUCTURE"},
    "PUSH": {"CREATURE", "HEAVY_OBJECT", "FRAGILE_STRUCTURE"},
    "PULL": {"CREATURE", "ROPE", "HEAVY_OBJECT"},
    "LIFT": {"CREATURE", "HEAVY_OBJECT", "FRAGILE_STRUCTURE"},
    "RESTRAIN": {"CREATURE", "ROPE", "VEGETATION"},
    "CLEAR_SMOKE": {"SMOKE", "GAS", "FIRE"},
    "CREATE_WIND": {"CREATURE", "SMOKE", "GAS", "FIRE", "LEAF_LITTER"},
    "MOVE_AIR": {"SMOKE", "GAS", "FIRE", "LEAF_LITTER"},
    "LIGHT": {"CREATURE", "DARKNESS"},
    "SURF": {"WATER", "POND", "STREAM", "RIVER", "LAKE"},
    "MOVE_WATER": {"WATER", "POND", "STREAM", "RIVER", "LAKE"},
}

THERMAL_EFFECTS = {"HEAT", "COOL", "MELT", "FREEZE"}
THERMAL_PROPERTY_KEYS = {
    "thermal_shock_sensitivity", "heat_resistance", "ignition_point_c",
    "melting_point_c", "freezing_point_c", "temperature_c",
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


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _rating(value, default=3):
    try:
        return max(0, min(5, int(round(float(value)))))
    except (TypeError, ValueError):
        return int(default)


def canonical_trajectory(move):
    """Return POKEROL trajectory while accepting older reference-inspired delivery tags."""
    row = _dict(move)
    authored = str(row.get("trajectory") or "").strip().upper()
    if authored in TRAJECTORY_TYPES:
        return authored
    delivery = str(row.get("delivery") or "").strip().upper()
    return LEGACY_TRAJECTORY_ALIASES.get(delivery, "DIRECT")


def canonical_range(move):
    row = _dict(move)
    value = str(row.get("range") or row.get("range_band") or "").strip().upper()
    if value in RANGE_TYPES:
        return value
    trajectory = canonical_trajectory(row)
    if trajectory == "SELF":
        return "SELF"
    if trajectory == "CONTACT":
        return "SHORT"
    return "MID"


def _derived_power(move):
    explicit = _dict(move).get("combat_profile", {}).get("power") if isinstance(_dict(move).get("combat_profile"), dict) else None
    if explicit is not None:
        return _rating(explicit)
    raw = _num(_dict(move).get("power"), 0)
    if raw <= 0:
        return 0
    if raw <= 40:
        return 2
    if raw <= 70:
        return 3
    if raw <= 100:
        return 4
    return 5


def _derived_control(move):
    profile = _dict(_dict(move).get("combat_profile"))
    if profile.get("control") is not None:
        return _rating(profile.get("control"))
    accuracy = _num(_dict(move).get("accuracy"), 100)
    if accuracy >= 100:
        return 4
    if accuracy >= 90:
        return 3
    if accuracy >= 75:
        return 2
    return 1


def _derived_speed(move):
    profile = _dict(_dict(move).get("combat_profile"))
    if profile.get("speed") is not None:
        return _rating(profile.get("speed"))
    priority = _num(_dict(move).get("priority"), 0)
    return _rating(3 + priority, default=3)


def move_combat_profile(move):
    """Hard-data profile consumed by tactical/DM battle logic.

    power controls damage/break/force; control controls precision and elaborate
    environment use; speed controls execution/reaction pressure. None replaces
    the Adventure-stat d6 checks used for maneuvers.
    """
    row = _dict(move)
    defense = str(row.get("defense_profile") or "NONE").strip().upper()
    properties = _strings(row.get("properties")) | _strings(row.get("combat_tags")) | _strings(row.get("world_effects"))
    return {
        "move_id": str(row.get("move_id") or "").strip(),
        "name": str(row.get("name") or row.get("move_id") or "").strip(),
        "power": _derived_power(row),
        "control": _derived_control(row),
        "speed": _derived_speed(row),
        "range": canonical_range(row),
        "trajectory": canonical_trajectory(row),
        "properties": sorted(properties),
        "world_effects": sorted(_strings(row.get("world_effects"))),
        "defense_profile": defense if defense in DEFENSE_PROFILES else "NONE",
        "defense_function": DEFENSE_FUNCTION_ALIASES.get(defense, "NONE"),
        "legacy_delivery": str(row.get("delivery") or "").strip().upper() or None,
        "profile_source": "AUTHORED" if isinstance(row.get("combat_profile"), dict) else "LEGACY_DERIVED",
    }


def validate_move_capability(move):
    move = _dict(move)
    errors = []
    move_id = str(move.get("move_id") or "").strip()
    if not move_id:
        errors.append("MISSING_MOVE_ID")

    delivery = str(move.get("delivery") or "").strip().upper()
    trajectory = str(move.get("trajectory") or "").strip().upper()
    if delivery and delivery not in DELIVERY_TYPES:
        errors.append("INVALID_DELIVERY")
    if trajectory and trajectory not in TRAJECTORY_TYPES:
        errors.append("INVALID_TRAJECTORY")
    if not delivery and not trajectory:
        errors.append("MISSING_DELIVERY_OR_TRAJECTORY")

    defense = str(move.get("defense_profile") or "NONE").strip().upper()
    if defense not in DEFENSE_PROFILES:
        errors.append("INVALID_DEFENSE_PROFILE")

    if bool(move.get("world_enabled")) and not _strings(move.get("world_effects")):
        errors.append("WORLD_ENABLED_WITHOUT_EFFECTS")

    profile = move_combat_profile(move)
    return {
        "valid": not errors,
        "errors": errors,
        "move_id": move_id,
        "delivery": delivery or None,
        "trajectory": profile["trajectory"],
        "range": profile["range"],
        "defense_profile": defense,
        "combat_profile": profile,
    }


def known_move_ids(pokemon):
    return _strings(_dict(pokemon).get("known_moves"))


def pokemon_knows_move(pokemon, move):
    move_id = str(_dict(move).get("move_id") or "").strip().upper()
    known = known_move_ids(pokemon)
    if not known:
        # Battle profiles often carry resolved moves rather than a separate ID set.
        for row in _list(_dict(pokemon).get("moves")) + _list(_dict(pokemon).get("resolved_moves")):
            if str(_dict(row).get("move_id") or "").strip().upper() == move_id:
                return True
    return bool(move_id and move_id in known)


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


def _explicit_effect_rules(move):
    rules = {}
    for raw in _list(_dict(move).get("effect_rules")):
        row = _dict(raw)
        effect = str(row.get("effect") or "").strip().upper()
        if not effect:
            continue
        rules[effect] = {
            "materials": _strings(row.get("materials")),
            "tags": _strings(row.get("tags")),
            "requires_properties": {str(v).strip() for v in _list(row.get("requires_properties")) if str(v).strip()},
        }
    return rules


def _target_has_required_property(target, names):
    if not names:
        return True
    props = _dict(_dict(target).get("physical_properties"))
    state = _dict(_dict(target).get("environmental_state"))
    return any(name in props or name in state for name in names)


def _thermal_target(target):
    target = _dict(target)
    props = _dict(target.get("physical_properties"))
    state = _dict(target.get("environmental_state"))
    return bool((set(props.keys()) | set(state.keys())) & THERMAL_PROPERTY_KEYS)


def _effect_matches(effect, move, target, explicit_rules):
    target = _dict(target)
    tags = _strings(target.get("materials")) | _strings(target.get("tags"))
    if not tags and not _dict(target.get("physical_properties")) and not _dict(target.get("environmental_state")):
        return False

    explicit = explicit_rules.get(effect)
    if explicit is not None:
        allowed = explicit["materials"] | explicit["tags"]
        if allowed and not (allowed & tags):
            return False
        return _target_has_required_property(target, explicit["requires_properties"])

    semantic = EFFECT_MATERIAL_DEFAULTS.get(effect)
    if semantic is not None:
        if semantic & tags:
            return True
        if effect in THERMAL_EFFECTS and _thermal_target(target):
            return True
        return False

    legacy = _strings(_dict(move).get("materials"))
    return not legacy or bool(legacy & tags)


def compatible_world_effects(move, target):
    """Return only effects physically compatible with this specific target."""
    move = _dict(move)
    target = _dict(target)
    effects = _strings(move.get("world_effects"))
    if not effects:
        return []
    if not target and canonical_trajectory(move) == "SELF":
        return sorted(effects)

    rules = _explicit_effect_rules(move)
    return sorted(effect for effect in effects if _effect_matches(effect, move, target, rules))


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
            "trajectory": validation["trajectory"],
            "effects": [],
        }

    target_tags = _strings(target.get("materials")) | _strings(target.get("tags"))
    legacy_matches = _strings(move.get("materials")) & target_tags
    return {
        "status": "WORLD_MOVE_ADMISSIBLE",
        "allowed": True,
        "move_id": validation["move_id"],
        "delivery": validation["delivery"],
        "trajectory": validation["trajectory"],
        "range": validation["range"],
        "combat_profile": validation["combat_profile"],
        "defense_profile": validation["defense_profile"],
        "effects": effects,
        "target_material_matches": sorted(legacy_matches),
        "world_rules": _list(move.get("world_rules")),
    }
