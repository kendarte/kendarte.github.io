"""Authoritative battle-position rules for POKEROL anime-style combat.

Battle position is structured state, not narration. The World/Room declares the
available water, cover and elevation anchors. This module validates transitions,
exposes movement options and supplies combat modifiers/reach checks.
"""

from copy import deepcopy

from services.pokemon_battle_environment_engine import environment_targets


POSITION_BUILD = "0.1.0-anime-battle-position"

STANCE_GROUND = "GROUND"
STANCE_WATER = "WATER"
STANCE_ELEVATED = "ELEVATED"
STANCE_AIR = "AIR"
VALID_STANCES = {STANCE_GROUND, STANCE_WATER, STANCE_ELEVATED, STANCE_AIR}

COVER_TAGS = {"COVER", "SHELTER", "LOW_COVER", "FULL_COVER"}
ELEVATION_TAGS = {"CLIMBABLE", "PERCH", "ELEVATED_POSITION", "HIGH_GROUND"}
CLIMB_BODY_TAGS = {"CLIMBER", "CLAWS", "VINES", "HOOKS", "GRIPPING_FEET"}

# These are authored Map-Creator biome cover tokens. They are not inferred by AI.
BIOME_COVER_RATING = {
    "houses": 0.45,
    "buildings": 0.45,
    "earth_banks": 0.38,
    "banks": 0.35,
    "rocks": 0.35,
    "trees": 0.30,
    "tree": 0.30,
    "fences": 0.25,
    "fence": 0.25,
    "benches": 0.22,
    "shrubs": 0.20,
    "hedges": 0.20,
    "reeds": 0.16,
    "tall_grass": 0.14,
    "posts": 0.12,
    "sign": 0.12,
}
BIOME_ELEVATION_TOKENS = {
    "trees", "tree", "fences", "fence", "earth_banks", "banks",
    "rocks", "buildings", "houses", "posts", "shelves", "branches",
}

AIR_REACH_DELIVERIES = {
    "PROJECTILE", "BEAM", "ARC", "RAIN", "WAVE", "CONE", "TARGETED", "MOVEMENT",
}
ELEVATED_REACH_DELIVERIES = AIR_REACH_DELIVERIES | {"PARABOLA"}
MOBILITY_WORLD_EFFECTS = {"CROSS_GAP", "FLY", "PULL", "LIFT", "SURF", "CARRY"}


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


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _upper_set(value):
    return {str(v).strip().upper() for v in _list(value) if str(v).strip()}


def _slug(value):
    raw = _text(value).lower().replace(" ", "_").replace("-", "_")
    return "".join(ch for ch in raw if ch.isalnum() or ch == "_")


def source_profile_for_side(battle, side="PLAYER"):
    state = _dict(battle)
    key = "_source_player_profile" if _text(side).upper() == "PLAYER" else "_source_enemy_profile"
    source = _dict(state.get(key))
    return source or _dict(state.get("player" if _text(side).upper() == "PLAYER" else "enemy"))


def normalized_position(pokemon):
    p = _dict(pokemon)
    raw = _dict(p.get("battle_position"))
    medium_id = _text(raw.get("medium_id") or p.get("contact_medium_id"))
    stance = _text(raw.get("stance")).upper()
    if medium_id:
        stance = STANCE_WATER
    if stance not in VALID_STANCES:
        stance = STANCE_GROUND
    cover = _dict(raw.get("cover"))
    return {
        "stance": stance,
        "medium_id": medium_id or None,
        "medium_kind": _text(raw.get("medium_kind") or p.get("contact_medium_kind")) or None,
        "anchor": deepcopy(_dict(raw.get("anchor"))),
        "cover": deepcopy(cover),
        "elevation": _text(raw.get("elevation")).upper() or ("MID" if stance == STANCE_ELEVATED else None),
        "altitude": _text(raw.get("altitude")).upper() or ("LOW" if stance == STANCE_AIR else None),
        "mobility_modifier": max(0.35, min(1.35, _float(raw.get("mobility_modifier"), 1.0))),
        "submerged": bool(raw.get("submerged", False)),
    }


def set_position(pokemon, position):
    if not isinstance(pokemon, dict):
        return None
    pos = normalized_position(position if isinstance(position, dict) else {})
    # normalized_position expects a Pokémon-shaped packet; copy explicit values back.
    explicit = _dict(position)
    stance = _text(explicit.get("stance")).upper() or pos["stance"]
    if stance not in VALID_STANCES:
        stance = STANCE_GROUND
    medium_id = _text(explicit.get("medium_id"))
    packet = {
        "stance": STANCE_WATER if medium_id else stance,
        "medium_id": medium_id or None,
        "medium_kind": _text(explicit.get("medium_kind")) or None,
        "anchor": deepcopy(_dict(explicit.get("anchor"))),
        "cover": deepcopy(_dict(explicit.get("cover"))),
        "elevation": _text(explicit.get("elevation")).upper() or None,
        "altitude": _text(explicit.get("altitude")).upper() or None,
        "mobility_modifier": max(0.35, min(1.35, _float(explicit.get("mobility_modifier"), 1.0))),
        "submerged": bool(explicit.get("submerged", False)),
    }
    pokemon["battle_position"] = packet
    if packet["medium_id"]:
        pokemon["contact_medium_id"] = packet["medium_id"]
        pokemon["contact_medium_kind"] = packet["medium_kind"]
    else:
        pokemon.pop("contact_medium_id", None)
        pokemon.pop("contact_medium_kind", None)
    return packet


def ensure_position(pokemon):
    current = normalized_position(pokemon)
    return set_position(pokemon, current)


def _locomotion(profile):
    return _upper_set(_dict(profile).get("locomotion"))


def _body_tags(profile):
    return _upper_set(_dict(profile).get("body_tags"))


def can_fly(profile):
    return "FLY" in _locomotion(profile) or "FLIGHT" in _locomotion(profile)


def can_climb(profile):
    return "CLIMB" in _locomotion(profile) or bool(_body_tags(profile) & CLIMB_BODY_TAGS)


def can_swim(profile):
    locomotion = _locomotion(profile)
    tags = _body_tags(profile)
    return "SWIM" in locomotion or "AQUATIC" in tags


def _move_effects(move):
    return _upper_set(_dict(move).get("world_effects"))


def _active_moves(pokemon):
    return [_dict(row) for row in _list(_dict(pokemon).get("moves")) if _dict(row)]


def _move_position_methods(pokemon):
    rows = []
    for move in _active_moves(pokemon):
        effects = _move_effects(move)
        move_id = _text(move.get("move_id"))
        if not move_id or int(move.get("pp_current", move.get("pp", 0)) or 0) <= 0:
            continue
        if "FLY" in effects:
            rows.append(("AIR", move))
        if "SURF" in effects or "MOVE_WATER" in effects:
            rows.append(("WATER", move))
        if effects & {"CROSS_GAP", "PULL", "LIFT"}:
            rows.append(("ELEVATED", move))
    return rows


def _target_ref(row):
    row = _dict(row)
    return {
        "object_id": _text(row.get("object_id")),
        "dbref": row.get("dbref"),
        "name": _text(row.get("name")),
        "water_body_id": _text(row.get("water_body_id")) or None,
    }


def _room_biome_cover(actor):
    room = getattr(actor, "location", None) if actor else None
    biome = _dict(getattr(getattr(room, "db", None), "biome_profile", {})) if room else {}
    rows = []
    seen = set()
    for raw in _list(biome.get("cover")):
        label = _text(raw)
        token = _slug(label)
        if not token or token in seen:
            continue
        seen.add(token)
        rating = BIOME_COVER_RATING.get(token, 0.18)
        rows.append({
            "target_id": f"BIOME-COVER:{token}",
            "name": label.replace("_", " ").title(),
            "source": "BIOME_PROFILE",
            "target_type": "COVER",
            "cover_rating": rating,
            "supports_elevation": token in BIOME_ELEVATION_TOKENS,
            "biome_cover_token": token,
        })
    return rows


def _object_position_targets(actor):
    rows = []
    for raw in environment_targets(actor):
        row = _dict(raw)
        tags = _upper_set(row.get("tags"))
        materials = _upper_set(row.get("materials"))
        water_body_id = _text(row.get("water_body_id"))
        base = {
            "name": _text(row.get("name")) or _text(row.get("object_id")) or "Objeto",
            "source": "ROOM_OBJECT",
            "object": _target_ref(row),
            "materials": sorted(materials),
            "tags": sorted(tags),
        }
        if water_body_id or "WATER" in materials:
            medium_id = water_body_id or f"WATER-OBJECT:{row.get('dbref')}"
            rows.append({
                **base,
                "target_id": f"WATER:{medium_id}",
                "target_type": "WATER",
                "water_body_id": medium_id,
                "medium_kind": "WATER",
            })
        if tags & COVER_TAGS:
            rating = 0.45 if "FULL_COVER" in tags else (0.18 if "LOW_COVER" in tags else 0.30)
            rows.append({
                **base,
                "target_id": f"COVER:{row.get('dbref')}",
                "target_type": "COVER",
                "cover_rating": rating,
                "supports_elevation": bool(tags & ELEVATION_TAGS),
            })
        if tags & ELEVATION_TAGS:
            rows.append({
                **base,
                "target_id": f"ELEVATED:{row.get('dbref')}",
                "target_type": "ELEVATED",
                "cover_rating": 0.18 if tags & COVER_TAGS else 0.0,
                "supports_elevation": True,
            })
    return rows


def _dedupe_targets(rows):
    output = []
    seen = set()
    for row in rows:
        key = (_text(row.get("target_id")), _text(row.get("action")), _text(row.get("method_move_id")))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def position_targets(actor, battle, side="PLAYER"):
    """Return server-authorized battle position transitions for one participant."""
    state = _dict(battle)
    side_name = _text(side).upper() or "PLAYER"
    pokemon = _dict(state.get("player" if side_name == "PLAYER" else "enemy"))
    profile = source_profile_for_side(state, side_name)
    current = normalized_position(pokemon)
    object_rows = _object_position_targets(actor)
    biome_rows = _room_biome_cover(actor)
    rows = []

    if current["stance"] != STANCE_GROUND or current.get("cover"):
        rows.append({
            "target_id": "GROUND:OPEN",
            "target_type": "GROUND",
            "action": "RETURN_GROUND",
            "name": "Terreno abierto",
            "source": "ROOM",
            "natural": True,
        })

    water_rows = [row for row in object_rows if row.get("target_type") == "WATER"]
    for row in water_rows:
        if _text(current.get("medium_id")) == _text(row.get("water_body_id")):
            continue
        rows.append({
            **deepcopy(row),
            "action": "ENTER_WATER",
            "natural": True,
            "mobility_modifier": 1.08 if can_swim(profile) else 0.72,
        })

    cover_rows = [row for row in object_rows if row.get("target_type") == "COVER"] + biome_rows
    for row in cover_rows:
        rows.append({**deepcopy(row), "action": "TAKE_COVER", "natural": True})

    elevated_rows = [row for row in object_rows if row.get("target_type") == "ELEVATED"]
    elevated_rows += [row for row in biome_rows if bool(row.get("supports_elevation"))]
    if can_climb(profile) or can_fly(profile):
        for row in elevated_rows:
            rows.append({**deepcopy(row), "action": "CLIMB", "natural": True})

    if can_fly(profile) and current["stance"] != STANCE_AIR:
        rows.append({
            "target_id": "AIRSPACE:LOW",
            "target_type": "AIR",
            "action": "TAKEOFF",
            "name": "Espacio aéreo",
            "source": "ROOM",
            "natural": True,
            "altitude": "LOW",
        })

    # Move-assisted positioning. The move is a method, not the owner of physics.
    for method_kind, move in _move_position_methods(pokemon):
        move_id = _text(move.get("move_id"))
        move_name = _text(move.get("name")) or move_id
        if method_kind == "AIR" and current["stance"] != STANCE_AIR:
            rows.append({
                "target_id": "AIRSPACE:LOW",
                "target_type": "AIR",
                "action": "TAKEOFF",
                "name": "Espacio aéreo",
                "source": "ROOM",
                "natural": False,
                "method_move_id": move_id,
                "method_move_name": move_name,
                "altitude": "LOW",
            })
        elif method_kind == "WATER":
            for row in water_rows:
                if _text(current.get("medium_id")) == _text(row.get("water_body_id")):
                    continue
                rows.append({
                    **deepcopy(row),
                    "action": "ENTER_WATER",
                    "natural": False,
                    "method_move_id": move_id,
                    "method_move_name": move_name,
                    "mobility_modifier": 1.12,
                })
        elif method_kind == "ELEVATED":
            for row in elevated_rows:
                rows.append({
                    **deepcopy(row),
                    "action": "CLIMB",
                    "natural": False,
                    "method_move_id": move_id,
                    "method_move_name": move_name,
                })

    return _dedupe_targets(rows)


def resolve_position_target(actor, battle, action, side="PLAYER"):
    """Validate one client-requested position target against current Room authority."""
    requested = _dict(action)
    wanted_target = _text(requested.get("target_id"))
    wanted_action = _text(requested.get("position_action")).upper()
    wanted_method = _text(requested.get("method_move_id"))
    for row in position_targets(actor, battle, side=side):
        if _text(row.get("target_id")) != wanted_target:
            continue
        if _text(row.get("action")).upper() != wanted_action:
            continue
        if _text(row.get("method_move_id")) != wanted_method:
            continue
        return deepcopy(row)
    return None


def apply_verified_position(pokemon, target):
    """Mutate one battle participant using an already verified target packet."""
    if not isinstance(pokemon, dict):
        return {"applied": False, "status": "NO_POKEMON", "build": POSITION_BUILD}
    row = _dict(target)
    action = _text(row.get("action")).upper()
    name = _text(pokemon.get("name") or pokemon.get("species_name")) or "Pokémon"

    if action == "RETURN_GROUND":
        position = set_position(pokemon, {"stance": STANCE_GROUND, "mobility_modifier": 1.0})
        text = f"{name} vuelve a terreno abierto."
    elif action == "ENTER_WATER":
        medium_id = _text(row.get("water_body_id"))
        if not medium_id:
            return {"applied": False, "status": "WATER_BODY_REQUIRED", "build": POSITION_BUILD}
        position = set_position(pokemon, {
            "stance": STANCE_WATER,
            "medium_id": medium_id,
            "medium_kind": _text(row.get("medium_kind")) or "WATER",
            "anchor": deepcopy(_dict(row.get("object"))),
            "mobility_modifier": _float(row.get("mobility_modifier"), 0.75),
        })
        text = f"{name} entra en {row.get('name') or 'el agua'}."
    elif action == "TAKE_COVER":
        rating = max(0.0, min(0.65, _float(row.get("cover_rating"), 0.20)))
        position = set_position(pokemon, {
            "stance": STANCE_GROUND,
            "anchor": deepcopy(_dict(row.get("object"))),
            "cover": {
                "target_id": row.get("target_id"),
                "name": row.get("name"),
                "rating": rating,
                "source": row.get("source"),
            },
            "mobility_modifier": 0.94,
        })
        text = f"{name} toma cobertura en {row.get('name') or 'el terreno'}."
    elif action == "CLIMB":
        position = set_position(pokemon, {
            "stance": STANCE_ELEVATED,
            "anchor": deepcopy(_dict(row.get("object"))) or {
                "target_id": row.get("target_id"), "name": row.get("name"), "source": row.get("source")
            },
            "cover": {
                "target_id": row.get("target_id"),
                "name": row.get("name"),
                "rating": max(0.0, min(0.45, _float(row.get("cover_rating"), 0.0))),
                "source": row.get("source"),
            } if _float(row.get("cover_rating"), 0.0) > 0 else {},
            "elevation": "MID",
            "mobility_modifier": 0.98,
        })
        text = f"{name} gana altura usando {row.get('name') or 'el terreno'}."
    elif action == "TAKEOFF":
        position = set_position(pokemon, {
            "stance": STANCE_AIR,
            "altitude": _text(row.get("altitude")).upper() or "LOW",
            "mobility_modifier": 1.08,
        })
        text = f"{name} toma el aire."
    else:
        return {"applied": False, "status": "UNSUPPORTED_POSITION_ACTION", "build": POSITION_BUILD}

    return {
        "applied": True,
        "status": "POSITION_CHANGED",
        "action": action,
        "text": text,
        "position": deepcopy(position),
        "target": deepcopy(row),
        "build": POSITION_BUILD,
    }


def position_accuracy_multiplier(attacker, defender):
    """Generic positional accuracy modifier used by every battle round."""
    atk = normalized_position(attacker)
    dfn = normalized_position(defender)
    mult = 1.0
    cover = _dict(dfn.get("cover"))
    rating = max(0.0, min(0.65, _float(cover.get("rating"), 0.0)))
    mult *= 1.0 - (rating * 0.60)
    if dfn["stance"] == STANCE_AIR:
        mult *= 0.90
    elif dfn["stance"] == STANCE_ELEVATED:
        mult *= 0.94
    if dfn["stance"] == STANCE_WATER and dfn.get("mobility_modifier", 1.0) < 0.9:
        mult *= 1.08
    if atk["stance"] == STANCE_WATER and atk.get("mobility_modifier", 1.0) < 0.9:
        mult *= 0.90
    return max(0.45, min(1.20, mult))


def position_speed_multiplier(pokemon):
    pos = normalized_position(pokemon)
    mult = max(0.45, min(1.25, _float(pos.get("mobility_modifier"), 1.0)))
    if pos["stance"] == STANCE_AIR:
        mult *= 1.03
    return max(0.40, min(1.30, mult))


def position_move_gate(attacker, defender, move):
    """Check whether a move can physically reach from current battle positions."""
    atk = normalized_position(attacker)
    dfn = normalized_position(defender)
    move = _dict(move)
    delivery = _text(move.get("delivery")).upper()
    effects = _move_effects(move)
    req = _dict(move.get("requirements"))

    if bool(req.get("ground_contact")) and atk["stance"] == STANCE_AIR:
        return {"allowed": False, "status": "ATTACKER_NOT_GROUNDED", "build": POSITION_BUILD}
    if bool(req.get("requires_water")) and atk["stance"] != STANCE_WATER and dfn["stance"] != STANCE_WATER:
        return {"allowed": False, "status": "WATER_POSITION_REQUIRED", "build": POSITION_BUILD}

    if dfn["stance"] == STANCE_AIR:
        same_space = atk["stance"] == STANCE_AIR
        reachable = same_space or delivery in AIR_REACH_DELIVERIES or bool(effects & MOBILITY_WORLD_EFFECTS)
        if not reachable:
            return {"allowed": False, "status": "TARGET_OUT_OF_REACH_AIR", "build": POSITION_BUILD}

    if dfn["stance"] == STANCE_ELEVATED:
        same_anchor = atk["stance"] == STANCE_ELEVATED and _dict(atk.get("anchor")) == _dict(dfn.get("anchor"))
        reachable = same_anchor or atk["stance"] == STANCE_AIR or delivery in ELEVATED_REACH_DELIVERIES or bool(effects & MOBILITY_WORLD_EFFECTS)
        if not reachable:
            return {"allowed": False, "status": "TARGET_OUT_OF_REACH_ELEVATED", "build": POSITION_BUILD}

    return {"allowed": True, "status": "POSITION_REACH_VALID", "build": POSITION_BUILD}


def position_label(pokemon):
    pos = normalized_position(pokemon)
    if pos["stance"] == STANCE_WATER:
        return f"AGUA · {pos.get('medium_id') or ''}".strip(" ·")
    if pos["stance"] == STANCE_AIR:
        return f"AIRE · {pos.get('altitude') or 'LOW'}"
    if pos["stance"] == STANCE_ELEVATED:
        anchor = _text(_dict(pos.get("anchor")).get("name"))
        return f"ALTURA · {anchor}" if anchor else "ALTURA"
    cover = _dict(pos.get("cover"))
    if cover:
        return f"COBERTURA · {_text(cover.get('name')) or 'TERRENO'}"
    return "SUELO"
