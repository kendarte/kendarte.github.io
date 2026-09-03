from evennia import search_object

from services.dm_campaign_director import start_campaign
from world.darkhaven_academy_seed import (
    CAMPAIGN_ID,
    ENTRY_ROOM_ID,
    GEAR_OBJECT_ID,
    KITCHEN_ROOM_ID,
    TRAINING_ROOM_ID,
    install as install_darkhaven,
)
from world.darkhaven_tutorial_campaign import DARKHAVEN_TUTORIAL_CAMPAIGN


PLAYER_KEY = "Nereida"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _find_exact(attr_name, value):
    wanted = str(value or "")
    for obj in search_object("*"):
        if str(getattr(getattr(obj, "db", None), attr_name, "") or "") == wanted:
            return obj
    return None


def _find_by_attr_candidates(attr_name, value):
    wanted = str(value or "")
    output = []
    try:
        from evennia.objects.models import ObjectDB
        for obj in ObjectDB.objects.all():
            if str(getattr(getattr(obj, "db", None), attr_name, "") or "") == wanted:
                output.append(obj)
    except Exception:
        pass
    return output


def _find_room(room_id):
    rows = _find_by_attr_candidates("room_id", room_id)
    return sorted(rows, key=lambda obj: int(getattr(obj, "id", 0) or 0))[0] if rows else None


def _find_object(object_id):
    rows = _find_by_attr_candidates("object_id", object_id)
    return sorted(rows, key=lambda obj: int(getattr(obj, "id", 0) or 0))[0] if rows else None


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
    gear = _find_object(GEAR_OBJECT_ID)
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

    player = _find_player()
    if not player:
        return {"status": "PLAYER_NOT_FOUND", "player_key": PLAYER_KEY}

    entry = _find_room(ENTRY_ROOM_ID)
    if not entry:
        return {"status": "ENTRY_ROOM_NOT_FOUND", "room_id": ENTRY_ROOM_ID}

    _reset_tutorial_world_state()

    # Reset only player-local campaign/tutorial progression. Persistent authored
    # world content remains installed and reusable.
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
    }
