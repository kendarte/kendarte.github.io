from evennia import search_tag

from services.consequence_engine import consequence_rules, upsert_consequence_rule
from services.fact_goal_engine import fact_goal_rules, upsert_fact_goal_rule
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v60 import MARA_NPC_ID
from world.upgrade_pilot_v86 import ACTION_ID, ensure_v86_pilot_content


PILOT_BUILD = "0.87.0-player-world-consequence-teaches-npc-fact-goal"
RULE_ID = "RULE-V087-MARA-LEARNS-AUDIT-CROSSCHECK-001"
FACT_ID = "FACT-V087-MARA-AUDIT-CROSSCHECK-001"
KNOWLEDGE_KEY = "V087_MARA_AUDIT_CROSSCHECK"
FACT_TOPIC = "confirmacion del cruce del sello blanco"
FACT_TEXT = (
    "El cruce del manifiesto confirmó que el sello blanco de auditoría coincide con el cierre del inventario nocturno."
)
GOAL_RULE_ID = "FACT-GOAL-V087-MARA-CARRY-AUDIT-CROSSCHECK-001"
GOAL_ID = "GOAL-V087-MARA-CARRY-AUDIT-CROSSCHECK-001"
TARGET_ROOM_ID = "CAR-KAL-DAR-004"
TARGET_ROOM_KEY = "Calle de Servicio"
GOAL_ACTIVITY = "saliendo de la pescaderia para llevar la confirmacion del sello al circuito de servicio"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"


def _find_npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "").strip() == wanted:
            return obj
    return None


def ensure_v87_pilot_content():
    previous = ensure_v86_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V86_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("site")
    manifest = previous.get("manifest")
    mara = _find_npc_by_id(MARA_NPC_ID)
    if not site or not manifest or not mara:
        return {
            "success": False,
            "reason": "SITE_MANIFEST_OR_MARA_MISSING",
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
            "recipient_mode": "EXPLICIT",
            "recipient_ids": [MARA_NPC_ID],
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
                    "confirmacion del sello",
                    "inventario nocturno confirmado",
                ],
                "text": FACT_TEXT,
                "knowledge_key": KNOWLEDGE_KEY,
                "required_level": 1,
                "canon_status": "prototype",
                "source": {
                    "kind": "WORLD_CONSEQUENCE",
                    "object_id": "$object_id",
                    "object_name": "$object_name",
                    "site_room_id": "$site_room_id",
                    "site_name": "$site_name",
                },
                "learned_by": {
                    "action_id": "$action_id",
                    "object_action_id": "$object_action_id",
                    "attempt_id": "$attempt_id",
                    "outcome": "$outcome",
                },
            },
        }
    )

    upsert_fact_goal_rule(
        mara,
        {
            "id": GOAL_RULE_ID,
            "enabled": True,
            "fact_id": FACT_ID,
            "goal": {
                "id": GOAL_ID,
                "type": "EVENT",
                "priority": 900,
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
        "site": site,
        "manifest": manifest,
        "informant": previous.get("informant"),
        "mara": mara,
        "action_id": ACTION_ID,
        "rule_id": RULE_ID,
        "fact_id": FACT_ID,
        "knowledge_key": KNOWLEDGE_KEY,
        "goal_rule_id": GOAL_RULE_ID,
        "goal_id": GOAL_ID,
        "target_room_id": TARGET_ROOM_ID,
        "target_room_key": TARGET_ROOM_KEY,
    }


def v87_rule_count():
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == RULE_ID)


def v87_goal_rule_count(mara):
    return sum(1 for row in fact_goal_rules(mara) if str(row.get("id") or "") == GOAL_RULE_ID)
