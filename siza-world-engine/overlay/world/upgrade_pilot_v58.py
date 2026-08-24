from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import remove_knowledge_fact
from services.npc_simulation import find_npc
from world.upgrade_pilot_v57 import FACT_ID, KNOWLEDGE_KEY, ensure_v57_pilot_content


PILOT_BUILD = "0.58.0-persistent-fact-transfer"
TARGET_QUERY = "Informante C"
TARGET_NPC_ID = "TEST-NPC-KAL-DAR-INFORMANT-C"


def ensure_v58_pilot_context():
    previous = ensure_v57_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V57_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("site")
    target = find_npc(TARGET_QUERY)
    if not site or not target:
        return {
            "success": False,
            "reason": "TARGET_OR_SITE_MISSING",
            "build": PILOT_BUILD,
        }
    if str(getattr(target.db, "npc_id", "") or "") != TARGET_NPC_ID:
        return {
            "success": False,
            "reason": "TARGET_NPC_ID_MISMATCH",
            "build": PILOT_BUILD,
        }
    if target.location != site:
        target.move_to(site, quiet=True)

    return {
        "success": True,
        "reason": "READY",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": previous.get("manifest"),
        "target": target,
        "fact_id": FACT_ID,
        "knowledge_key": KNOWLEDGE_KEY,
    }


def reset_v58_target_fact():
    context = ensure_v58_pilot_context()
    if not bool(context.get("success")):
        return context

    target = context.get("target")
    levels = knowledge_levels(target)
    before = levels.pop(KNOWLEDGE_KEY, None)
    target.db.knowledge = levels
    fact_removed = remove_knowledge_fact(target, FACT_ID)
    return {
        **context,
        "reason": "TARGET_FACT_RESET",
        "knowledge_before": before,
        "fact_removed": fact_removed,
    }
