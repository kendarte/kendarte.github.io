"""Translate successful movement-capable world moves into battle position state."""

from copy import deepcopy

from services.pokemon_battle_position_engine import (
    STANCE_AIR,
    STANCE_WATER,
    set_position,
)


MOVE_POSITION_BUILD = "0.1.0-world-move-position-followthrough"


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


def _effects(move):
    return {str(v).strip().upper() for v in _list(_dict(move).get("world_effects")) if str(v).strip()}


def apply_world_move_position_followthrough(battle, side, move, world_result, request=None):
    state = battle if isinstance(battle, dict) else {}
    result = _dict(world_result)
    if not bool(result.get("executed")):
        return {"applied": False, "status": "WORLD_MOVE_NOT_EXECUTED", "build": MOVE_POSITION_BUILD}
    pokemon = state.get("player" if _text(side).upper() == "PLAYER" else "enemy")
    if not isinstance(pokemon, dict):
        return {"applied": False, "status": "BATTLE_PARTICIPANT_MISSING", "build": MOVE_POSITION_BUILD}

    effects = _effects(move)
    name = _text(pokemon.get("name") or pokemon.get("species_name")) or "Pokémon"
    medium_id = _text(result.get("target_water_body_id"))

    if effects & {"SURF", "MOVE_WATER"} and medium_id:
        position = set_position(pokemon, {
            "stance": STANCE_WATER,
            "medium_id": medium_id,
            "medium_kind": "WATER",
            "anchor": {
                "object_id": result.get("target_object_id"),
                "dbref": result.get("target_dbref"),
                "name": result.get("target_name"),
            },
            "mobility_modifier": 1.12,
        })
        return {
            "applied": True,
            "status": "SURF_POSITION_ENTERED",
            "text": f"{name} queda desplazándose sobre {result.get('target_name') or 'el agua'}.",
            "position": deepcopy(position),
            "build": MOVE_POSITION_BUILD,
        }

    if "FLY" in effects:
        position = set_position(pokemon, {
            "stance": STANCE_AIR,
            "altitude": "LOW",
            "mobility_modifier": 1.08,
        })
        return {
            "applied": True,
            "status": "FLY_POSITION_ENTERED",
            "text": f"{name} queda en el aire.",
            "position": deepcopy(position),
            "build": MOVE_POSITION_BUILD,
        }

    return {"applied": False, "status": "NO_POSITION_FOLLOWTHROUGH", "build": MOVE_POSITION_BUILD}
