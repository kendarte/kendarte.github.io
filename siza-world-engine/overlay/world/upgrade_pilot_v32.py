from evennia import search_object

from services.world_event_engine import (
    EVENT_SITE_CATEGORY,
    EVENT_SITE_TAG,
    refresh_world_event_rules,
)


UPGRADE_TAG = "kalnaj_pilot_v32_event_awareness"
UPGRADE_CATEGORY = "siza_upgrade"
PESCADERIA_ID = "CAR-KAL-DAR-007"
PLAZA_ID = "CAR-KAL-DAR-003"
RULE_ID = "TEST-RULE-PESCADERIA-LOCAL-ALERT-001"
EVENT_ID = "TEST-WORLD-EVENT-PESCADERIA-LOCAL-001"
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


def _find_room(name, room_id):
    for obj in search_object(name):
        if str(getattr(obj.db, "room_id", "") or "") == room_id:
            return obj
    return None


def build():
    site = _find_room("Pescaderia de Darsena", PESCADERIA_ID)
    plaza = _find_room("Plaza de Recepcion", PLAZA_ID)
    if not site or not plaza:
        caller.msg("No puedo aplicar v0.32: falta Pescaderia o Plaza de Recepcion.")
        return

    if site.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.32 ya estaba aplicado; no se duplicó el evento local.")
        return

    try:
        state = dict(site.db.world_event_state or {})
    except Exception:
        state = {}
    if "local_alert" not in state:
        state["local_alert"] = 0
    site.db.world_event_state = state

    rules = []
    for raw in _plain_list(site.db.world_event_rules):
        item = _record(raw)
        if item is not None:
            rules.append(item)

    rule = {
        "id": RULE_ID,
        "event_id": EVENT_ID,
        "enabled": True,
        "goal_type": "EVENT",
        "field": "local_alert",
        "op": "gte",
        "value": 1,
        "priority": 75,
        "response_mode": "ACK",
        "target_room_id": PLAZA_ID,
        "target_room_key": "Plaza de Recepcion",
        "activity": "reportando un incidente local de prueba ocurrido en la pescaderia",
        "npc_ids": [MARA_ID, WORKER_B_ID],
        "job_ids": [],
        "faction_ids": [],
        "awareness_mode": "LOCAL",
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

    site.db.world_event_rules = rules
    if site.db.world_event_instances is None:
        site.db.world_event_instances = []
    site.tags.add(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY)
    site.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    refresh_world_event_rules()

    caller.msg("Kalnaj Pilot v0.32 aplicado: Perception / Event Awareness.")
    caller.msg(f"Harness: {EVENT_ID} | source=Pescaderia | target=Plaza | priority=75 | awareness=LOCAL.")
    caller.msg("Audience: Mara + Trabajador B, pero cada occurrence congela aware_npc_ids según quién estaba físicamente en Pescaderia al activarse.")
    caller.msg("Llegar tarde al lugar no añade awareness retroactivamente; una nueva occurrence toma un snapshot nuevo.")
    caller.msg("Órdenes conservan comunicación directa y DANGER conserva semántica ambiental en v0.32.")
    caller.msg("No se modificó hora, posición, supplies, jobs, claims, skills, Knowledge, traits, memories, relationships, orders ni dangers.")
    caller.msg("Prueba: siza-events | siza-eventset CAR-KAL-DAR-007 local_alert 1")


build()
