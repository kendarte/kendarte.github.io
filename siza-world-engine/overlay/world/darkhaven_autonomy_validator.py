"""Read-only deployment checks for the bounded Darkhaven autonomy slice."""

import inspect

from services.actor_registry import siza_npcs
from services.job_engine import collect_job_candidates
from services.npc_decision import collect_candidates
from services.npc_simulation import find_path
from services.relationship_engine import collect_relationship_candidates
from services.world_event_engine import collect_event_candidates, refresh_world_event_rules
from typeclasses.world_tick import world_tick_state
from world import darkhaven_autonomy_patch as autonomy


def _npc(npc_id):
    return autonomy._find_npc(npc_id)


def validate():
    """Inspect installed Darkhaven autonomy without creating scripts or mutating actor attributes."""
    tick = world_tick_state()
    results = {
        "world_tick_exists": bool(tick.get("exists")),
        "world_tick_unique": int(tick.get("duplicate_count", 0)) == 0,
        "selected_npcs": {},
        "jobs": False,
        "event_candidate": False,
        "relationship_candidate": False,
        "fact_share_resolvable": False,
        "movement_path": False,
        "no_kalnaj_dependency": True,
    }

    selected = []
    for npc_id in sorted(autonomy.AUTONOMY_NPC_IDS):
        npc = _npc(npc_id)
        config = autonomy.AUTONOMY[npc_id]
        routine_rooms = [entry.get("room_id") for entry in list(getattr(npc.db, "routine", []) or [])] if npc else []
        room_ids = [config["home_room_id"], config["work_room_id"], config["rest_room_id"]]
        row = {
            "exists": bool(npc),
            "simulation_enabled": bool(npc and npc.db.simulation_enabled),
            "decision_enabled": bool(npc and npc.db.decision_enabled),
            "locations_exist": all(autonomy._find_room(room_id) for room_id in room_ids),
            "routine_rooms_exist": bool(routine_rooms) and all(autonomy._find_room(room_id) for room_id in routine_rooms),
        }
        results["selected_npcs"][npc_id] = row
        if npc:
            selected.append(npc)

    for npc in selected:
        if collect_job_candidates(npc):
            results["jobs"] = True
        candidates = collect_candidates(npc)
        if candidates:
            results["movement_path"] = results["movement_path"] or any(
                item.get("target_room_id") and autonomy._find_room(item.get("target_room_id"))
                and find_path(npc.location, autonomy._find_room(item.get("target_room_id"))) is not None
                for item in candidates
            )

    refresh_world_event_rules()
    squeek = _npc("NPC-DH7-SQUEEK")
    if squeek:
        event_rows = collect_event_candidates(squeek)
        social_rows = collect_relationship_candidates(squeek)
        results["event_candidate"] = bool(event_rows)
        results["relationship_candidate"] = bool(social_rows)
        results["fact_share_resolvable"] = any(
            row.get("relationship_kind") == "SHARE_FACT" and row.get("target_room_id")
            for row in social_rows
        )

    from services import actor_registry, npc_simulation
    for module in (actor_registry, npc_simulation):
        if "kalnaj_pilot_v03_entities" in inspect.getsource(module):
            results["no_kalnaj_dependency"] = False

    required = [
        results["world_tick_exists"],
        results["world_tick_unique"],
        results["jobs"],
        results["event_candidate"],
        results["relationship_candidate"],
        results["fact_share_resolvable"],
        results["movement_path"],
        results["no_kalnaj_dependency"],
    ]
    required.extend(all(row.values()) for row in results["selected_npcs"].values())
    results["status"] = "VALID" if all(required) else "INVALID"
    results["selected_count"] = len(selected)
    results["available_siza_npcs"] = len(siza_npcs())
    results["tick"] = tick
    return results
