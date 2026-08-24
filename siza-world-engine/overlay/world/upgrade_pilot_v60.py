from evennia import search_tag

from services.fact_goal_completion_engine import (
    FACT_GOAL_COMPLETION_BUILD,
    clear_completion_ledger,
    completion_rules,
    upsert_completion_rule,
)
from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import remove_knowledge_fact
from services.fact_goal_engine import remove_fact_goal
from world.upgrade_pilot_v57 import FACT_ID, KNOWLEDGE_KEY
from world.upgrade_pilot_v59 import GOAL_ID, ensure_v59_pilot_content


PILOT_BUILD = "0.60.0-fact-propagation-chain"
COMPLETION_RULE_ID = "FACT-GOAL-COMPLETE-TEST-INFORMANT-SHARE-MARA-001"
MARA_NPC_ID = "NPC-KAL-DAR-MARA-001"
MARA_NAME = "Mara Vensal"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
LEDGER_PREFIX = f"FACT_GOAL_COMPLETION:{GOAL_ID}:"


def _find_npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "").strip() == wanted:
            return obj
    return None


def ensure_v60_pilot_content():
    previous = ensure_v59_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V59_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    informant = previous.get("target")
    destination = previous.get("destination")
    mara = _find_npc_by_id(MARA_NPC_ID)
    if not informant or not destination or not mara:
        return {
            "success": False,
            "reason": "INFORMANT_DESTINATION_OR_MARA_MISSING",
            "build": PILOT_BUILD,
        }

    upsert_completion_rule(
        informant,
        {
            "id": COMPLETION_RULE_ID,
            "enabled": True,
            "goal_id": GOAL_ID,
            "effect_type": "SHARE_FACT",
            "fact_id": FACT_ID,
            "target_npc_id": MARA_NPC_ID,
            "canon_status": "prototype",
        },
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "completion_build": FACT_GOAL_COMPLETION_BUILD,
        "site": previous.get("site"),
        "manifest": previous.get("manifest"),
        "informant": informant,
        "destination": destination,
        "mara": mara,
        "goal_id": GOAL_ID,
        "fact_id": FACT_ID,
        "completion_rule_id": COMPLETION_RULE_ID,
    }


def reset_v60_playtest_state():
    install = ensure_v60_pilot_content()
    if not bool(install.get("success")):
        return install

    informant = install.get("informant")
    mara = install.get("mara")
    site = install.get("site")
    destination = install.get("destination")

    goal_removed = remove_fact_goal(informant, GOAL_ID)
    ledger_removed = clear_completion_ledger(informant, prefix=LEDGER_PREFIX)
    informant.db.current_goal = None
    informant.db.destination_id = None
    informant.db.current_activity = None

    levels = knowledge_levels(mara)
    mara_knowledge_before = levels.pop(KNOWLEDGE_KEY, None)
    mara.db.knowledge = levels
    mara_fact_removed = remove_knowledge_fact(mara, FACT_ID)

    if site and informant.location != site:
        informant.move_to(site, quiet=True)
    if destination and mara.location != destination:
        mara.move_to(destination, quiet=True)

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "informant": informant,
        "mara": mara,
        "site": site,
        "destination": destination,
        "goal_removed": goal_removed,
        "ledger_removed": ledger_removed,
        "mara_knowledge_before": mara_knowledge_before,
        "mara_fact_removed": mara_fact_removed,
        "completion_rule_count": sum(
            1
            for row in completion_rules(informant)
            if str(row.get("id") or "") == COMPLETION_RULE_ID
        ),
    }
