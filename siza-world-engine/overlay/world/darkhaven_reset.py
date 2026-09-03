from evennia.accounts.models import AccountDB
from evennia.utils import utils

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


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _candidate_score(account, character):
    score = 0
    campaign = getattr(character.db, "dm_campaign_state", None)
    location = getattr(character, "location", None)
    room_id = str(getattr(getattr(location, "db", None), "room_id", "") or "")
    if getattr(account.db, "_last_puppet", None) == character:
        score += 2000
    if campaign and str(campaign.get("campaign_id") or "") == CAMPAIGN_ID:
        score += 1200
    if room_id.startswith("DH7-ROOM-"):
        score += 900
    elif location:
        score += 100
    if bool(getattr(account, "is_superuser", False)):
        score += 50
    return score


def _find_player():
    pairs = []
    for account in AccountDB.objects.all().order_by("id"):
        characters = list(utils.make_iter(account.characters))
        last = getattr(account.db, "_last_puppet", None)
        if last and last not in characters and last.access(account, "puppet"):
            characters.append(last)
        for character in characters:
            if character and character.access(account, "puppet"):
                pairs.append((account, character))
    if not pairs:
        return None
    account, character = max(
        pairs,
        key=lambda pair: (_candidate_score(pair[0], pair[1]), int(getattr(pair[1], "id", 0) or 0)),
    )
    account.db._last_puppet = character
    return character


def _reset_tutorial_world_state():
    gear = _find_by_attr("object_id", GEAR_OBJECT_ID)
    if gear:
        state = _plain_dict(getattr(gear.db, "state", {}))
        state["completed"] = False
        gear.db.state = state

    kitchen = _find_room(KITCHEN_ROOM_ID)
    if kitchen:
        state = _plain_dict(getattr(kitchen.db, "world_state", {}))
        state.pop("darkhaven_ingreso_equipo_reclamado", None)
        state.pop("nereida_ingreso_equipo_reclamado", None)
        kitchen.db.world_state = state

    training = _find_room(TRAINING_ROOM_ID)
    if training:
        state = _plain_dict(getattr(training.db, "world_state", {}))
        state.pop("darkhaven_prueba_orlan_realizada", None)
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
        return {"status": "PLAYER_NOT_FOUND"}

    entry = _find_room(ENTRY_ROOM_ID)
    if not entry:
        return {"status": "ENTRY_ROOM_NOT_FOUND", "room_id": ENTRY_ROOM_ID}

    _reset_tutorial_world_state()

    player.db.dm_campaign_state = {}
    player.db.object_action_history = []
    player.db.action_resolution_history = []
    player.db.current_action = None
    player.db.discovered_facts = []
    player.db.knowledge_facts = []
    player.db.knowledge = {}

    player.move_to(entry, quiet=True)
    started = start_campaign(player, DARKHAVEN_TUTORIAL_CAMPAIGN, force=True)
    player.db.darkhaven_intro_pending = True

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
