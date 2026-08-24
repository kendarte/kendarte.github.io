from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v28_knowledge_aware_decisions"
UPGRADE_CATEGORY = "siza_upgrade"

MARA_ID = "NPC-KAL-DAR-MARA-001"
FACT_ID = "TEST-KNOWLEDGE-PESCADERIA-JOB-CONTEXT-001"
EFFECT_ID = "TEST-KNOWLEDGE-EFFECT-PESCADERIA-JOB-001"


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
        caller.msg("No puedo aplicar v0.28: falta Mara Vensal.")
        return

    if mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.28 ya estaba aplicado; no se duplicó el Knowledge fact.")
        return

    effect = {
        "id": EFFECT_ID,
        "enabled": False,
        "value": 15,
        "when": {
            "type": "JOB",
            "target_room_id": "CAR-KAL-DAR-007",
        },
        "kind": "KNOWLEDGE_CONTEXT_BIAS",
        "canon_status": "prototype",
    }

    fact = {
        "id": FACT_ID,
        "topic": "prototype knowledge decision context",
        "aliases": ["prototype knowledge decision context"],
        "knowledge_key": "PESCADERIA",
        "required_level": 2,
        "decision_effects": [effect],
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

    try:
        current_level = int(dict(mara.db.knowledge or {}).get("PESCADERIA", 0) or 0)
    except Exception:
        current_level = 0

    caller.msg("Kalnaj Pilot v0.28 aplicado: Knowledge-aware Decisions.")
    caller.msg(
        f"Harness: {FACT_ID} | key=PESCADERIA | required=2 | "
        f"effect={EFFECT_ID} JOB hacia Pescaderia +15 | DISABLED."
    )
    caller.msg(f"Nivel PESCADERIA actual de Mara preservado: {current_level}.")
    caller.msg("Knowledge sólo habilita efectos explícitos de facts conocidos; no genera prioridades automáticas por nivel.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, memories, relationships, orders, factions, events ni dangers.")
    caller.msg("Prueba: siza-knowledge Mara")


build()
