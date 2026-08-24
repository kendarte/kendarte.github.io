from services.consequence_engine import consequence_rules, upsert_consequence_rule
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v55 import SYNCED_FIELD, ensure_v55_pilot_content


PILOT_BUILD = "0.56.0-player-knowledge-unlocks"
KNOWLEDGE_KEY = "V056_SEAL_CYCLE_PATTERN"
DEDUCE_ACTION_ID = "ACT-TEST-PESCADERIA-DEDUCIR-CICLO-001"
DEDUCE_RULE_ID = "RULE-TEST-PESCADERIA-DEDUCIR-CICLO-SUCCESS-001"
FOLLOW_ACTION_ID = "ACT-TEST-PESCADERIA-IDENTIFICAR-TURNO-001"
FOLLOW_RULE_ID = "RULE-TEST-PESCADERIA-IDENTIFICAR-TURNO-COMPLETE-001"
PRESENTATION_ID = "PRES-TEST-PESCADERIA-TURNO-IDENTIFICADO-001"
DEDUCED_FIELD = "seal_cycle_deduced"
SHIFT_FIELD = "stamp_shift_identified"
WORLD_SHIFT_FIELD = "v056_stamp_shift_identified"
PRESENTATION_TEXT = (
    "Con el ciclo de estampado ya comprendido, identificas el turno responsable: "
    "la segunda anotacion fue procesada durante el relevo de cierre de la darsena."
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


def ensure_v56_pilot_content():
    previous = ensure_v55_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V55_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("site")
    manifest = previous.get("manifest")
    if not site or not manifest:
        return {"success": False, "reason": "PERSISTENT_CONTENT_MISSING", "build": PILOT_BUILD}
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {"success": False, "reason": "MANIFEST_ID_MISMATCH", "build": PILOT_BUILD}

    state = _plain_dict(getattr(manifest.db, "state", {}))
    state.setdefault(DEDUCED_FIELD, False)
    state.setdefault(SHIFT_FIELD, False)
    manifest.db.state = state

    deduce_action = {
        "id": DEDUCE_ACTION_ID,
        "name": "Deducir ciclo de estampado",
        "input_phrases": ["deducir ciclo", "interpretar patron mecanico", "estudiar ciclo"],
        "enabled": True,
        "object_state_requirements": [
            {
                "field": SYNCED_FIELD,
                "op": "EQ",
                "value": True,
                "name": "Sellos sincronizados",
            },
            {
                "field": DEDUCED_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Ciclo aun no deducido",
            },
        ],
        "check": {
            "id": f"CHECK-{DEDUCE_ACTION_ID}",
            "trigger": "OBSTACLE",
            "mode": "DIRECT",
            "stat": "INT",
            "difficulty": 7,
        },
        "canon_status": "prototype",
    }
    follow_action = {
        "id": FOLLOW_ACTION_ID,
        "name": "Identificar turno de estampado",
        "input_phrases": ["identificar turno", "ubicar turno de estampado", "reconocer turno"],
        "enabled": True,
        "knowledge_requirements": [
            {
                "knowledge_key": KNOWLEDGE_KEY,
                "min_level": 1,
                "name": "Patron del ciclo de estampado",
            }
        ],
        "object_state_requirements": [
            {
                "field": DEDUCED_FIELD,
                "op": "EQ",
                "value": True,
                "name": "Ciclo deducido",
            },
            {
                "field": SHIFT_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Turno aun no identificado",
            },
        ],
        "canon_status": "prototype",
    }
    actions = _upsert_by_id(getattr(manifest.db, "object_actions", []), deduce_action)
    manifest.db.object_actions = _upsert_by_id(actions, follow_action)

    upsert_consequence_rule(
        {
            "id": DEDUCE_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTOR",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": DEDUCE_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "SUCCESS",
            },
            "knowledge": {
                "knowledge_key": KNOWLEDGE_KEY,
                "mode": "MAX",
                "value": 1,
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": DEDUCED_FIELD,
                    "op": "SET",
                    "value": True,
                }
            ],
        }
    )
    upsert_consequence_rule(
        {
            "id": FOLLOW_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": FOLLOW_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": SHIFT_FIELD,
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": WORLD_SHIFT_FIELD,
                    "op": "SET",
                    "value": 1,
                },
            ],
        }
    )

    presentation = {
        "id": PRESENTATION_ID,
        "text": PRESENTATION_TEXT,
        "enabled": True,
        "state_requirements": [
            {
                "field": WORLD_SHIFT_FIELD,
                "op": "EQ",
                "value": 1,
                "name": "Turno de estampado identificado",
            }
        ],
        "canon_status": "prototype",
    }
    site.db.state_presentations = _upsert_by_id(getattr(site.db, "state_presentations", []), presentation)

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "knowledge_key": KNOWLEDGE_KEY,
        "action_ids": [DEDUCE_ACTION_ID, FOLLOW_ACTION_ID],
        "rule_ids": [DEDUCE_RULE_ID, FOLLOW_RULE_ID],
        "presentation_id": PRESENTATION_ID,
    }


def reset_v56_world_state():
    install = ensure_v56_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = install.get("site")
    manifest = install.get("manifest")
    state = _plain_dict(getattr(manifest.db, "state", {}))
    state[DEDUCED_FIELD] = False
    state[SHIFT_FIELD] = False
    manifest.db.state = state

    world_state = _plain_dict(getattr(site.db, "world_state", {}))
    world_state.pop(WORLD_SHIFT_FIELD, None)
    site.db.world_state = world_state

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "deduced": False,
        "shift_identified": False,
    }


def v56_rule_count(rule_id):
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == str(rule_id or ""))
