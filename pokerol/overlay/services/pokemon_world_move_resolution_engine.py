"""POKEROL bridge from authored Pokémon move capability to anime-world physics."""

from services.anime_world_physics_engine import resolve_anime_physics
from services.pokemon_move_capability_engine import evaluate_world_move_use


def resolve_pokemon_world_move(pokemon, move, target=None, environment=None, intensity=1.0):
    gate = evaluate_world_move_use(
        pokemon,
        move,
        target=target,
        environment=environment,
    )
    if not gate.get("allowed"):
        return {
            "status": "WORLD_MOVE_REJECTED",
            "allowed": False,
            "gate": gate,
            "physics": None,
        }

    physics = resolve_anime_physics(
        move,
        target or {},
        environment=environment or {},
        intensity=intensity,
    )
    return {
        "status": "WORLD_MOVE_RESOLVED",
        "allowed": True,
        "gate": gate,
        "physics": physics,
        "proposed_target_state": (physics.get("target") or {}).get("environmental_state") or {},
        "proposed_environment_state": physics.get("environment") or {},
        "events": physics.get("events") or [],
        "area_impacts": physics.get("area_impacts") or [],
    }
