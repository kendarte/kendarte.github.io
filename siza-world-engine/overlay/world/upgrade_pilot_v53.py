from evennia import search_object

from services.consequence_engine import consequence_rules, upsert_consequence_rule
from world.upgrade_pilot_v51 import MANIFEST_ID, PESCADERIA_ID
from world.upgrade_pilot_v52 import ensure_v52_pilot_content


PILOT_BUILD = "0.53.0-accumulate-d6-player-resolution"
RECONSTRUCT_ACTION_ID = "ACT-TEST-PESCADERIA-RECONSTRUIR-SECUENCIA-001"
PROGRESS_RULE_ID = "RULE-TEST-PESCADERIA-RECONSTRUIR-PROGRESS-001"
SETBACK_RULE_ID = "RULE-TEST-PESCADERIA-RECONSTRUIR-SETBACK-001"
COMPLETE_RULE_ID = "RULE-TEST-PESCADERIA-RECONSTRUIR-COMPLETE-001"
PRESENTATION_ID = "PRES-TEST-PESCADERIA-SECUENCIA-RECONSTRUIDA-001"
PROGRESS_FIELD = "route_progress"
COMPLETE_FIELD = "route_reconstructed"
WORLD_COMPLETE_FIELD = "v053_route_reconstructed"
PROGRESS_GOAL = 2
PRESENTATION_TEXT = (
    "Al ordenar los sellos y horarios del manifiesto, reconstruyes una secuencia coherente: "
    "la partida duplicada fue asentada en dos momentos distintos aunque conserva el mismo sello de recepcion."
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


def _find_site():
    for obj in search_object("Pescaderia de Darsena"):
        if str(getattr(obj.db, "room_id", "") or "") == PESCADERIA_ID:
            return obj
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


def ensure_v53_pilot_content():
    v52 = ensure_v52_pilot_content()
    if not bool(v52.get("success")):
        return {
            "success": False,
            "reason": v52.get("reason") or "V52_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = v52.get("site") or _find_site()
    manifest = v52.get("manifest")
    if not site or not manifest:
        return {"success": False, "reason": "PERSISTENT_CONTENT_MISSING", "build": PILOT_BUILD}
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {"success": False, "reason": "MANIFEST_ID_MISMATCH", "build": PILOT_BUILD}

    state = _plain_dict(getattr(manifest.db, "state", {}))
    state.setdefault(PROGRESS_FIELD, 0)
    state.setdefault(COMPLETE_FIELD, False)
    manifest.db.state = state

    action = {
        "id": RECONSTRUCT_ACTION_ID,
        "name": "Reconstruir secuencia del manifiesto",
        "input_phrases": ["reconstruir", "ordenar secuencia", "seguir registros"],
        "enabled": True,
        "object_state_requirements": [
            {
                "field": "analyzed",
                "op": "EQ",
                "value": True,
                "name": "Manifiesto analizado",
            },
            {
                "field": COMPLETE_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Secuencia sin reconstruir",
            },
        ],
        "check": {
            "id": f"CHECK-{RECONSTRUCT_ACTION_ID}",
            "trigger": "OBSTACLE",
            "mode": "ACCUMULATE",
            "stat": "INT",
            "difficulty": 7,
            "metadata": {
                "progress_field": PROGRESS_FIELD,
                "progress_goal": PROGRESS_GOAL,
                "progress_step": 1,
            },
        },
        "canon_status": "prototype",
    }
    manifest.db.object_actions = _upsert_by_id(manifest.db.object_actions, action)

    upsert_consequence_rule(
        {
            "id": PROGRESS_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": RECONSTRUCT_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "PROGRESS",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": PROGRESS_FIELD,
                    "op": "ADD",
                    "value": 1,
                }
            ],
        }
    )
    upsert_consequence_rule(
        {
            "id": SETBACK_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": RECONSTRUCT_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "SETBACK",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": PROGRESS_FIELD,
                    "op": "SUBTRACT",
                    "value": 1,
                }
            ],
        }
    )
    upsert_consequence_rule(
        {
            "id": COMPLETE_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": RECONSTRUCT_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "COMPLETE",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": PROGRESS_FIELD,
                    "op": "SET",
                    "value": PROGRESS_GOAL,
                },
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": COMPLETE_FIELD,
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": WORLD_COMPLETE_FIELD,
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
                "field": WORLD_COMPLETE_FIELD,
                "op": "EQ",
                "value": 1,
                "name": "Secuencia reconstruida",
            }
        ],
        "canon_status": "prototype",
    }
    site.db.state_presentations = _upsert_by_id(site.db.state_presentations, presentation)

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "action_id": RECONSTRUCT_ACTION_ID,
        "rule_ids": [PROGRESS_RULE_ID, SETBACK_RULE_ID, COMPLETE_RULE_ID],
        "presentation_id": PRESENTATION_ID,
    }


def reset_v53_playtest_state():
    install = ensure_v53_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = install.get("site")
    manifest = install.get("manifest")
    state = _plain_dict(getattr(manifest.db, "state", {}))
    state[PROGRESS_FIELD] = 0
    state[COMPLETE_FIELD] = False
    manifest.db.state = state

    world_state = _plain_dict(getattr(site.db, "world_state", {}))
    world_state.pop(WORLD_COMPLETE_FIELD, None)
    site.db.world_state = world_state

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "progress": 0,
        "goal": PROGRESS_GOAL,
        "complete": False,
        "presentation_visible": False,
    }
