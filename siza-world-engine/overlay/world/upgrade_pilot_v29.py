from evennia import search_tag

from services.consequence_engine import (
    CONSEQUENCE_BUILD,
    consequence_rules,
    get_consequence_registry,
    upsert_consequence_rule,
)


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v29_learning_by_doing"
UPGRADE_CATEGORY = "siza_upgrade"

MARA_ID = "NPC-KAL-DAR-MARA-001"
TASK_ID = "TEST-WORKORDER-PESCADERIA-001"
RULE_ID = "TEST-CONSEQUENCE-PESCADERIA-JOB-LEARNING-001"
KNOWLEDGE_KEY = "TEST_PESCADERIA_WORKFLOW"
FACT_ID = "TEST-KNOWLEDGE-PESCADERIA-EXPERIENCE-001"
EFFECT_ID = "TEST-KNOWLEDGE-EFFECT-PESCADERIA-EXPERIENCE-JOB-001"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == str(npc_id):
            return obj
    return None


def build():
    mara = _find_npc(MARA_ID)
    if not mara:
        caller.msg("No puedo aplicar v0.29: falta Mara Vensal.")
        return

    if mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.29 ya estaba aplicado; no se duplicó el harness.")
        return

    existing_rules = {
        str(item.get("id") or ""): item
        for item in consequence_rules()
        if item.get("id")
    }
    rule = {
        "id": RULE_ID,
        "enabled": bool(existing_rules.get(RULE_ID, {}).get("enabled", False)),
        "when": {
            "action_type": "JOB_COMPLETED",
            "task_id": TASK_ID,
            "actor_npc_id": MARA_ID,
        },
        "recipient_mode": "ACTOR",
        "knowledge": {
            "knowledge_key": KNOWLEDGE_KEY,
            "mode": "MAX",
            "value": 1,
        },
        "canon_status": "prototype",
    }
    upsert_consequence_rule(rule)
    registry = get_consequence_registry(create=True)
    registry.db.build = CONSEQUENCE_BUILD

    fact = {
        "id": FACT_ID,
        "topic": "prototype learned workflow",
        "aliases": ["prototype learned workflow"],
        "knowledge_key": KNOWLEDGE_KEY,
        "required_level": 1,
        "decision_effects": [
            {
                "id": EFFECT_ID,
                "enabled": True,
                "value": 10,
                "when": {
                    "type": "JOB",
                    "target_room_id": "CAR-KAL-DAR-007",
                },
                "kind": "KNOWLEDGE_CONTEXT_BIAS",
                "canon_status": "prototype",
            }
        ],
        "canon_status": "prototype",
    }

    facts = []
    replaced = False
    for raw in _plain_list(mara.db.knowledge_facts):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == FACT_ID:
            facts.append(dict(fact))
            replaced = True
        else:
            facts.append(item)
    if not replaced:
        facts.append(dict(fact))
    mara.db.knowledge_facts = facts
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    levels = {}
    try:
        levels = {str(key): value for key, value in (mara.db.knowledge or {}).items()}
    except Exception:
        pass
    current = int(levels.get(KNOWLEDGE_KEY, 0) or 0)

    caller.msg("Kalnaj Pilot v0.29 aplicado: Learning by Doing via Action -> Consequence -> Knowledge.")
    caller.msg(
        f"Rule: {RULE_ID} | JOB_COMPLETED {TASK_ID} por Mara -> {KNOWLEDGE_KEY}=MAX(1) | DISABLED."
    )
    caller.msg(
        f"Fact: {FACT_ID} | required={KNOWLEDGE_KEY}:1 | effect={EFFECT_ID} JOB hacia Pescaderia +10 | ENABLED."
    )
    caller.msg(f"Nivel aprendido actual preservado: {KNOWLEDGE_KEY}={current}.")
    caller.msg("El effect está habilitado pero no puede actuar hasta que el Knowledge sea aprendido por una consecuencia real.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, memories, relationships, orders, factions, events ni dangers.")
    caller.msg("Prueba: siza-consequences | siza-knowledge Mara")


build()
