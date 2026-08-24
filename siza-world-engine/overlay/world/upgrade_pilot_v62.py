from services.consequence_engine import consequence_rules, upsert_consequence_rule
from services.fact_goal_completion_engine import (
    FACT_GOAL_OBJECT_ACTION_BUILD,
    clear_completion_ledger,
    completion_rules,
    upsert_completion_rule,
)
from world.upgrade_pilot_v51 import MANIFEST_ID, MANIFEST_NAME
from world.upgrade_pilot_v57 import KNOWLEDGE_KEY
from world.upgrade_pilot_v60 import MARA_NPC_ID
from world.upgrade_pilot_v61 import GOAL_ID as V61_GOAL_ID, ensure_v61_pilot_content, reset_v61_playtest_state


PILOT_BUILD = "0.62.0-mara-manifest-object-verification"
ACTION_ID = "ACT-MARA-VERIFY-MANIFEST-DUPLICATE-001"
CONSEQUENCE_RULE_ID = "RULE-MARA-VERIFY-MANIFEST-DUPLICATE-001"
COMPLETION_RULE_ID = "FACT-GOAL-COMPLETE-MARA-VERIFY-MANIFEST-001"
VERIFIED_FIELD = "v062_mara_verified_duplicate"
LEDGER_PREFIX = f"FACT_GOAL_COMPLETION:{V61_GOAL_ID}:{COMPLETION_RULE_ID}"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _upsert_by_id(rows, replacement):
    output = []
    replaced = False
    wanted = str(replacement.get("id") or "")
    for raw in _plain_list(rows):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == wanted:
            output.append(dict(replacement))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(replacement))
    return output


def ensure_v62_pilot_content():
    previous = ensure_v61_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V61_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    mara = previous.get("mara")
    manifest = previous.get("manifest")
    destination = previous.get("destination")
    if not mara or not manifest or not destination:
        return {
            "success": False,
            "reason": "MARA_MANIFEST_OR_DESTINATION_MISSING",
            "build": PILOT_BUILD,
        }

    state = _plain_dict(getattr(manifest.db, "state", {}))
    state.setdefault(VERIFIED_FIELD, False)
    manifest.db.state = state

    action = {
        "id": ACTION_ID,
        "name": "Verificar hallazgo en el manifiesto",
        "activity": "verificando en el manifiesto la anotacion duplicada vinculada al relevo de cierre",
        "enabled": True,
        "knowledge_requirements": [
            {
                "knowledge_key": KNOWLEDGE_KEY,
                "min_level": 1,
                "name": "Hallazgo del relevo de cierre",
            }
        ],
        "object_state_requirements": [
            {
                "field": VERIFIED_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Verificacion de Mara aun pendiente",
            }
        ],
        "canon_status": "prototype",
        "metadata": {
            "purpose": "NPC fact-driven verification",
            "source_goal_id": V61_GOAL_ID,
        },
    }
    manifest.db.object_actions = _upsert_by_id(getattr(manifest.db, "object_actions", []), action)

    upsert_consequence_rule(
        {
            "id": CONSEQUENCE_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTOR",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "actor_npc_id": MARA_NPC_ID,
                "object_action_id": ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": VERIFIED_FIELD,
                    "op": "SET",
                    "value": True,
                }
            ],
        }
    )

    upsert_completion_rule(
        mara,
        {
            "id": COMPLETION_RULE_ID,
            "enabled": True,
            "goal_id": V61_GOAL_ID,
            "effect_type": "OBJECT_ACTION",
            "object_id": MANIFEST_ID,
            "object_name": MANIFEST_NAME,
            "object_action_id": ACTION_ID,
            "canon_status": "prototype",
        },
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "object_action_build": FACT_GOAL_OBJECT_ACTION_BUILD,
        "mara": mara,
        "manifest": manifest,
        "start": previous.get("mara_start"),
        "destination": destination,
        "goal_id": V61_GOAL_ID,
        "action_id": ACTION_ID,
        "consequence_rule_id": CONSEQUENCE_RULE_ID,
        "completion_rule_id": COMPLETION_RULE_ID,
        "verified_field": VERIFIED_FIELD,
    }


def reset_v62_playtest_state():
    install = ensure_v62_pilot_content()
    if not bool(install.get("success")):
        return install

    base_reset = reset_v61_playtest_state()
    mara = install.get("mara")
    manifest = install.get("manifest")

    state = _plain_dict(getattr(manifest.db, "state", {}))
    before = state.get(VERIFIED_FIELD)
    state[VERIFIED_FIELD] = False
    manifest.db.state = state
    ledger_removed = clear_completion_ledger(mara, prefix=LEDGER_PREFIX)

    return {
        "success": bool(base_reset.get("success")),
        "reason": "PLAYTEST_RESET" if base_reset.get("success") else base_reset.get("reason"),
        "build": PILOT_BUILD,
        "mara": mara,
        "manifest": manifest,
        "goal_removed": base_reset.get("goal_removed"),
        "verified_before": before,
        "verified_after": False,
        "ledger_removed": ledger_removed,
    }


def v62_completion_rule_count():
    install = ensure_v62_pilot_content()
    mara = install.get("mara") if install.get("success") else None
    return sum(
        1
        for row in completion_rules(mara)
        if str(row.get("id") or "") == COMPLETION_RULE_ID
    ) if mara else 0


def v62_consequence_rule_count():
    return sum(
        1
        for row in consequence_rules()
        if str(row.get("id") or "") == CONSEQUENCE_RULE_ID
    )
