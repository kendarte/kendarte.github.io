from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v20_relationship_obligations"
UPGRADE_CATEGORY = "siza_upgrade"
MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
OBLIGATION_ID = "TEST-REL-MARA-WORKER-B-001"


def find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == npc_id:
            return obj
    return None


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return {}


def build():
    mara = find_npc(MARA_ID)
    worker = find_npc(WORKER_ID)
    if not mara or not worker:
        caller.msg("No puedo aplicar v0.20: faltan Mara o Trabajador de Prueba B.")
        return

    if mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.20 ya estaba aplicado; no se alteró el estado del mundo.")
        caller.msg(f"Harness: {OBLIGATION_ID} permanece según su estado actual.")
        return

    try:
        relationships = dict(mara.db.relationships or {})
    except Exception:
        relationships = {}

    relation = _record(relationships.get(WORKER_ID))
    obligations = []
    for raw in _plain_list(relation.get("obligations")):
        obligations.append(_record(raw))

    obligation = {
        "id": OBLIGATION_ID,
        "kind": "REQUEST",
        "active": False,
        "status": "inactive",
        "priority": 50,
        "one_shot": True,
        "activity": "atendiendo una solicitud social de prueba del trabajador B",
        "canon_status": "prototype",
    }

    replaced = False
    for index, existing in enumerate(obligations):
        if str(existing.get("id") or "") == OBLIGATION_ID:
            obligations[index] = obligation
            replaced = True
            break
    if not replaced:
        obligations.append(obligation)

    relation["target_npc_id"] = WORKER_ID
    relation["target_name"] = worker.key
    relation["obligations"] = obligations
    relation["canon_status"] = relation.get("canon_status") or "prototype"
    relationships[WORKER_ID] = relation
    mara.db.relationships = relationships
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.20 aplicado: obligaciones RELATIONSHIP persistentes.")
    caller.msg(f"Harness prototype: Mara -> {worker.key} | {OBLIGATION_ID} | priority=50.")
    caller.msg("La obligación queda INACTIVE al instalarla; no cambia comportamiento hasta activarla.")
    caller.msg("El target es el NPC, no una Room: cada decisión usa la ubicación actual del worker.")
    caller.msg("Se resuelve sólo cuando Mara y el worker coinciden físicamente.")
    caller.msg("JOB60 conserva prioridad sobre RELATIONSHIP50; ROUTINE10 queda debajo.")
    caller.msg("No se modificó posición, hora, fatigue, jobs, claims, events ni dangers.")
    caller.msg(f"Prueba: siza-rel-toggle Mara {OBLIGATION_ID} on | siza-decide Mara")


build()
