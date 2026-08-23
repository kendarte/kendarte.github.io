from evennia import search_object

from services.world_event_engine import (
    EVENT_SITE_CATEGORY,
    EVENT_SITE_TAG,
    refresh_world_event_rules,
)


UPGRADE_TAG = "kalnaj_pilot_v19_world_danger"
UPGRADE_CATEGORY = "siza_upgrade"
PESCADERIA_ID = "CAR-KAL-DAR-007"
PLAZA_ID = "CAR-KAL-DAR-003"
RULE_ID = "TEST-RULE-PESCADERIA-HAZARD-001"
DANGER_ID = "TEST-WORLD-DANGER-PESCADERIA-001"


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


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def build():
    pescaderia = find_room("Pescaderia de Darsena", PESCADERIA_ID)
    plaza = find_room("Plaza de Recepcion", PLAZA_ID)
    if not pescaderia or not plaza:
        caller.msg("No puedo aplicar v0.19: faltan Pescaderia de Darsena o Plaza de Recepcion.")
        return

    if pescaderia.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.19 ya estaba aplicado; no se alteró el estado del mundo.")
        caller.msg("Prueba: siza-eventset CAR-KAL-DAR-007 hazard 1 | siza-events")
        return

    try:
        state = dict(pescaderia.db.world_event_state or {})
    except Exception:
        state = {}
    if "hazard" not in state:
        state["hazard"] = 0
    pescaderia.db.world_event_state = state

    rules = []
    for raw in _plain_list(pescaderia.db.world_event_rules):
        item = _record(raw)
        if item is not None:
            rules.append(item)

    rule = {
        "id": RULE_ID,
        "event_id": DANGER_ID,
        "enabled": True,
        "goal_type": "DANGER",
        "response_mode": "PERSISTENT",
        "field": "hazard",
        "op": "gte",
        "value": 1,
        "priority": 100,
        "affected_room_ids": [PESCADERIA_ID],
        "target_room_id": PLAZA_ID,
        "target_room_key": "Plaza de Recepcion",
        "activity": "evacuando un peligro urgente de prueba en la pescadería",
        "blocks_jobs": True,
        "npc_ids": [],
        "job_ids": [],
        "canon_status": "prototype",
    }

    replaced = False
    for index, existing in enumerate(rules):
        if str(existing.get("id") or "") == RULE_ID:
            rules[index] = rule
            replaced = True
            break
    if not replaced:
        rules.append(rule)

    pescaderia.db.world_event_rules = rules
    if pescaderia.db.world_event_instances is None:
        pescaderia.db.world_event_instances = []
    pescaderia.tags.add(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY)
    pescaderia.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    refresh_world_event_rules()

    caller.msg("Kalnaj Pilot v0.19 aplicado: WORLD DANGER persistente.")
    caller.msg(f"Danger site: Pescaderia de Darsena ({PESCADERIA_ID}).")
    caller.msg("State prototype: hazard=0 por defecto; no se sobrescribió si ya existía.")
    caller.msg(f"Rule {RULE_ID}: hazard>=1 -> DANGER100 {DANGER_ID}.")
    caller.msg("Affected room: Pescaderia; safe target: Plaza de Recepcion.")
    caller.msg("DANGER no usa ACK: evacua mientras afecte la ubicación y persiste hasta llegar al target seguro.")
    caller.msg("blocks_jobs=True: ningún claim nuevo puede enviarse hacia Pescaderia mientras hazard esté activo.")
    caller.msg("Un owner existente conserva su claim, pero el JOB queda oculto mientras el destino siga peligroso.")
    caller.msg("No se modificó alert de Plaza, supplies, jobs, fatigue, hora, posiciones ni claims.")
    caller.msg("Prueba: siza-eventset CAR-KAL-DAR-007 hazard 1 | siza-events")


build()
