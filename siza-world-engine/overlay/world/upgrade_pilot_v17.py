from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v17_shift_handoff"
UPGRADE_CATEGORY = "siza_upgrade"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
POLICY = "RELEASE"


def find_worker():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == WORKER_ID:
            return obj
    return None


def build():
    worker = find_worker()
    if not worker:
        caller.msg("No puedo aplicar v0.17: falta Trabajador de Prueba B de v0.13.")
        return

    if worker.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.17 ya estaba aplicado; no se alteró el estado del mundo.")
        caller.msg("Harness B: offshift_claim_policy=RELEASE.")
        return

    try:
        schedule = dict(worker.db.job_schedule or {})
    except Exception:
        schedule = {}

    if not schedule:
        caller.msg("No puedo aplicar v0.17: B no tiene job_schedule de v0.16.")
        return

    previous = schedule.get("offshift_claim_policy")
    schedule["offshift_claim_policy"] = POLICY
    schedule["canon_status"] = "prototype"
    worker.db.job_schedule = schedule
    worker.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.17 aplicado: handoff de JOB al cerrar turno.")
    caller.msg(
        f"Harness B: offshift_claim_policy={POLICY} "
        f"(previous={previous or 'KEEP/default'})."
    )
    caller.msg("Al cerrar 08:00-17:00, un claim activo de B se libera sin borrar work_done.")
    caller.msg("El task sigue activo y puede ser reasignado por el árbitro en el mismo tick.")
    caller.msg("KEEP sigue siendo el comportamiento por defecto para NPCs/schedules sin esta policy.")
    caller.msg("No se modificó supplies, work_done, fatigue, claim, hora ni posiciones.")
    caller.msg("Prueba recomendada: crear JOB antes de 17:00, dejarlo incompleto y cruzar 17:00.")


build()
