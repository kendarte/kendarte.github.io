from services.consequence_engine import consequence_rules, upsert_consequence_rule
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v53 import COMPLETE_FIELD, ensure_v53_pilot_content
from world.upgrade_pilot_v54 import ensure_v54_pilot_content


PILOT_BUILD = "0.55.0-synchronize-d6-player-resolution"
SYNC_ACTION_ID = "ACT-TEST-PESCADERIA-SINCRONIZAR-SELLOS-001"
SYNC_RULE_ID = "RULE-TEST-PESCADERIA-SINCRONIZAR-SELLOS-SYNC-001"
PRESENTATION_ID = "PRES-TEST-PESCADERIA-SELLOS-SINCRONIZADOS-001"
SYNCED_FIELD = "seal_timing_synced"
WORLD_SYNCED_FIELD = "v055_seal_timing_synced"
SYNC_STAT = "COO"
SYNC_PARITY = "EVEN"
PRESENTATION_TEXT = (
    "Al hacer coincidir la cadencia de los sellos con los horarios reconstruidos, detectas un patron: "
    "la segunda anotacion fue estampada durante el mismo ciclo mecanico que la primera."
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


def ensure_v55_pilot_content():
    v54 = ensure_v54_pilot_content()
    v53 = ensure_v53_pilot_content()
    if not bool(v54.get("success")) or not bool(v53.get("success")):
        return {
            "success": False,
            "reason": v54.get("reason") or v53.get("reason") or "PREVIOUS_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = v53.get("site")
    manifest = v53.get("manifest")
    if not site or not manifest:
        return {"success": False, "reason": "PERSISTENT_CONTENT_MISSING", "build": PILOT_BUILD}
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {"success": False, "reason": "MANIFEST_ID_MISMATCH", "build": PILOT_BUILD}

    state = _plain_dict(getattr(manifest.db, "state", {}))
    state.setdefault(SYNCED_FIELD, False)
    manifest.db.state = state

    action = {
        "id": SYNC_ACTION_ID,
        "name": "Sincronizar sellos del manifiesto",
        "input_phrases": ["sincronizar sellos", "alinear sellos", "seguir cadencia"],
        "enabled": True,
        "object_state_requirements": [
            {
                "field": COMPLETE_FIELD,
                "op": "EQ",
                "value": True,
                "name": "Secuencia reconstruida",
            },
            {
                "field": SYNCED_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Sellos aun no sincronizados",
            },
        ],
        "check": {
            "id": f"CHECK-{SYNC_ACTION_ID}",
            "trigger": "SYNCHRONY",
            "mode": "SYNCHRONIZE",
            "stat": SYNC_STAT,
            "metadata": {
                "parity": SYNC_PARITY,
            },
        },
        "canon_status": "prototype",
    }
    manifest.db.object_actions = _upsert_by_id(getattr(manifest.db, "object_actions", []), action)

    upsert_consequence_rule(
        {
            "id": SYNC_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": SYNC_ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "SYNC",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": SYNCED_FIELD,
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": WORLD_SYNCED_FIELD,
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
                "field": WORLD_SYNCED_FIELD,
                "op": "EQ",
                "value": 1,
                "name": "Sellos sincronizados",
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
        "action_id": SYNC_ACTION_ID,
        "rule_id": SYNC_RULE_ID,
        "presentation_id": PRESENTATION_ID,
        "parity": SYNC_PARITY,
    }


def reset_v55_playtest_state():
    install = ensure_v55_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = install.get("site")
    manifest = install.get("manifest")
    state = _plain_dict(getattr(manifest.db, "state", {}))
    state[SYNCED_FIELD] = False
    manifest.db.state = state

    world_state = _plain_dict(getattr(site.db, "world_state", {}))
    world_state.pop(WORLD_SYNCED_FIELD, None)
    site.db.world_state = world_state

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "synced": False,
        "parity": SYNC_PARITY,
    }


def v55_rule_count():
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == SYNC_RULE_ID)
