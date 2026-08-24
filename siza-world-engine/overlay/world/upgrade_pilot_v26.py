from datetime import datetime, timezone

from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v26_memory_relationship_context"
UPGRADE_CATEGORY = "siza_upgrade"

MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
MEMORY_ID = "TEST-MEMORY-MARA-B-CONTEXT-001"
MEMORY_EFFECT_ID = "TEST-MEMORY-EFFECT-MARA-B-ORDER-001"
RELATIONSHIP_EFFECT_ID = "TEST-RELATIONSHIP-EFFECT-MARA-B-001"


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


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == str(npc_id):
            return obj
    return None


def _upsert_effect(container, effect):
    output = []
    replaced = False
    for raw in _plain_list((container or {}).get("decision_effects")):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == str(effect.get("id") or ""):
            output.append(dict(effect))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(effect))
    container["decision_effects"] = output
    return container


def build():
    mara = _find_npc(MARA_ID)
    worker = _find_npc(WORKER_ID)
    if not mara or not worker:
        caller.msg("No puedo aplicar v0.26: faltan Mara o Trabajador B.")
        return

    if mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.26 ya estaba aplicado; no se duplicaron memories ni relationship effects.")
        return

    memory_effect = {
        "id": MEMORY_EFFECT_ID,
        "enabled": False,
        "value": 20,
        "when": {"type": "ORDER", "issuer_id": WORKER_ID},
        "kind": "CONTEXT_BIAS",
        "canon_status": "prototype",
    }

    memories = []
    memory_found = False
    for raw in _plain_list(mara.db.memories):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or item.get("memory_id") or "") == MEMORY_ID:
            item = _upsert_effect(item, memory_effect)
            memories.append(item)
            memory_found = True
        else:
            memories.append(item)

    if not memory_found:
        memories.append(
            {
                "id": MEMORY_ID,
                "type": "behavioral_context_test",
                "schema": 3,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "subject_npc_id": WORKER_ID,
                "with_id": int(worker.id),
                "with_name": worker.key,
                "summary": "Recuerdo conductual de prueba asociado al Trabajador B.",
                "canon_status": "prototype",
                "decision_effects": [memory_effect],
            }
        )
    mara.db.memories = memories[-100:]

    relationships = _plain_dict(mara.db.relationships)
    relation = _record(relationships.get(WORKER_ID)) or {}
    relation.setdefault("target_type", "NPC")
    relation.setdefault("target_npc_id", WORKER_ID)
    relation.setdefault("target_dbref", int(worker.id))
    relation.setdefault("target_name", worker.key)
    relation = _upsert_effect(
        relation,
        {
            "id": RELATIONSHIP_EFFECT_ID,
            "enabled": False,
            "value": 15,
            "when": {
                "type": "RELATIONSHIP",
                "relationship_target_npc_id": WORKER_ID,
            },
            "kind": "CONTEXT_BIAS",
            "canon_status": "prototype",
        },
    )
    relationships[WORKER_ID] = relation
    mara.db.relationships = relationships

    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.26 aplicado: Memory + Relationship Decision Context.")
    caller.msg(f"Memory harness: {MEMORY_ID} | effect={MEMORY_EFFECT_ID} | ORDER from B +20 | DISABLED.")
    caller.msg(f"Relationship harness: Mara->B | effect={RELATIONSHIP_EFFECT_ID} | RELATIONSHIP +15 | DISABLED.")
    caller.msg("Los efectos son explícitos; el engine no infiere sentimiento ni prioridad leyendo texto de memoria.")
    caller.msg("No hay decay, trust score ni reputation global en v0.26.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, obligations, orders, factions, events ni dangers.")
    caller.msg("Prueba: siza-context-effects Mara")


build()
