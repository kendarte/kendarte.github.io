from evennia import search_object

from services.dm_campaign_director import start_campaign
from world.darkhaven_academy_seed import (
    CAMPAIGN_ID,
    ENTRY_ROOM_ID,
    GEAR_OBJECT_ID,
    KITCHEN_ROOM_ID,
    TRAINING_ROOM_ID,
    _find_by_attr,
    _find_room,
    install as install_darkhaven,
)
from world.darkhaven_tutorial_campaign import DARKHAVEN_TUTORIAL_CAMPAIGN
from world.darkhaven_tutorial_patch import apply as apply_tutorial_patch


PLAYER_KEY = "Nereida"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _find_player():
    rows = []
    for obj in search_object(PLAYER_KEY):
        if str(getattr(obj, "key", "") or "").lower() != PLAYER_KEY.lower():
            continue
        if bool(getattr(getattr(obj, "db", None), "is_npc", False)):
            continue
        rows.append(obj)
    if not rows:
        return None
    return sorted(rows, key=lambda obj: int(getattr(obj, "id", 0) or 0), reverse=True)[0]


def _reset_tutorial_world_state():
    gear = _find_by_attr("object_id", GEAR_OBJECT_ID)
    if gear:
        state = _plain_dict(getattr(gear.db, "state", {}))
        state["completed"] = False
        gear.db.state = state

    kitchen = _find_room(KITCHEN_ROOM_ID)
    if kitchen:
        state = _plain_dict(getattr(kitchen.db, "world_state", {}))
        state.pop("nereida_ingreso_equipo_reclamado", None)
        kitchen.db.world_state = state

    training = _find_room(TRAINING_ROOM_ID)
    if training:
        state = _plain_dict(getattr(training.db, "world_state", {}))
        state.pop("nereida_prueba_orlan_realizada", None)
        training.db.world_state = state


def reset():
    installed = install_darkhaven()
    if str(installed.get("status") or "") != "INSTALLED":
        return {"status": "INSTALL_FAILED", "install": installed}

    patched = apply_tutorial_patch()
    if str(patched.get("status") or "") != "PATCHED":
        return {"status": "PATCH_FAILED", "install": installed, "patch": patched}

    player = _find_player()
    if not player:
        return {"status": "PLAYER_NOT_FOUND", "player_key": PLAYER_KEY}

    entry = _find_room(ENTRY_ROOM_ID)
    if not entry:
        return {"status": "ENTRY_ROOM_NOT_FOUND", "room_id": ENTRY_ROOM_ID}

    _reset_tutorial_world_state()

    # Reset player-local campaign/tutorial progress, not the authored academy.
    player.db.dm_campaign_state = {}
    player.db.object_action_history = []
    player.db.action_resolution_history = []
    player.db.current_action = None
    player.db.discovered_facts = []
    player.db.knowledge_facts = []
    player.db.knowledge = {}

    player.move_to(entry, quiet=True)
    started = start_campaign(player, DARKHAVEN_TUTORIAL_CAMPAIGN, force=True)

    return {
        "status": "RESET",
        "campaign_id": CAMPAIGN_ID,
        "player": player.key,
        "player_dbref": int(player.id),
        "location": entry.key,
        "room_id": ENTRY_ROOM_ID,
        "campaign": started,
        "install": installed,
        "patch": patched,
    }
