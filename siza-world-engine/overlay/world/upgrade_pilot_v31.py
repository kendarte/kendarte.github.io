from evennia import search_object, search_tag

from services.skill_engine import set_skill_level


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v31_skills_competence"
UPGRADE_CATEGORY = "siza_upgrade"

PESCADERIA_ID = "CAR-KAL-DAR-007"
TASK_ID = "TEST-WORKORDER-PESCADERIA-001"
SKILL_ID = "TEST_DARSENA_WORK"
SKILL_NAME = "Trabajo de Darsena de Prueba"
MIN_LEVEL = 1
MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_B_ID = "TEST-NPC-KAL-DAR-WORKER-B"


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


def _find_site():
    for obj in search_object("Pescaderia de Darsena"):
        if str(getattr(obj.db, "room_id", "") or "") == PESCADERIA_ID:
            return obj
    return None


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == str(npc_id):
            return obj
    return None


def build():
    site = _find_site()
    mara = _find_npc(MARA_ID)
    worker = _find_npc(WORKER_B_ID)
    if not site or not mara or not worker:
        caller.msg("No puedo aplicar v0.31: faltan Pescaderia, Mara o Trabajador B.")
        return

    if site.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.31 ya estaba aplicado; no se duplicó el requisito de skill.")
        return

    tasks = []
    found = False
    for raw in _plain_list(site.db.job_tasks):
        task = _record(raw)
        if task is None:
            continue
        if str(task.get("id") or "") == TASK_ID:
            found = True
            task["skill_requirements"] = [
                {
                    "skill_id": SKILL_ID,
                    "name": SKILL_NAME,
                    "min_level": MIN_LEVEL,
                    "canon_status": "prototype",
                }
            ]
        tasks.append(task)

    if not found:
        caller.msg(f"No puedo aplicar v0.31: falta task {TASK_ID}.")
        return

    site.db.job_tasks = tasks
    set_skill_level(mara, SKILL_ID, max(1, int((getattr(mara.db, "skills", {}) or {}).get(SKILL_ID, {}).get("level", 0) if hasattr((getattr(mara.db, "skills", {}) or {}).get(SKILL_ID, {}), "get") else 0)), name=SKILL_NAME)
    set_skill_level(worker, SKILL_ID, max(1, int((getattr(worker.db, "skills", {}) or {}).get(SKILL_ID, {}).get("level", 0) if hasattr((getattr(worker.db, "skills", {}) or {}).get(SKILL_ID, {}), "get") else 0)), name=SKILL_NAME)
    site.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.31 aplicado: Skills / Competence.")
    caller.msg(f"Task {TASK_ID}: requiere {SKILL_ID} >= {MIN_LEVEL}.")
    caller.msg("Mara y Trabajador B reciben level=1 prototype para preservar el comportamiento validado al instalar.")
    caller.msg("El skill es un requisito duro de elegibilidad; no cambia la prioridad psicológica del JOB.")
    caller.msg("No se modificó hora, posición, supplies, claims, Knowledge, traits, memories, relationships, orders, factions, events ni dangers.")
    caller.msg("Prueba: siza-skills Mara | siza-skills Trabajador B")


build()
