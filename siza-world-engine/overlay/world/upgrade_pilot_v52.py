from evennia import search_object

from services.consequence_engine import consequence_rules, upsert_consequence_rule
from world.upgrade_pilot_v51 import (
    MANIFEST_ID,
    MANIFEST_VISIBLE_FIELD,
    PESCADERIA_ID,
    ensure_v51_pilot_content,
)


PILOT_BUILD = "0.52.0-direct-d6-player-resolution"
ANALYZE_ACTION_ID = "ACT-TEST-PESCADERIA-ANALIZAR-MANIFIESTO-001"
ANALYZE_RULE_ID = "RULE-TEST-PESCADERIA-ANALIZAR-MANIFIESTO-001"
PRESENTATION_ID = "PRES-TEST-PESCADERIA-MANIFIESTO-ANALIZADO-001"
ANALYZED_FIELD = "v052_manifest_analyzed"
PRESENTATION_TEXT = (
    "Al comparar las cifras del manifiesto, detectas una discrepancia: una partida de carga "
    "aparece registrada dos veces con el mismo sello de recepcion."
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


def ensure_v52_pilot_content():
    v51 = ensure_v51_pilot_content()
    if not bool(v51.get("success")):
        return {
            "success": False,
            "reason": v51.get("reason") or "V51_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = v51.get("site") or _find_site()
    manifest = v51.get("manifest")
    if not site or not manifest:
        return {"success": False, "reason": "PERSISTENT_CONTENT_MISSING", "build": PILOT_BUILD}
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {"success": False, "reason": "MANIFEST_ID_MISMATCH", "build": PILOT_BUILD}

    manifest_state = _plain_dict(getattr(manifest.db, "state", {}))
    manifest_state.setdefault("analyzed", False)
    manifest.db.state = manifest_state

    action = {
        "id": ANALYZE_ACTION_ID,
        "name": "Analizar manifiesto de carga",
        "input_phrases": ["analizar", "examinar", "descifrar"],
        "enabled": True,
        "object_state_requirements": [
            {
                "field": "analyzed",
                "op": "EQ",
                "value": False,
                "name": "Manifiesto sin analizar",
            }
        ],
        "check": {
            "id": f"CHECK-{ANALYZE_ACTION_ID}",
            "trigger": "OBSTACLE",
            "mode": "DIRECT",
            "stat": "PER",
            "difficulty": 7,
        },
        "canon_status": "prototype",
    }
    manifest.db.object_actions = _upsert_by_id(manifest.db.object_actions, action)

    upsert_consequence_rule(
        {
            "id": ANALYZE_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": ANALYZE_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "SUCCESS",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": "analyzed",
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": ANALYZED_FIELD,
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
                "field": ANALYZED_FIELD,
                "op": "EQ",
                "value": 1,
                "name": "Manifiesto analizado",
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
        "action_id": ANALYZE_ACTION_ID,
        "rule_id": ANALYZE_RULE_ID,
        "presentation_id": PRESENTATION_ID,
        "manifest_visible_field": MANIFEST_VISIBLE_FIELD,
    }


def reset_v52_playtest_state():
    install = ensure_v52_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = install.get("site")
    manifest = install.get("manifest")
    state = _plain_dict(getattr(manifest.db, "state", {}))
    state["analyzed"] = False
    manifest.db.state = state

    world_state = _plain_dict(getattr(site.db, "world_state", {}))
    world_state.pop(ANALYZED_FIELD, None)
    site.db.world_state = world_state

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "analyzed": False,
        "presentation_visible": False,
    }
