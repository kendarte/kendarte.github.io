from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v22_decision_personality"
UPGRADE_CATEGORY = "siza_upgrade"
MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
MARA_MOD_ID = "TEST-PERSONALITY-MARA-RELATIONSHIP-001"
WORKER_MOD_ID = "TEST-PERSONALITY-WORKER-B-JOB-001"


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
        return None


def _upsert_modifier(npc, modifier):
    modifiers = []
    replaced = False
    for raw in _plain_list(getattr(npc.db, "decision_modifiers", [])):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == str(modifier.get("id") or ""):
            modifiers.append(dict(modifier))
            replaced = True
        else:
            modifiers.append(item)
    if not replaced:
        modifiers.append(dict(modifier))
    npc.db.decision_modifiers = modifiers


def build():
    mara = find_npc(MARA_ID)
    worker = find_npc(WORKER_ID)
    if not mara or not worker:
        caller.msg("No puedo aplicar v0.22: faltan Mara o Trabajador de Prueba B.")
        return

    if mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.22 ya estaba aplicado; no se alteraron modifiers ni estado del mundo.")
        return

    _upsert_modifier(
        mara,
        {
            "id": MARA_MOD_ID,
            "enabled": False,
            "value": 20,
            "when": {"type": "RELATIONSHIP"},
            "kind": "DECISION_BIAS",
            "canon_status": "prototype",
        },
    )
    _upsert_modifier(
        worker,
        {
            "id": WORKER_MOD_ID,
            "enabled": False,
            "value": 15,
            "when": {"type": "JOB"},
            "kind": "DECISION_BIAS",
            "canon_status": "prototype",
        },
    )

    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.22 aplicado: Decision Personality Layer.")
    caller.msg("Las prioridades base siguen siendo fallback; cada NPC puede aplicar modifiers propios.")
    caller.msg(f"Mara harness: {MARA_MOD_ID} | RELATIONSHIP +20 | DISABLED.")
    caller.msg(f"Worker B harness: {WORKER_MOD_ID} | JOB +15 | DISABLED.")
    caller.msg("Los modifiers quedan apagados al instalar; no cambian decisiones hasta activarlos.")
    caller.msg("El árbitro de JOB usa la misma prioridad efectiva que siza-decide.")
    caller.msg("No se modificó hora, posición, jobs, claims, fatigue, relationships, events ni dangers.")
    caller.msg("Prueba: siza-personality Mara | siza-personality Trabajador B")


build()
