from evennia import search_object, search_tag

from services.world_event_engine import refresh_world_event_rules


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v23_authority_orders"
UPGRADE_CATEGORY = "siza_upgrade"
EVENT_SITE_TAG = "siza_event_site"
EVENT_SITE_CATEGORY = "siza_world_event"

MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
PLAZA_ID = "CAR-KAL-DAR-003"
ORDER_RULE_ID = "TEST-RULE-AUTHORITY-ORDER-001"
ORDER_ID = "TEST-AUTHORITY-ORDER-REPORT-001"
AUTHORITY_ID = "TEST-AUTHORITY-DARSENA"
MARA_MOD_ID = "TEST-PERSONALITY-MARA-ORDER-001"
WORKER_MOD_ID = "TEST-PERSONALITY-WORKER-B-ORDER-001"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


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


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == npc_id:
            return obj
    return None


def _find_plaza():
    for obj in search_object("Plaza de Recepcion"):
        if str(getattr(obj.db, "room_id", "") or "") == PLAZA_ID:
            return obj
    return None


def _upsert_modifier(npc, modifier):
    output = []
    replaced = False
    for raw in _plain_list(getattr(npc.db, "decision_modifiers", [])):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == str(modifier.get("id") or ""):
            output.append(dict(modifier))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(modifier))
    npc.db.decision_modifiers = output


def _upsert_rule(site, rule):
    output = []
    replaced = False
    for raw in _plain_list(site.db.world_event_rules):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == str(rule.get("id") or ""):
            output.append(dict(rule))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(rule))
    site.db.world_event_rules = output


def build():
    mara = _find_npc(MARA_ID)
    worker = _find_npc(WORKER_ID)
    plaza = _find_plaza()
    if not mara or not worker or not plaza:
        caller.msg("No puedo aplicar v0.23: faltan Mara, Trabajador B o Plaza de Recepcion.")
        return

    if plaza.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.23 ya estaba aplicado; no se reescribieron orders ni modifiers.")
        return

    state = _plain_dict(plaza.db.world_event_state)
    if "test_authority_order" not in state:
        state["test_authority_order"] = 0
        plaza.db.world_event_state = state

    _upsert_rule(
        plaza,
        {
            "id": ORDER_RULE_ID,
            "event_id": ORDER_ID,
            "enabled": True,
            "goal_type": "ORDER",
            "response_mode": "ACK",
            "field": "test_authority_order",
            "op": "gte",
            "value": 1,
            "activate_value": 1,
            "deactivate_value": 0,
            "priority": 60,
            "target_room_id": PLAZA_ID,
            "target_room_key": plaza.key,
            "activity": "presentándose ante una autoridad de prueba en la plaza",
            "npc_ids": [MARA_ID, WORKER_ID],
            "job_ids": [],
            "authority_id": AUTHORITY_ID,
            "authority_name": "Autoridad de Prueba de Darsena",
            "issuer_id": None,
            "issuer_name": None,
            "order_kind": "DIRECTIVE",
            "canon_status": "prototype",
        },
    )
    plaza.tags.add(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY)
    if plaza.db.world_event_instances is None:
        plaza.db.world_event_instances = []

    _upsert_modifier(
        mara,
        {
            "id": MARA_MOD_ID,
            "enabled": False,
            "value": -15,
            "when": {"type": "ORDER"},
            "kind": "DECISION_BIAS",
            "canon_status": "prototype",
        },
    )
    _upsert_modifier(
        worker,
        {
            "id": WORKER_MOD_ID,
            "enabled": False,
            "value": 20,
            "when": {"type": "ORDER"},
            "kind": "DECISION_BIAS",
            "canon_status": "prototype",
        },
    )

    refresh_world_event_rules()
    plaza.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.23 aplicado: Authority / Orders persistentes.")
    caller.msg(f"Orden prototype: {ORDER_ID} | authority={AUTHORITY_ID} | base_priority=60 | INACTIVE.")
    caller.msg("Audience prototype: Mara y Trabajador B; la orden existe fuera de ambos NPCs.")
    caller.msg(f"Mara harness: {MARA_MOD_ID} | ORDER -15 | DISABLED.")
    caller.msg(f"Worker B harness: {WORKER_MOD_ID} | ORDER +20 | DISABLED.")
    caller.msg("Cada receptor completa la misma occurrence por separado; retirar y reemitir crea una occurrence nueva.")
    caller.msg("No se creó ninguna facción ni membership; eso queda para la siguiente capa.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, relationships, events ni dangers.")
    caller.msg("Prueba: siza-orders | siza-order-toggle TEST-AUTHORITY-ORDER-REPORT-001 on")


build()
