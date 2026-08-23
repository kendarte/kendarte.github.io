from evennia import search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v15_priority_arbitration"
UPGRADE_CATEGORY = "siza_upgrade"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
PLAZA_ID = "CAR-KAL-DAR-003"


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def find_worker():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == WORKER_ID:
            return obj
    return None


def build():
    plaza = find_room("Plaza de Recepcion", PLAZA_ID)
    if not plaza:
        caller.msg("No puedo aplicar v0.15: falta Plaza de Recepcion.")
        return

    worker = find_worker()
    if not worker:
        caller.msg("No puedo aplicar v0.15: falta Trabajador de Prueba B de v0.13.")
        return

    if worker.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.15 ya estaba aplicado; no se alteró el estado del mundo.")
        caller.msg("Use siza-needset Mara fatigue 7 y siza-workset CAR-KAL-DAR-007 supplies 1.")
        return

    positioned = False
    try:
        positioned = bool(worker.move_to(plaza, quiet=True, move_type="teleport"))
    except Exception:
        try:
            worker.location = plaza
            positioned = worker.location == plaza
        except Exception:
            positioned = False

    worker.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.15 aplicado: arbitraje sensible a prioridades activas.")
    caller.msg("NPCs con un goal alcanzable de prioridad mayor al JOB quedan fuera del arbitraje de ese JOB.")
    caller.msg("Un NPC que ya posee otro JOB tampoco puede recibir un segundo claim simultáneo.")
    caller.msg("Los NEED de CLOCK ahora se actualizan antes del arbitraje global.")
    caller.msg("No se modificó supplies, work_done, fatigue, claim ni posición/estado de Mara.")
    caller.msg(
        f"Harness prototype {worker.key}: "
        f"{'posicionado en Plaza de Recepcion' if positioned else 'no pude reposicionarlo'}; no es canon."
    )
    caller.msg("Prueba: siza-needset Mara fatigue 7 | siza-workset CAR-KAL-DAR-007 supplies 1")


build()
