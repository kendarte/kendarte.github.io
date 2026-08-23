from evennia import search_object


UPGRADE_TAG = "kalnaj_pilot_v12_job_progress"
UPGRADE_CATEGORY = "siza_upgrade"
PESCADERIA_ID = "CAR-KAL-DAR-007"
TASK_ID = "TEST-WORKORDER-PESCADERIA-001"
WORK_REQUIRED = 3
WORK_PER_ACTION = 1


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


def build():
    site = find_pescaderia()
    if not site:
        caller.msg("No puedo aplicar v0.12: falta Pescaderia de Darsena.")
        return

    try:
        already = site.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    except Exception:
        already = False

    if already:
        caller.msg("Kalnaj Pilot v0.12 ya estaba aplicado; no se reinició progreso de trabajo.")
        caller.msg("Use siza-jobs Mara para inspeccionar el task.")
        return

    tasks = []
    found = False
    for raw in _plain_list(site.db.job_tasks):
        try:
            task = {str(key): value for key, value in raw.items()}
        except Exception:
            tasks.append(raw)
            continue

        if str(task.get("id") or "") != TASK_ID:
            tasks.append(task)
            continue

        found = True
        task["work_required"] = WORK_REQUIRED
        task["work_per_action"] = WORK_PER_ACTION

        try:
            work_done = max(0, int(task.get("work_done", 0) or 0))
        except (TypeError, ValueError):
            work_done = 0

        status = str(task.get("status") or "inactive")
        if status == "completed":
            # Existing completed history should display as complete. A future
            # producer recurrence resets work_done to 0 automatically.
            task["work_done"] = WORK_REQUIRED
        else:
            task["work_done"] = min(WORK_REQUIRED, work_done)

        task["canon_status"] = str(task.get("canon_status") or "prototype")
        tasks.append(task)

    if not found:
        caller.msg(f"No puedo aplicar v0.12: no existe task {TASK_ID}.")
        return

    site.db.job_tasks = tasks
    site.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.12 aplicado: JOB con progreso persistente.")
    caller.msg(f"Task {TASK_ID}: work_required={WORK_REQUIRED} | work_per_action={WORK_PER_ACTION}.")
    caller.msg("Llegar al worksite ya no completa el JOB; cada tick WORK suma progreso.")
    caller.msg("El efecto sobre supplies ocurre únicamente cuando work_done alcanza work_required.")
    caller.msg("No se modificó supplies, fatigue, ubicación ni estado actual de Mara.")
    caller.msg("Prueba: siza-jobs Mara | siza-workset CAR-KAL-DAR-007 supplies 1")


build()
