from services.consequence_engine import consequence_rules, upsert_consequence_rule
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v56 import KNOWLEDGE_KEY as V56_KNOWLEDGE_KEY, SHIFT_FIELD, ensure_v56_pilot_content


PILOT_BUILD = "0.57.0-persistent-player-knowledge-facts"
FACT_ID = "FACT-PESCADERIA-DUPLICADO-RELEVO-001"
KNOWLEDGE_KEY = "V057_DUPLICATE_SHIFT_LINK"
ACTION_ID = "ACT-TEST-PESCADERIA-CONSOLIDAR-HALLAZGO-001"
RULE_ID = "RULE-TEST-PESCADERIA-CONSOLIDAR-HALLAZGO-SUCCESS-001"
RECORDED_FIELD = "v057_duplicate_shift_fact_recorded"
FACT_TOPIC = "Vinculo entre la anotacion duplicada y el relevo de cierre"
FACT_TEXT = (
    "La anotacion duplicada del manifiesto fue procesada durante el relevo de cierre de la darsena, "
    "vinculando el segundo registro con ese turno operativo."
)


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


def ensure_v57_pilot_content():
    previous = ensure_v56_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V56_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("site")
    manifest = previous.get("manifest")
    if not site or not manifest:
        return {"success": False, "reason": "PERSISTENT_CONTENT_MISSING", "build": PILOT_BUILD}
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {"success": False, "reason": "MANIFEST_ID_MISMATCH", "build": PILOT_BUILD}

    state = _plain_dict(getattr(manifest.db, "state", {}))
    state.setdefault(RECORDED_FIELD, False)
    manifest.db.state = state

    action = {
        "id": ACTION_ID,
        "name": "Consolidar hallazgo del relevo",
        "input_phrases": ["consolidar hallazgo", "documentar hallazgo", "confirmar vinculo del relevo"],
        "enabled": True,
        "knowledge_requirements": [
            {
                "knowledge_key": V56_KNOWLEDGE_KEY,
                "min_level": 1,
                "name": "Patron del ciclo de estampado",
            }
        ],
        "object_state_requirements": [
            {
                "field": SHIFT_FIELD,
                "op": "EQ",
                "value": True,
                "name": "Turno de estampado identificado",
            },
            {
                "field": RECORDED_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Hallazgo aun no consolidado",
            },
        ],
        "check": {
            "id": f"CHECK-{ACTION_ID}",
            "trigger": "OBSTACLE",
            "mode": "DIRECT",
            "stat": "INT",
            "difficulty": 8,
        },
        "canon_status": "prototype",
    }
    manifest.db.object_actions = _upsert_by_id(getattr(manifest.db, "object_actions", []), action)

    upsert_consequence_rule(
        {
            "id": RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTOR",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "SUCCESS",
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
                    "object_name": "Manifiesto de carga de prueba",
                    "site_room_id": "$site_room_id",
                    "site_name": "$site_name",
                },
                "learned_by": {
                    "object_action_id": "$object_action_id",
                    "attempt_id": "$attempt_id",
                    "provider": "$provider",
                    "outcome": "$outcome",
                },
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": RECORDED_FIELD,
                    "op": "SET",
                    "value": True,
                }
            ],
        }
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "action_id": ACTION_ID,
        "rule_id": RULE_ID,
        "fact_id": FACT_ID,
        "knowledge_key": KNOWLEDGE_KEY,
    }


def reset_v57_world_state():
    install = ensure_v57_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    manifest = install.get("manifest")
    state = _plain_dict(getattr(manifest.db, "state", {}))
    state[RECORDED_FIELD] = False
    manifest.db.state = state
    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "site": install.get("site"),
        "manifest": manifest,
        "recorded": False,
    }


def v57_rule_count():
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == RULE_ID)
