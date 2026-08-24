from services.fact_goal_engine import FACT_GOAL_BUILD, remove_fact_goal, upsert_fact_goal_rule
from world.upgrade_pilot_v57 import FACT_ID
from world.upgrade_pilot_v60 import ensure_v60_pilot_content


PILOT_BUILD = "0.61.0-propagated-fact-secondary-behavior"
RULE_ID = "FACT-GOAL-MARA-VERIFY-DUPLICATE-001"
GOAL_ID = "GOAL-MARA-VERIFY-DUPLICATE-001"
TARGET_ROOM_ID = "CAR-KAL-DAR-007"
TARGET_ROOM_KEY = "Pescaderia de Darsena"
GOAL_ACTIVITY = "volviendo a la pescaderia para verificar el manifiesto relacionado con el hallazgo recibido"


def ensure_v61_pilot_content():
    previous = ensure_v60_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V60_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    mara = previous.get("mara")
    site = previous.get("site")
    destination = previous.get("destination")
    if not mara or not site or not destination:
        return {
            "success": False,
            "reason": "MARA_SITE_OR_START_MISSING",
            "build": PILOT_BUILD,
        }

    upsert_fact_goal_rule(
        mara,
        {
            "id": RULE_ID,
            "enabled": True,
            "fact_id": FACT_ID,
            "goal": {
                "id": GOAL_ID,
                "type": "EVENT",
                "priority": 155,
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
        "informant": previous.get("informant"),
        "mara": mara,
        "manifest": previous.get("manifest"),
        "informant_site": site,
        "mara_start": destination,
        "destination": site,
        "rule_id": RULE_ID,
        "goal_id": GOAL_ID,
        "fact_id": FACT_ID,
    }


def reset_v61_playtest_state():
    install = ensure_v61_pilot_content()
    if not bool(install.get("success")):
        return install

    mara = install.get("mara")
    start = install.get("mara_start")
    removed = remove_fact_goal(mara, GOAL_ID)
    mara.db.current_goal = None
    mara.db.destination_id = None
    mara.db.current_activity = None
    if start and mara.location != start:
        mara.move_to(start, quiet=True)

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "mara": mara,
        "start": start,
        "destination": install.get("destination"),
        "goal_removed": removed,
    }
