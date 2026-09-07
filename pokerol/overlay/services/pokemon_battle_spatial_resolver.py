"""Tag-driven spatial reasoning for POKEROL battles.

This is read-only. It does not roll dice, deal damage or mutate the room. It
turns authored move/object hard data into a path result and a bounded resolution
plan (normally zero/one roll, at most two for an elaborate maneuver).
"""

from services.pokemon_move_capability_engine import move_combat_profile


SPATIAL_RESOLVER_BUILD = "0.1.0-tag-driven-anime-space"

COVER_TAGS = {
    "SOLID_COVER", "COVER", "LOW_OBSTACLE", "HIGH_OBSTACLE", "OVERHEAD_COVER",
    "ROOF", "WALL", "FRAGILE_COVER", "TRANSPARENT_COVER",
}


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


def _tags(value):
    row = _dict(value)
    values = _list(row.get("tags")) + _list(row.get("materials")) + _list(row.get("battle_tags"))
    return {str(item or "").strip().upper() for item in values if str(item or "").strip()}


def _obstacle_packet(raw):
    row = _dict(raw)
    tags = _tags(row)
    return {
        "object_id": row.get("object_id"),
        "dbref": row.get("dbref"),
        "name": str(row.get("name") or row.get("object_id") or "obstáculo"),
        "tags": sorted(tags),
        "cover": bool(tags & COVER_TAGS),
        "low": "LOW_OBSTACLE" in tags,
        "high": bool(tags & {"HIGH_OBSTACLE", "WALL"}),
        "overhead": bool(tags & {"OVERHEAD_COVER", "ROOF"}),
        "fragile": bool(tags & {"FRAGILE_COVER", "FRAGILE_STRUCTURE", "BREAKABLE"}),
    }


def resolve_attack_path(move, obstacles=None, target=None, environment=None):
    """Resolve trajectory against already-authored obstacles between attacker/target."""
    profile = move_combat_profile(move)
    trajectory = profile.get("trajectory")
    rows = [_obstacle_packet(row) for row in _list(obstacles) if _obstacle_packet(row).get("cover")]
    env = _dict(environment)
    target_tags = _tags(target)

    if trajectory == "GROUND" and ("AIRBORNE" in target_tags or env.get("target_ground_contact") is False):
        return {
            "status": "PATH_INVALID",
            "reason": "TARGET_NOT_ON_GROUND",
            "clear": False,
            "profile": profile,
            "obstacles": rows,
            "build": SPATIAL_RESOLVER_BUILD,
        }

    if trajectory == "VERTICAL":
        roof = next((row for row in rows if row.get("overhead")), None)
        if roof:
            return {
                "status": "BLOCKED_OVERHEAD",
                "reason": "OVERHEAD_COVER",
                "clear": False,
                "blocking_object": roof,
                "profile": profile,
                "obstacles": rows,
                "build": SPATIAL_RESOLVER_BUILD,
            }
        return {"status": "CLEAR_VERTICAL", "clear": True, "profile": profile, "obstacles": rows, "build": SPATIAL_RESOLVER_BUILD}

    if not rows or trajectory in {"SELF", "MOVEMENT", "ZONE"}:
        return {"status": "CLEAR", "clear": True, "profile": profile, "obstacles": rows, "build": SPATIAL_RESOLVER_BUILD}

    blocker = rows[0]
    if trajectory == "BALLISTIC" and blocker.get("low") and not blocker.get("overhead"):
        return {
            "status": "CLEAR_ARC_OVER",
            "clear": True,
            "bypassed_object": blocker,
            "profile": profile,
            "obstacles": rows,
            "build": SPATIAL_RESOLVER_BUILD,
        }
    if trajectory == "CURVED" and not blocker.get("high") and not blocker.get("overhead"):
        return {
            "status": "CLEAR_CURVE_AROUND",
            "clear": True,
            "bypassed_object": blocker,
            "profile": profile,
            "obstacles": rows,
            "build": SPATIAL_RESOLVER_BUILD,
        }
    if trajectory == "GROUND" and not blocker.get("high"):
        return {
            "status": "CLEAR_UNDER",
            "clear": True,
            "bypassed_object": blocker,
            "profile": profile,
            "obstacles": rows,
            "build": SPATIAL_RESOLVER_BUILD,
        }

    return {
        "status": "BLOCKED_BY_COVER",
        "reason": "SOLID_PATH_OBSTRUCTION",
        "clear": False,
        "blocking_object": blocker,
        "can_damage_cover": bool(profile.get("power", 0) >= 3 and blocker.get("fragile")),
        "profile": profile,
        "obstacles": rows,
        "build": SPATIAL_RESOLVER_BUILD,
    }


def maneuver_resolution_plan(move, intent=None, path_result=None, contested=False, synchronized=False, progressive=False):
    """Suggest existing d6 checks without resolving them.

    Creativity selects the relevant challenge; the existing d6 engines remain
    authoritative. Micro-steps are collapsed so a turn never asks for more than
    two checks.
    """
    profile = move_combat_profile(move)
    intent = _dict(intent)
    path = _dict(path_result)
    elaborate = bool(intent.get("elaborate") or intent.get("environment_use") or intent.get("reposition"))
    checks = []

    if progressive:
        checks.append({"mode": "ACCUMULATE", "stat": str(intent.get("stat") or "COO").upper(), "reason": "PERSISTENT_WORLD_PROGRESS"})
    elif synchronized:
        checks.append({"mode": "SYNCHRONIZE", "stat": str(intent.get("stat") or "COO").upper(), "reason": "TRAINER_POKEMON_TIMING"})
    elif contested:
        checks.append({
            "mode": "CONFRONT",
            "stat": str(intent.get("stat") or ("AGI" if intent.get("reposition") else "COO")).upper(),
            "target_stat": str(intent.get("target_stat") or ("PER" if elaborate else "AGI")).upper(),
            "reason": "ACTIVE_OPPOSITION",
        })
    elif elaborate or (path and not path.get("clear", True)):
        checks.append({"mode": "DIRECT", "stat": str(intent.get("stat") or "COO").upper(), "reason": "ELABORATE_EXECUTION"})

    # A truly elaborate synchronized setup may still face one active opponent.
    # This is the only supported two-check shape: execution/timing + opposition.
    if elaborate and synchronized and contested and len(checks) < 2:
        checks.append({
            "mode": "CONFRONT",
            "stat": str(intent.get("contest_stat") or "AGI").upper(),
            "target_stat": str(intent.get("target_stat") or "PER").upper(),
            "reason": "ACTIVE_REACTION",
        })

    return {
        "checks": checks[:2],
        "roll_count": min(2, len(checks)),
        "move_profile": profile,
        "path": path,
        "build": SPATIAL_RESOLVER_BUILD,
    }
