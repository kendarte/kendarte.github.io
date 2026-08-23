from evennia import search_object

from services.world_event_engine import (
    EVENT_SITE_CATEGORY,
    EVENT_SITE_TAG,
    refresh_world_event_rules,
)


UPGRADE_TAG = "kalnaj_pilot_v18_world_events"
UPGRADE_CATEGORY = "siza_upgrade"
PLAZA_ID = "CAR-KAL-DAR-003"
RULE_ID = "TEST-RULE-PLAZA-ALERT-001"
EVENT_ID = "TEST-WORLD-EVENT-PLAZA-ALERT-001"
MARA_ID = "NPC-KAL-DAR-MARA-001"


def find_plaza():
    for obj in search_object("Plaza de Recepcion"):
        if obj.db.room_id == PLAZA_ID:
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
    plaza = find_plaza()
    if not plaza:
        caller.msg("No puedo aplicar v0.18: falta Plaza de Recepcion.")
        return

    if plaza.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.18 ya estaba aplicado; no se alteró el estado del mundo.")
        caller.msg("Prueba: siza-eventset CAR-KAL-DAR-003 alert 1 | siza-decide Mara")
        return

    state = {}
    try:
        state = dict(plaza.db.world_event_state or {})
    except Exception:
        state = {}
    if "alert" not in state:
        state["alert"] = 0
    plaza.db.world_event_state = state

    rules = []
    for raw in _plain_list(plaza.db.world_event_rules):
        item = _record(raw)
        if item is not None:
            rules.append(item)

    rule = {
        "id": RULE_ID,
        "event_id": EVENT_ID,
        "enabled": True,
        "field": "alert",
        "op": "gte",
        "value": 1,
        "priority": 80,
        "target_room_id": PLAZA_ID,
        "target_room_key": "Plaza de Recepcion",
        "activity": "atendiendo una alerta urgente de prueba en la plaza",
        "npc_ids": [MARA_ID],
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

    plaza.db.world_event_rules = rules
    if plaza.db.world_event_instances is None:
        plaza.db.world_event_instances = []
    plaza.tags.add(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY)
    plaza.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    refresh_world_event_rules()

    caller.msg("Kalnaj Pilot v0.18 aplicado: productor persistente de WORLD EVENT.")
    caller.msg(f"Event site: Plaza de Recepcion ({PLAZA_ID}).")
    caller.msg("State prototype: alert=0 por defecto; no se sobrescribió si ya existía.")
    caller.msg(f"Rule {RULE_ID}: alert>=1 -> EVENT80 {EVENT_ID}.")
    caller.msg("Audience prototype: Mara Vensal únicamente; el evento no se escribió dentro del NPC.")
    caller.msg("Al llegar al target, Mara ACK el occurrence; mientras alert siga activo no vuelve a responder al mismo occurrence.")
    caller.msg("Si alert vuelve a 0 y luego a 1, nace un occurrence nuevo y el ACK se reinicia.")
    caller.msg("No se modificó supplies, jobs, fatigue, hora, posición ni claims.")
    caller.msg("Prueba: siza-eventset CAR-KAL-DAR-003 alert 1 | siza-decide Mara")


build()
