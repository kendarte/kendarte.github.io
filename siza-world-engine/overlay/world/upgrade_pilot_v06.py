from evennia import search_object

from services.job_engine import JOB_SITE_CATEGORY, JOB_SITE_TAG


TASK_ID = "TEST-WORKORDER-PESCADERIA-001"


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def build():
    pescaderia = find_room("Pescaderia de Darsena", "CAR-KAL-DAR-007")
    if not pescaderia:
        caller.msg("No puedo aplicar v0.6: falta Pescaderia de Darsena.")
        return

    tasks = []
    found = False
    try:
        existing = list(pescaderia.db.job_tasks or [])
    except Exception:
        existing = []

    for raw in existing:
        try:
            task = {str(key): value for key, value in raw.items()}
        except Exception:
            tasks.append(raw)
            continue
        if str(task.get("id")) == TASK_ID:
            found = True
        tasks.append(task)

    if not found:
        tasks.append(
            {
                "id": TASK_ID,
                "job_id": "JOB-DARSENA-TEST",
                "assigned_npc_id": None,
                "active": False,
                "status": "inactive",
                "priority": 60,
                "activity": "revisando una orden de abastecimiento de prueba en la pescadería",
                "one_shot": True,
                "canon_status": "prototype",
            }
        )

    pescaderia.db.job_tasks = tasks
    pescaderia.tags.add(JOB_SITE_TAG, category=JOB_SITE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.6 aplicado: productor JOB desde estado persistente del mundo.")
    caller.msg("La tarea de prueba vive en Pescaderia.db.job_tasks; NO vive en Mara.decision_goals.")
    caller.msg(f"Task: {TASK_ID} | job_id=JOB-DARSENA-TEST | active=False | prototype")
    caller.msg("Prueba: siza-jobs Mara | siza-job-toggle TEST-WORKORDER-PESCADERIA-001 on")


build()
