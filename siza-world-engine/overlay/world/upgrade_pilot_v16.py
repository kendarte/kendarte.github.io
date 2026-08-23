from evennia import search_object, search_tag

from services.world_clock import ensure_world_clock, world_clock_state


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v16_world_clock_schedules"
UPGRADE_CATEGORY = "siza_upgrade"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
PLAZA_ID = "CAR-KAL-DAR-003"
PESCADERIA_ID = "CAR-KAL-DAR-007"
SHIFT_START = 8 * 60
SHIFT_END = 17 * 60


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
    pescaderia = find_room("Pescaderia de Darsena", PESCADERIA_ID)
    worker = find_worker()

    if not plaza or not pescaderia:
        caller.msg("No puedo aplicar v0.16: faltan Plaza de Recepcion o Pescaderia de Darsena.")
        return
    if not worker:
        caller.msg("No puedo aplicar v0.16: falta Trabajador de Prueba B de v0.13.")
        return

    if worker.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        state = world_clock_state()
        caller.msg("Kalnaj Pilot v0.16 ya estaba aplicado; no se alteró el estado del mundo.")
        caller.msg(
            f"World clock: day {state.get('day')} {state.get('time')} | "
            f"rate={state.get('minutes_per_tick')} world-min/tick."
        )
        caller.msg("Use siza-time | siza-timeset 0 07:50 | siza-decide Trabajador B.")
        return

    ensure_world_clock()

    worker.db.job_schedule = {
        "enabled": True,
        "start_minute": SHIFT_START,
        "end_minute": SHIFT_END,
        "canon_status": "prototype",
    }

    worker.db.routine = [
        {
            "id": "ROUTINE-WORKER-B-OFFSHIFT-PLAZA",
            "room_id": PLAZA_ID,
            "room_key": "Plaza de Recepcion",
            "activity": "esperando fuera del turno de prueba en la plaza",
            "activity_kind": "IDLE",
            "duration_ticks": 1,
            "schedule": {
                "enabled": True,
                "start_minute": SHIFT_END,
                "end_minute": SHIFT_START,
                "canon_status": "prototype",
            },
            "status": "prototype",
        },
        {
            "id": "ROUTINE-WORKER-B-SHIFT-PESCADERIA",
            "room_id": PESCADERIA_ID,
            "room_key": "Pescaderia de Darsena",
            "activity": "presente en el puesto de prueba durante su turno",
            "activity_kind": "IDLE",
            "duration_ticks": 1,
            "schedule": {
                "enabled": True,
                "start_minute": SHIFT_START,
                "end_minute": SHIFT_END,
                "canon_status": "prototype",
            },
            "status": "prototype",
        },
    ]
    worker.db.routine_index = 0
    worker.db.routine_hold_remaining = 0
    worker.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    state = world_clock_state()
    caller.msg("Kalnaj Pilot v0.16 aplicado: reloj mundial persistente + schedules de JOB/ROUTINE.")
    caller.msg(
        f"World clock: day {state.get('day')} {state.get('time')} | "
        f"rate={state.get('minutes_per_tick')} world-min/tick | calendario=prototype tecnico."
    )
    caller.msg("Harness B job_schedule=08:00-17:00.")
    caller.msg("Harness B routine: Plaza 17:00-08:00 | Pescaderia 08:00-17:00.")
    caller.msg("Fuera de turno B no puede adquirir un claim nuevo; un claim ya existente no se revoca a mitad de tarea.")
    caller.msg("No se modificó supplies, work_done, fatigue, claim ni posición/estado de Mara.")
    caller.msg("No se movió al worker B y no se modificó el progreso/claim que pudiera tener activo.")
    caller.msg("Prueba: siza-workset CAR-KAL-DAR-007 supplies 5 | siza-timeset 0 07:50")


build()
