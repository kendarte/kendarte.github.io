from evennia import search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v14_job_arbitration"
UPGRADE_CATEGORY = "siza_upgrade"
PESCADERIA_ID = "CAR-KAL-DAR-007"
TASK_ID = "TEST-WORKORDER-PESCADERIA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
POLICY = "NEAREST_REACHABLE"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def find_pescaderia():
    for obj in search_object("Pescaderia de Darsena"):
        if obj.db.room_id == PESCADERIA_ID:
            return obj
    return None


def find_worker():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == WORKER_ID:
            return obj
    return None


def build():
    site = find_pescaderia()
    if not site:
        caller.msg("No puedo aplicar v0.14: falta Pescaderia de Darsena.")
        return

    if site.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.14 ya estaba aplicado; no se alteró task ni posiciones.")
        caller.msg("Use siza-workset CAR-KAL-DAR-007 supplies 1 para repetir la prueba.")
        return

    tasks = []
    found = False
    previous_policy = None
    for raw in _plain_list(site.db.job_tasks):
        try:
            task = {str(key): value for key, value in raw.items()}
        except Exception:
            tasks.append(raw)
            continue

        if str(task.get("id") or "") == TASK_ID:
            found = True
            previous_policy = task.get("claim_policy")
            task["claim_policy"] = POLICY
        tasks.append(task)

    if not found:
        caller.msg(f"No puedo aplicar v0.14: no existe task {TASK_ID}.")
        return

    site.db.job_tasks = tasks

    worker = find_worker()
    worker_positioned = False
    if worker:
        try:
            worker_positioned = bool(worker.move_to(site, quiet=True, move_type="teleport"))
        except Exception:
            try:
                worker.location = site
                worker_positioned = worker.location == site
            except Exception:
                worker_positioned = False

    site.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.14 aplicado: arbitraje de JOB por distancia real.")
    caller.msg(
        f"Task {TASK_ID}: claim_policy={POLICY} "
        f"(previous={previous_policy or 'NONE'})."
    )
    caller.msg("El árbitro corre antes de ejecutar NPCs y usa el mismo grafo de Exits transitables.")
    caller.msg("Empates: menor npc_id estable; el orden interno del loop no decide el winner.")
    caller.msg("No se modificó supplies, work_done, fatigue, posición ni estado de Mara.")
    if worker:
        caller.msg(
            f"Harness prototype {worker.key}: "
            f"{'posicionado en Pescaderia para probar distancia=0' if worker_positioned else 'no pude reposicionarlo'}; "
            "no es canon."
        )
    else:
        caller.msg("ATENCION: no encontré Trabajador de Prueba B; la policy sí quedó aplicada.")
    caller.msg("Prueba: siza-workset CAR-KAL-DAR-007 supplies 1 | siza-sim-start 5")


build()
