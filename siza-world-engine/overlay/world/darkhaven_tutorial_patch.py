from services.consequence_engine import upsert_consequence_rule
from services.knowledge_fact_engine import set_knowledge_fact_status
from world.darkhaven_academy_seed import (
    GEAR_ACTION_ID,
    GEAR_RULE_ID,
    TRAINING_ACTION_ID,
    TRAINING_RULE_ID,
    _find_by_attr,
)


ORIENTATION_FACT_ID = "DH7-FACT-TUT-ORIENTATION-001"


def _install_player_neutral_rules():
    upsert_consequence_rule({
        "id": GEAR_RULE_ID,
        "enabled": True,
        "canon_status": "vertical_slice",
        "when": {
            "action_type": "OBJECT_ACTION_COMPLETED",
            "object_action_id": GEAR_ACTION_ID,
            "outcome": "COMPLETED",
        },
        "state_effects": [
            {"scope": "ACTION_OBJECT", "namespace": "state", "field": "completed", "op": "SET", "value": True},
            {"scope": "ACTION_SITE", "namespace": "world_state", "field": "darkhaven_ingreso_equipo_reclamado", "op": "SET", "value": True},
        ],
    })
    upsert_consequence_rule({
        "id": TRAINING_RULE_ID,
        "enabled": True,
        "canon_status": "vertical_slice",
        "when": {
            "action_type": "OBJECT_ACTION_COMPLETED",
            "object_action_id": TRAINING_ACTION_ID,
        },
        "state_effects": [
            {"scope": "ACTION_SITE", "namespace": "world_state", "field": "darkhaven_prueba_orlan_realizada", "op": "SET", "value": True},
        ],
    })


def apply():
    removed = []
    for exit_id in ("DH7-EXIT-011A", "DH7-EXIT-011B"):
        obj = _find_by_attr("exit_id", exit_id)
        if obj:
            removed.append({"exit_id": exit_id, "dbref": int(obj.id)})
            obj.delete()

    briefing_exit = _find_by_attr("exit_id", "DH7-EXIT-012A")
    if briefing_exit:
        briefing_exit.db.campaign_tags = ["DH-TUT-BRIEFING"]

    dino = _find_by_attr("npc_id", "NPC-DH7-DINO")
    dino_fact = None
    if dino:
        dino_fact = set_knowledge_fact_status(
            dino,
            ORIENTATION_FACT_ID,
            "RETRACTED",
            reason="DARKHAVEN_TUTORIAL_SOURCE_IS_SQUEEK",
        )

    squeek = _find_by_attr("npc_id", "NPC-DH7-SQUEEK")
    squeek_fact = None
    if squeek:
        squeek_fact = set_knowledge_fact_status(
            squeek,
            ORIENTATION_FACT_ID,
            "ACTIVE",
            reason="DARKHAVEN_TUTORIAL_ORIENTATION_SOURCE",
        )

    _install_player_neutral_rules()

    return {
        "status": "PATCHED",
        "removed_duplicate_exits": removed,
        "briefing_exit_dbref": int(briefing_exit.id) if briefing_exit else None,
        "dino_fact": dino_fact,
        "squeek_fact": squeek_fact,
        "player_neutral_rules": [GEAR_RULE_ID, TRAINING_RULE_ID],
    }
