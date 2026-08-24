from evennia import search_object

from services.fact_goal_engine import FACT_GOAL_BUILD, remove_fact_goal, upsert_fact_goal_rule
from world.upgrade_pilot_v57 import FACT_ID
from world.upgrade_pilot_v58 import TARGET_QUERY, ensure_v58_pilot_context


PILOT_BUILD = "0.59.0-fact-driven-informant-behavior"
RULE_ID = "FACT-GOAL-TEST-INFORMANT-REPORT-DUPLICATE-001"
GOAL_ID = "GOAL-TEST-INFORMANT-REPORT-DUPLICATE-001"
TARGET_ROOM_ID = "CAR-KAL-DAR-006"
TARGET_ROOM_KEY = "Cantina de Turno"
GOAL_ACTIVITY = "llevando el hallazgo del manifiesto a la Cantina de Turno"


def _find_room():
    for obj in search_object(TARGET_ROOM_KEY):
        if str(getattr(obj.db, "room_id", "") or "") == TARGET_ROOM_ID:
            return obj
    return None


def ensure_v59_pilot_content():
    previous = ensure_v58_pilot_context()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V58_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    target = previous.get("target")
    destination = _find_room()
    if not target or not destination:
        return {
            "success": False,
            "reason": "TARGET_OR_DESTINATION_MISSING",
            "build": PILOT_BUILD,
        }

    upsert_fact_goal_rule(
        target,
        {
            "id": RULE_ID,
            "enabled": True,
            "fact_id": FACT_ID,
            "goal": {
                "id": GOAL_ID,
                "type": "EVENT",
                "priority": 150,
                "target_room_id": TARGET_ROOM_ID,
                "target_room_key": TARGET_ROOM_KEY,
                "activity": GOAL_ACTIVITY,
                "one_shot": True,
                "canon_status": "prototype",
            },
            "canon_status": "prototype",
        },
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "fact_goal_build": FACT_GOAL_BUILD,
        "site": previous.get("site"),
        "manifest": previous.get("manifest"),
        "target": target,
        "destination": destination,
        "rule_id": RULE_ID,
        "goal_id": GOAL_ID,
        "fact_id": FACT_ID,
    }


def reset_v59_playtest_state():
    install = ensure_v59_pilot_content()
    if not bool(install.get("success")):
        return install
    target = install.get("target")
    site = install.get("site")
    removed = remove_fact_goal(target, GOAL_ID)
    target.db.current_goal = None
    target.db.destination_id = None
    target.db.current_activity = None
    if site and target.location != site:
        target.move_to(site, quiet=True)
    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "target": target,
        "site": site,
        "goal_removed": removed,
    }
