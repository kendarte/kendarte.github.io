from services.consequence_engine import consequence_rules, upsert_consequence_rule
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v86 import ACTION_ID
from world.upgrade_pilot_v87 import ensure_v87_pilot_content


PILOT_BUILD = "0.88.0-site-local-npc-witness-knowledge"
RULE_ID = "RULE-V088-SITE-WITNESSES-LEARN-AUDIT-CROSSCHECK-001"
FACT_ID = "FACT-V088-SITE-WITNESS-AUDIT-CROSSCHECK-001"
KNOWLEDGE_KEY = "V088_SITE_WITNESS_AUDIT_CROSSCHECK"
FACT_TOPIC = "cruce del sello blanco presenciado en la pescaderia"
FACT_TEXT = (
    "El cruce del manifiesto y el sello blanco de auditoría fue completado en la Pescadería de Dársena."
)


def ensure_v88_pilot_content():
    previous = ensure_v87_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V87_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("site")
    manifest = previous.get("manifest")
    if not site or not manifest:
        return {
            "success": False,
            "reason": "SITE_OR_MANIFEST_MISSING",
            "build": PILOT_BUILD,
        }
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {
            "success": False,
            "reason": "MANIFEST_ID_MISMATCH",
            "build": PILOT_BUILD,
        }

    upsert_consequence_rule(
        {
            "id": RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "SITE_NPCS",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "COMPLETED",
            },
            "knowledge": {
                "knowledge_key": KNOWLEDGE_KEY,
                "mode": "MAX",
                "value": 1,
            },
            "knowledge_fact": {
                "id": FACT_ID,
                "topic": FACT_TOPIC,
                "aliases": [
                    "cruce del sello blanco",
                    "sello blanco presenciado",
                    "cruce del manifiesto presenciado",
                ],
                "text": FACT_TEXT,
                "knowledge_key": KNOWLEDGE_KEY,
                "required_level": 1,
                "canon_status": "prototype",
                "source": {
                    "kind": "DIRECT_SITE_WITNESS",
                    "site_room_id": "$site_room_id",
                    "site_name": "$site_name",
                    "object_id": "$object_id",
                    "object_name": "$object_name",
                },
                "learned_by": {
                    "mode": "SITE_PRESENCE",
                    "action_id": "$action_id",
                    "object_action_id": "$object_action_id",
                    "attempt_id": "$attempt_id",
                    "outcome": "$outcome",
                },
            },
        }
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "informant": previous.get("informant"),
        "mara": previous.get("mara"),
        "rule_id": RULE_ID,
        "fact_id": FACT_ID,
        "knowledge_key": KNOWLEDGE_KEY,
    }


def v88_rule_count():
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == RULE_ID)
