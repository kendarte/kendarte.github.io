from services.consequence_engine import consequence_rules, upsert_consequence_rule
from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import remove_knowledge_fact
from world.upgrade_pilot_v51 import MANIFEST_ID, MANIFEST_NAME
from world.upgrade_pilot_v60 import MARA_NPC_ID
from world.upgrade_pilot_v62 import ACTION_ID as V62_ACTION_ID, ensure_v62_pilot_content, reset_v62_playtest_state


PILOT_BUILD = "0.63.0-npc-self-discovered-knowledge-fact"
FACT_ID = "FACT-PESCADERIA-MARA-DIRECT-VERIFICATION-001"
KNOWLEDGE_KEY = "V063_MANIFEST_DIRECT_VERIFICATION"
RULE_ID = "RULE-MARA-VERIFY-MANIFEST-LEARN-FACT-001"
FACT_TOPIC = "Verificacion directa del manifiesto por Mara"
FACT_TEXT = (
    "Mara verifico personalmente en el manifiesto original que la anotacion duplicada esta presente "
    "en el documento y corresponde al registro vinculado al relevo de cierre."
)


def ensure_v63_pilot_content():
    previous = ensure_v62_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V62_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    mara = previous.get("mara")
    manifest = previous.get("manifest")
    if not mara or not manifest:
        return {
            "success": False,
            "reason": "MARA_OR_MANIFEST_MISSING",
            "build": PILOT_BUILD,
        }

    upsert_consequence_rule(
        {
            "id": RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTOR",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "actor_npc_id": MARA_NPC_ID,
                "object_action_id": V62_ACTION_ID,
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
                "text": FACT_TEXT,
                "knowledge_key": KNOWLEDGE_KEY,
                "required_level": 1,
                "canon_status": "prototype",
                "source": {
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

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "mara": mara,
        "manifest": manifest,
        "start": previous.get("start"),
        "destination": previous.get("destination"),
        "v62_goal_id": previous.get("goal_id"),
        "v62_action_id": V62_ACTION_ID,
        "fact_id": FACT_ID,
        "knowledge_key": KNOWLEDGE_KEY,
        "rule_id": RULE_ID,
    }


def reset_v63_playtest_state():
    install = ensure_v63_pilot_content()
    if not bool(install.get("success")):
        return install

    base = reset_v62_playtest_state()
    mara = install.get("mara")
    levels = knowledge_levels(mara)
    knowledge_before = levels.pop(KNOWLEDGE_KEY, None)
    mara.db.knowledge = levels
    fact_removed = remove_knowledge_fact(mara, FACT_ID)

    return {
        "success": bool(base.get("success")),
        "reason": "PLAYTEST_RESET" if base.get("success") else base.get("reason"),
        "build": PILOT_BUILD,
        "mara": mara,
        "manifest": install.get("manifest"),
        "knowledge_before": knowledge_before,
        "fact_removed": fact_removed,
        "verified_after": base.get("verified_after"),
        "goal_removed": base.get("goal_removed"),
    }


def v63_rule_count():
    return sum(
        1
        for row in consequence_rules()
        if str(row.get("id") or "") == RULE_ID
    )
