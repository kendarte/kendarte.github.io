from services.fact_share_rule_engine import fact_share_rules, upsert_fact_share_rule
from world.upgrade_pilot_v60 import MARA_NPC_ID
from world.upgrade_pilot_v88 import FACT_ID, ensure_v88_pilot_content


PILOT_BUILD = "0.89.0-witness-fact-social-propagation"
RULE_ID = "FACT-SHARE-V089-INFORMANT-TO-MARA-WITNESS-001"
PRIORITY = 950


def ensure_v89_pilot_content():
    previous = ensure_v88_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V88_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    informant = previous.get("informant")
    mara = previous.get("mara")
    site = previous.get("site")
    manifest = previous.get("manifest")
    if not informant or not mara or not site or not manifest:
        return {
            "success": False,
            "reason": "INFORMANT_MARA_SITE_OR_MANIFEST_MISSING",
            "build": PILOT_BUILD,
        }

    target_id = str(getattr(mara.db, "npc_id", "") or "").strip()
    if target_id != MARA_NPC_ID:
        return {
            "success": False,
            "reason": "MARA_ID_MISMATCH",
            "build": PILOT_BUILD,
        }

    upsert_fact_share_rule(
        informant,
        {
            "id": RULE_ID,
            "enabled": True,
            "fact_id": FACT_ID,
            "target_npc_id": MARA_NPC_ID,
            "priority": PRIORITY,
            "one_shot": True,
            "activity": "buscando a Mara para contarle lo presenciado durante el cruce del sello blanco",
            "canon_status": "prototype",
        },
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "informant": informant,
        "mara": mara,
        "fact_id": FACT_ID,
        "rule_id": RULE_ID,
        "target_npc_id": MARA_NPC_ID,
        "priority": PRIORITY,
    }


def v89_rule_count(informant):
    return sum(1 for row in fact_share_rules(informant) if str(row.get("id") or "") == RULE_ID)
