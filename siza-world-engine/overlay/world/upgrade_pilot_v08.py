from evennia import search_object

from services.job_engine import JOB_SITE_CATEGORY, JOB_SITE_TAG, refresh_world_job_rules


TASK_ID = "TEST-WORKORDER-PESCADERIA-001"
RULE_ID = "TEST-RULE-PESCADERIA-SUPPLIES-LOW-001"
UPGRADE_TAG = "kalnaj_pilot_v08_worksite_rules"
UPGRADE_CATEGORY = "siza_upgrade"


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def build():
    pescaderia = find_room("Pescaderia de Darsena", "CAR-KAL-DAR-007")
    if not pescaderia:
        caller.msg("No puedo aplicar v0.8: falta Pescaderia de Darsena.")
        return

    try:
        already = pescaderia.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    except Exception:
        already = False

    if already:
        caller.msg("Kalnaj Pilot v0.8 ya estaba aplicado; no se reinició el estado del worksite.")
        caller.msg("Use siza-worksite CAR-KAL-DAR-007 para inspeccionarlo.")
        return

    state = _plain_dict(pescaderia.db.work_state)
    state["supplies"] = 5
    pescaderia.db.work_state = state

    tasks = []
    task_found = False
    for raw in _plain_list(pescaderia.db.job_tasks):
        try:
            task = {str(key): value for key, value in raw.items()}
        except Exception:
            tasks.append(raw)
            continue
        if str(task.get("id")) == TASK_ID:
            task_found = True
            task["job_id"] = "JOB-DARSENA-TEST"
            task["assigned_npc_id"] = None
            task["active"] = False
            task["status"] = "inactive"
            task["priority"] = 60
            task["activity"] = "revisando una orden de abastecimiento de prueba en la pescadería"
            task["one_shot"] = True
            task["canon_status"] = "prototype"
            task["rule_id"] = RULE_ID
            for key in (
                "completed_by_npc_id",
                "completed_by_name",
                "completed_at",
                "completion_effects_applied",
            ):
                task.pop(key, None)
        tasks.append(task)

    if not task_found:
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
                "rule_id": RULE_ID,
            }
        )
    pescaderia.db.job_tasks = tasks

    rules = []
    rule_found = False
    for raw in _plain_list(pescaderia.db.job_rules):
        try:
            rule = {str(key): value for key, value in raw.items()}
        except Exception:
            rules.append(raw)
            continue
        if str(rule.get("id")) == RULE_ID:
            rule_found = True
            rule = {
                "id": RULE_ID,
                "enabled": True,
                "field": "supplies",
                "op": "lte",
                "value": 2,
                "task_id": TASK_ID,
                "completion_effects": [
                    {"field": "supplies", "op": "set", "value": 5}
                ],
                "canon_status": "prototype",
            }
        rules.append(rule)

    if not rule_found:
        rules.append(
            {
                "id": RULE_ID,
                "enabled": True,
                "field": "supplies",
                "op": "lte",
                "value": 2,
                "task_id": TASK_ID,
                "completion_effects": [
                    {"field": "supplies", "op": "set", "value": 5}
                ],
                "canon_status": "prototype",
            }
        )
    pescaderia.db.job_rules = rules

    pescaderia.tags.add(JOB_SITE_TAG, category=JOB_SITE_CATEGORY)
    pescaderia.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    refresh_world_job_rules()

    caller.msg("Kalnaj Pilot v0.8 aplicado: worksite -> regla -> JOB -> efecto de mundo.")
    caller.msg("Estado prototype inicial: Pescaderia.work_state.supplies=5.")
    caller.msg(f"Regla: {RULE_ID}: supplies <= 2 activa {TASK_ID}.")
    caller.msg("Al completar el JOB, el efecto prototype establece supplies=5.")
    caller.msg("Prueba: siza-worksite CAR-KAL-DAR-007")
    caller.msg("Luego: siza-workset CAR-KAL-DAR-007 supplies 1")


build()
