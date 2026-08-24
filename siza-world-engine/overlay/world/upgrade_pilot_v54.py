from services.action_resolution_engine import adventure_stats
from services.consequence_engine import consequence_rules, upsert_consequence_rule
from services.npc_simulation import find_npc
from world.upgrade_pilot_v53 import ensure_v53_pilot_content


PILOT_BUILD = "0.54.0-confront-d6-player-resolution"
TARGET_QUERY = "Informante C"
CONFRONT_ACTION_ID = "ACT-TEST-PESCADERIA-PRESIONAR-INFORMANTE-001"
CONFRONT_RULE_ID = "RULE-TEST-PESCADERIA-PRESIONAR-INFORMANTE-WIN-001"
PRESENTATION_ID = "PRES-TEST-PESCADERIA-INFORMANTE-CEDIO-001"
CONFRONTED_FIELD = "v054_pressure_conceded"
WORLD_CONFRONTED_FIELD = "v054_informant_conceded"
TARGET_STAT = "PSI"
DEFAULT_TARGET_STAT_VALUE = 3
PRESENTATION_TEXT = (
    "El informante evita sostenerte la mirada. Tras la confrontacion, ha cedido lo suficiente como para que sus contradicciones queden en evidencia."
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


def ensure_v54_pilot_content():
    previous = ensure_v53_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V53_INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("site")
    target = find_npc(TARGET_QUERY)
    if not site or not target:
        return {
            "success": False,
            "reason": "SITE_OR_TARGET_MISSING",
            "build": PILOT_BUILD,
        }

    if target.location != site:
        target.move_to(site, quiet=True)

    stats = adventure_stats(target)
    target_stat_authored = TARGET_STAT in stats
    if not target_stat_authored:
        stats[TARGET_STAT] = DEFAULT_TARGET_STAT_VALUE
        target.db.adventure_stats = stats

    state = _plain_dict(getattr(target.db, "state", {}))
    state.setdefault(CONFRONTED_FIELD, False)
    target.db.state = state

    action = {
        "id": CONFRONT_ACTION_ID,
        "name": "Presionar al informante",
        "input_phrases": ["presionar", "confrontar", "poner contra las cuerdas"],
        "enabled": True,
        "object_state_requirements": [
            {
                "field": CONFRONTED_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Informante aun no ha cedido",
            }
        ],
        "check": {
            "id": f"CHECK-{CONFRONT_ACTION_ID}",
            "trigger": "OPPOSITION",
            "mode": "CONFRONT",
            "stat": "PSI",
            "target_stat": TARGET_STAT,
        },
        "canon_status": "prototype",
    }
    target.db.object_actions = _upsert_by_id(getattr(target.db, "object_actions", []), action)

    upsert_consequence_rule(
        {
            "id": CONFRONT_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_RESOLVED",
                "object_action_id": CONFRONT_ACTION_ID,
                "outcome": "ACTOR_WIN",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": CONFRONTED_FIELD,
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": WORLD_CONFRONTED_FIELD,
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
                "field": WORLD_CONFRONTED_FIELD,
                "op": "EQ",
                "value": 1,
                "name": "Informante cedio en confrontacion",
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
        "target": target,
        "action_id": CONFRONT_ACTION_ID,
        "rule_id": CONFRONT_RULE_ID,
        "presentation_id": PRESENTATION_ID,
        "target_stat": TARGET_STAT,
        "target_stat_value": adventure_stats(target).get(TARGET_STAT),
        "target_stat_was_authored": target_stat_authored,
    }


def reset_v54_playtest_state():
    install = ensure_v54_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": PILOT_BUILD,
        }

    site = install.get("site")
    target = install.get("target")
    state = _plain_dict(getattr(target.db, "state", {}))
    state[CONFRONTED_FIELD] = False
    target.db.state = state

    world_state = _plain_dict(getattr(site.db, "world_state", {}))
    world_state.pop(WORLD_CONFRONTED_FIELD, None)
    site.db.world_state = world_state

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": PILOT_BUILD,
        "site": site,
        "target": target,
        "target_stat": TARGET_STAT,
        "target_stat_value": adventure_stats(target).get(TARGET_STAT),
        "confronted": False,
        "presentation_visible": False,
    }


def v54_rule_count():
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == CONFRONT_RULE_ID)
