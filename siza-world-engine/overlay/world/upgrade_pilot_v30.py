from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v30_virtue_defect_traits"
UPGRADE_CATEGORY = "siza_upgrade"

WORKER_B_ID = "TEST-NPC-KAL-DAR-WORKER-B"
DILIGENCE_ID = "TEST-TRAIT-WORKER-B-DILIGENCE-001"
DILIGENCE_EFFECT_ID = "TEST-TRAIT-EFFECT-WORKER-B-JOB-001"
ORDER_AVERSION_ID = "TEST-TRAIT-WORKER-B-ORDER-AVERSION-001"
ORDER_AVERSION_EFFECT_ID = "TEST-TRAIT-EFFECT-WORKER-B-ORDER-001"


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


def _upsert_traits(npc, authored):
    by_id = {str(item.get("id")): dict(item) for item in authored}
    output = []
    seen = set()
    for raw in _plain_list(getattr(npc.db, "traits", [])):
        item = _record(raw)
        if item is None:
            continue
        trait_id = str(item.get("id") or "")
        if trait_id in by_id:
            replacement = dict(by_id[trait_id])
            replacement["enabled"] = bool(item.get("enabled", replacement.get("enabled", False)))
            output.append(replacement)
            seen.add(trait_id)
        else:
            output.append(item)
    for trait_id, item in by_id.items():
        if trait_id not in seen:
            output.append(dict(item))
    npc.db.traits = output


def build():
    worker = _find_npc(WORKER_B_ID)
    if not worker:
        caller.msg("No puedo aplicar v0.30: falta Trabajador de Prueba B.")
        return

    if worker.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.30 ya estaba aplicado; no se duplicaron traits.")
        return

    diligence = {
        "id": DILIGENCE_ID,
        "name": "Diligencia de Prueba",
        "kind": "VIRTUE",
        "enabled": False,
        "decision_effects": [
            {
                "id": DILIGENCE_EFFECT_ID,
                "enabled": True,
                "value": 15,
                "when": {"type": "JOB"},
                "canon_status": "prototype",
            }
        ],
        "canon_status": "prototype",
    }
    order_aversion = {
        "id": ORDER_AVERSION_ID,
        "name": "Aversión a Órdenes de Prueba",
        "kind": "DEFECT",
        "enabled": False,
        "decision_effects": [
            {
                "id": ORDER_AVERSION_EFFECT_ID,
                "enabled": True,
                "value": -20,
                "when": {"type": "ORDER"},
                "canon_status": "prototype",
            }
        ],
        "canon_status": "prototype",
    }

    _upsert_traits(worker, [diligence, order_aversion])
    worker.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.30 aplicado: Virtue / Defect Traits.")
    caller.msg(
        f"{DILIGENCE_ID} | kind=VIRTUE | JOB +15 | DISABLED."
    )
    caller.msg(
        f"{ORDER_AVERSION_ID} | kind=DEFECT | ORDER -20 | DISABLED."
    )
    caller.msg("VIRTUE/DEFECT describe el trait; el valor y el contexto viven en decision_effects explícitos.")
    caller.msg("El harness sólo modifica Trabajador de Prueba B; no asigna traits a Mara.")
    caller.msg("No se modificó posición, hora, jobs, claims, Knowledge, memories, relationships, orders, factions, events ni dangers.")
    caller.msg("Prueba: siza-traits Trabajador B")


build()
