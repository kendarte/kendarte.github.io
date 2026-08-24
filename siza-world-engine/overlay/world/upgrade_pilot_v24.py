from evennia import search_object, search_tag

from services.faction_engine import upsert_faction, upsert_membership
from services.world_event_engine import refresh_world_event_rules


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v24_faction_membership_loyalty"
UPGRADE_CATEGORY = "siza_upgrade"
EVENT_SITE_TAG = "siza_event_site"
EVENT_SITE_CATEGORY = "siza_world_event"

MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
PLAZA_ID = "CAR-KAL-DAR-003"
FACTION_ID = "TEST-FACTION-DARSENA"
AUTHORITY_ID = "TEST-AUTHORITY-DARSENA"
ORDER_RULE_ID = "TEST-RULE-FACTION-ORDER-001"
ORDER_ID = "TEST-FACTION-ORDER-REPORT-001"


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
        caller.msg("No puedo aplicar v0.24: faltan Mara, Trabajador B o Plaza de Recepcion.")
        return

    if plaza.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.24 ya estaba aplicado; no se reescribieron memberships ni loyalty_bias.")
        return

    upsert_faction(
        {
            "id": FACTION_ID,
            "name": "Faccion de Prueba de Darsena",
            "active": True,
            "kind": "TEST_AUTHORITY_GROUP",
            "canon_status": "prototype",
        }
    )

    upsert_membership(
        mara,
        {
            "faction_id": FACTION_ID,
            "active": True,
            "role": "TEST_MEMBER",
            "rank": "TEST_RANK",
            "loyalty_bias": -10,
            "canon_status": "prototype",
        },
    )
    upsert_membership(
        worker,
        {
            "faction_id": FACTION_ID,
            "active": True,
            "role": "TEST_MEMBER",
            "rank": "TEST_RANK",
            "loyalty_bias": 10,
            "canon_status": "prototype",
        },
    )

    state = _plain_dict(plaza.db.world_event_state)
    if "test_faction_order" not in state:
        state["test_faction_order"] = 0
        plaza.db.world_event_state = state

    _upsert_rule(
        plaza,
        {
            "id": ORDER_RULE_ID,
            "event_id": ORDER_ID,
            "enabled": True,
            "goal_type": "ORDER",
            "response_mode": "ACK",
            "field": "test_faction_order",
            "op": "gte",
            "value": 1,
            "activate_value": 1,
            "deactivate_value": 0,
            "priority": 55,
            "target_room_id": PLAZA_ID,
            "target_room_key": plaza.key,
            "activity": "respondiendo a una orden de faccion de prueba en la plaza",
            "npc_ids": [],
            "job_ids": [],
            "faction_ids": [FACTION_ID],
            "faction_id": FACTION_ID,
            "authority_id": AUTHORITY_ID,
            "authority_name": "Autoridad de Prueba de Darsena",
            "issuer_id": None,
            "issuer_name": None,
            "order_kind": "FACTION_DIRECTIVE",
            "canon_status": "prototype",
        },
    )
    plaza.tags.add(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY)
    if plaza.db.world_event_instances is None:
        plaza.db.world_event_instances = []

    refresh_world_event_rules()
    plaza.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.24 aplicado: Faction Membership + Loyalty.")
    caller.msg(f"Faction prototype: {FACTION_ID} | INDEPENDIENTE del canon.")
    caller.msg(f"Mara membership: active=True | loyalty_bias=-10 hacia {FACTION_ID}.")
    caller.msg(f"Worker B membership: active=True | loyalty_bias=+10 hacia {FACTION_ID}.")
    caller.msg(f"Orden prototype: {ORDER_ID} | base_priority=55 | audience=faction:{FACTION_ID} | INACTIVE.")
    caller.msg("La audiencia ya no enumera Mara/B: cualquier membership ACTIVA de esa faccion puede recibirla.")
    caller.msg("loyalty_bias sólo modifica ORDER cuando faction_id coincide; no cambia JOB/NEED/RELATIONSHIP ni otras facciones.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, relationships, events ni dangers.")
    caller.msg("Prueba: siza-factions | siza-factions Mara | siza-factions Trabajador B")


build()
