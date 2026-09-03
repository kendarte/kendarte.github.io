from evennia.accounts.models import AccountDB
from evennia.utils import utils

from services.dm_campaign_director import get_campaign_state
from services.knowledge_fact_engine import find_knowledge_fact
from world.darkhaven_academy_seed import (
    CAMPAIGN_ID,
    ENTRY_ROOM_ID,
    GEAR_ACTION_ID,
    GEAR_OBJECT_ID,
    TRAINING_ACTION_ID,
    TRAINING_OBJECT_ID,
    _find_by_attr,
    _find_room,
)


ORIENTATION_FACT_ID = "DH7-FACT-TUT-ORIENTATION-001"


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
    return max(
        pairs,
        key=lambda pair: (_candidate_score(pair[0], pair[1]), int(getattr(pair[1], "id", 0) or 0)),
    )[1]


def _actions(obj):
    try:
        return [dict(row) for row in list(getattr(obj.db, "object_actions", []) or [])]
    except Exception:
        return []


def _fact_status(entity, fact_id):
    fact = find_knowledge_fact(entity, fact_id) if entity else None
    return str((fact or {}).get("fact_status") or "").upper()


def validate():
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    player = _find_player()
    check("player-exists", bool(player), getattr(player, "key", None))

    entry = _find_room(ENTRY_ROOM_ID)
    check("entry-room-exists", bool(entry), int(entry.id) if entry else None)

    state = get_campaign_state(player) if player else {}
    check("darkhaven-campaign-active", str(state.get("campaign_id") or "") == CAMPAIGN_ID, state)
    check("tutorial-starts-at-arrival", str(state.get("active_beat_id") or "") == "DH-TUT-BEAT-ARRIVAL", state.get("active_beat_id"))
    check("player-at-darkhaven-gate", bool(player and entry and player.location == entry), str(getattr(getattr(player, "location", None), "key", "") or ""))

    arrival_exit = _find_by_attr("exit_id", "DH7-EXIT-001A")
    check("arrival-exit-tagged", bool(arrival_exit and "DH-TUT-ARRIVAL" in list(getattr(arrival_exit.db, "campaign_tags", []) or [])), list(getattr(arrival_exit.db, "campaign_tags", []) or []) if arrival_exit else None)

    briefing_exit = _find_by_attr("exit_id", "DH7-EXIT-012A")
    check("briefing-exit-tagged", bool(briefing_exit and "DH-TUT-BRIEFING" in list(getattr(briefing_exit.db, "campaign_tags", []) or [])), list(getattr(briefing_exit.db, "campaign_tags", []) or []) if briefing_exit else None)
    check("duplicate-training-exit-removed-a", _find_by_attr("exit_id", "DH7-EXIT-011A") is None)
    check("duplicate-training-exit-removed-b", _find_by_attr("exit_id", "DH7-EXIT-011B") is None)

    dino = _find_by_attr("npc_id", "NPC-DH7-DINO")
    squeek = _find_by_attr("npc_id", "NPC-DH7-SQUEEK")
    check("dino-exists", bool(dino), int(dino.id) if dino else None)
    check("squeek-exists", bool(squeek), int(squeek.id) if squeek else None)
    check("dino-does-not-short-circuit-orientation", _fact_status(dino, ORIENTATION_FACT_ID) == "RETRACTED", _fact_status(dino, ORIENTATION_FACT_ID))
    check("squeek-holds-orientation", _fact_status(squeek, ORIENTATION_FACT_ID) == "ACTIVE", _fact_status(squeek, ORIENTATION_FACT_ID))

    gear = _find_by_attr("object_id", GEAR_OBJECT_ID)
    gear_actions = _actions(gear)
    gear_action = next((row for row in gear_actions if str(row.get("id") or "") == GEAR_ACTION_ID), None)
    gear_tags = ((gear_action or {}).get("metadata") or {}).get("campaign_tags") or []
    check("gear-object-exists", bool(gear), int(gear.id) if gear else None)
    check("gear-action-tagged", "DH-TUT-GEAR" in list(gear_tags), gear_tags)

    training = _find_by_attr("object_id", TRAINING_OBJECT_ID)
    training_actions = _actions(training)
    training_action = next((row for row in training_actions if str(row.get("id") or "") == TRAINING_ACTION_ID), None)
    training_tags = ((training_action or {}).get("metadata") or {}).get("campaign_tags") or []
    training_check = (training_action or {}).get("check") or {}
    check("training-object-exists", bool(training), int(training.id) if training else None)
    check("training-action-tagged", "DH-TUT-TRAINING" in list(training_tags), training_tags)
    check("training-uses-real-direct-check", str(training_check.get("mode") or "").upper() == "DIRECT" and str(training_check.get("stat") or "").upper() == "COO", training_check)

    npcs_with_decks = []
    for npc_id in ("NPC-DH7-BASILIZA", "NPC-DH7-DRASHTON", "NPC-DH7-ROXY", "NPC-DH7-AXEL"):
        npc = _find_by_attr("npc_id", npc_id)
        profile = dict(getattr(npc.db, "combat_profile", {}) or {}) if npc else {}
        if npc and bool(profile.get("enabled")) and str(profile.get("deck_id") or ""):
            npcs_with_decks.append({"npc_id": npc_id, "deck_id": profile.get("deck_id")})
    check("fireteam7-combat-decks", len(npcs_with_decks) == 4, npcs_with_decks)

    failed = [row for row in checks if not row["passed"]]
    return {
        "status": "PASS" if not failed else "FAIL",
        "player": getattr(player, "key", None),
        "passed": len(checks) - len(failed),
        "total": len(checks),
        "failed": failed,
        "checks": checks,
    }
