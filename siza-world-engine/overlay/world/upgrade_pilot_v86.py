from services.consequence_engine import consequence_rules, upsert_consequence_rule
from services.knowledge_context_engine import knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.npc_simulation import find_npc
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v54 import CONFRONTED_FIELD, TARGET_QUERY
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


PILOT_BUILD = "0.86.0-acquired-fact-unlocks-authored-action"
FACT_ID = "FACT-PESCADERIA-INFORMANTE-SELLO-AUDITORIA-001"
KNOWLEDGE_KEY = "V086_INFORMANT_AUDIT_SEAL"
FACT_TOPIC = "sello blanco de auditoria"
FACT_TEXT = (
    "El sello blanco de auditoría fue aplicado por el relevo que cerró el inventario nocturno."
)
ACTION_ID = "ACT-TEST-PESCADERIA-CRUZAR-SELLO-AUDITORIA-001"
RULE_ID = "RULE-TEST-PESCADERIA-CRUZAR-SELLO-AUDITORIA-001"
PRESENTATION_ID = "PRES-TEST-PESCADERIA-SELLO-AUDITORIA-CRUZADO-001"
ACTION_FIELD = "v086_audit_seal_crosschecked"
WORLD_FIELD = "v086_audit_seal_crosschecked"
ACTION_INPUT = "cruzar sello blanco del manifiesto"
EXPLICIT_FACT_PHRASE = "hablo con Informante de Prueba C sobre sello blanco de auditoria"
PRESENTATION_TEXT = (
    "Con el dato obtenido del informante, cruzas el sello blanco de auditoría con el manifiesto y "
    "confirmas que el cierre del inventario nocturno fue asentado por ese mismo relevo."
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


def ensure_v86_pilot_content():
    previous = ensure_v63_pilot_content()
    if not bool(previous.get("success")):
        return {
            "success": False,
            "reason": previous.get("reason") or "V63_CONTEXT_FAILED",
            "build": PILOT_BUILD,
        }

    site = previous.get("destination")
    manifest = previous.get("manifest")
    informant = find_npc(TARGET_QUERY)
    if not site or not manifest or not informant:
        return {
            "success": False,
            "reason": "SITE_MANIFEST_OR_INFORMANT_MISSING",
            "build": PILOT_BUILD,
        }
    if str(getattr(manifest.db, "object_id", "") or "") != MANIFEST_ID:
        return {
            "success": False,
            "reason": "MANIFEST_ID_MISMATCH",
            "build": PILOT_BUILD,
        }
    if informant.location != site:
        informant.move_to(site, quiet=True)

    existing_fact = find_knowledge_fact(informant, FACT_ID)
    fact = {
        "id": FACT_ID,
        "topic": FACT_TOPIC,
        "aliases": ["sello blanco", "sello de auditoria", "inventario nocturno"],
        "text": FACT_TEXT,
        "knowledge_key": KNOWLEDGE_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "kind": "PILOT_AUTHORED_INFORMANT_KNOWLEDGE",
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
        },
        "learned_by": {
            "provider": "PILOT_CONTENT",
            "mode": "PREEXISTING_NPC_KNOWLEDGE",
        },
    }
    if existing_fact:
        if existing_fact.get("transfer_history") is not None:
            fact["transfer_history"] = _plain_list(existing_fact.get("transfer_history"))
        if existing_fact.get("origin_learned_at") is not None:
            fact["origin_learned_at"] = existing_fact.get("origin_learned_at")
    upsert_knowledge_fact(informant, fact)
    current_level = int(knowledge_levels(informant).get(KNOWLEDGE_KEY, 0) or 0)
    set_knowledge_level(informant, KNOWLEDGE_KEY, max(current_level, 1))

    policies = _plain_dict(getattr(informant.db, "fact_disclosure_policies", {}))
    policies[FACT_ID] = {
        "npc_state_requirements": [
            {
                "field": CONFRONTED_FIELD,
                "op": "EQ",
                "value": True,
                "name": "Informante ha cedido a la presion",
            }
        ]
    }
    informant.db.fact_disclosure_policies = policies

    state = _plain_dict(getattr(manifest.db, "state", {}))
    state.setdefault(ACTION_FIELD, False)
    manifest.db.state = state

    action = {
        "id": ACTION_ID,
        "name": "Cruzar sello blanco de auditoria",
        "activity": "contrastando el sello blanco de auditoria con el manifiesto",
        "input_phrases": [
            "cruzar sello blanco",
            "verificar sello de auditoria",
            "contrastar sello blanco",
        ],
        "enabled": True,
        "knowledge_requirements": [
            {
                "knowledge_key": KNOWLEDGE_KEY,
                "min_level": 1,
                "name": "Origen del sello blanco de auditoria",
            }
        ],
        "object_state_requirements": [
            {
                "field": ACTION_FIELD,
                "op": "EQ",
                "value": False,
                "name": "Sello de auditoria aun no cruzado",
            }
        ],
        "canon_status": "prototype",
    }
    manifest.db.object_actions = _upsert_by_id(getattr(manifest.db, "object_actions", []), action)

    upsert_consequence_rule(
        {
            "id": RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": ACTION_ID,
                "object_id": MANIFEST_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": ACTION_FIELD,
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": WORLD_FIELD,
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
                "field": WORLD_FIELD,
                "op": "EQ",
                "value": 1,
                "name": "Sello blanco de auditoria cruzado",
            }
        ],
        "canon_status": "prototype",
    }
    site.db.state_presentations = _upsert_by_id(
        getattr(site.db, "state_presentations", []),
        presentation,
    )

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "manifest": manifest,
        "informant": informant,
        "fact_id": FACT_ID,
        "knowledge_key": KNOWLEDGE_KEY,
        "action_id": ACTION_ID,
        "rule_id": RULE_ID,
        "presentation_id": PRESENTATION_ID,
        "fact": find_knowledge_fact(informant, FACT_ID),
    }


def v86_rule_count():
    return sum(1 for row in consequence_rules() if str(row.get("id") or "") == RULE_ID)
