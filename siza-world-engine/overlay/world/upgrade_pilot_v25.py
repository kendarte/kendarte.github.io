from evennia import search_object, search_tag

from services.faction_engine import (
    faction_definition,
    membership_for,
    upsert_faction,
    upsert_membership,
)
from services.world_event_engine import refresh_world_event_rules


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v25_faction_rank_authority"
UPGRADE_CATEGORY = "siza_upgrade"
EVENT_SITE_TAG = "siza_event_site"
EVENT_SITE_CATEGORY = "siza_world_event"

MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
PLAZA_ID = "CAR-KAL-DAR-003"
FACTION_ID = "TEST-FACTION-DARSENA"
AUTHORITY_ID = "TEST-AUTHORITY-DARSENA"
RANK_MEMBER = "TEST_MEMBER"
RANK_SUPERVISOR = "TEST_SUPERVISOR"
ORDER_RULE_ID = "TEST-RULE-RANKED-ORDER-001"
ORDER_ID = "TEST-RANKED-ORDER-REPORT-001"


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
        caller.msg("No puedo aplicar v0.25: faltan Mara, Trabajador B o Plaza de Recepcion.")
        return

    if plaza.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.25 ya estaba aplicado; no se reescribieron rangos ni memberships.")
        return

    faction = dict(faction_definition(FACTION_ID) or {})
    ranks = _plain_dict(faction.get("ranks"))
    ranks[RANK_MEMBER] = {
        "id": RANK_MEMBER,
        "name": "Miembro de Prueba",
        "authority_level": 10,
        "canon_status": "prototype",
    }
    ranks[RANK_SUPERVISOR] = {
        "id": RANK_SUPERVISOR,
        "name": "Supervisor de Prueba",
        "authority_level": 30,
        "canon_status": "prototype",
    }
    faction.update(
        {
            "id": FACTION_ID,
            "name": faction.get("name") or "Faccion de Prueba de Darsena",
            "active": True,
            "kind": faction.get("kind") or "TEST_AUTHORITY_GROUP",
            "ranks": ranks,
            "canon_status": "prototype",
        }
    )
    upsert_faction(faction)

    mara_membership = dict(membership_for(mara, FACTION_ID) or {})
    mara_membership.update(
        {
            "faction_id": FACTION_ID,
            "active": bool(mara_membership.get("active", True)),
            "role": mara_membership.get("role") or "TEST_MEMBER",
            "rank_id": RANK_MEMBER,
            "rank": "Miembro de Prueba",
            "loyalty_bias": int(mara_membership.get("loyalty_bias", -10) or 0),
            "canon_status": "prototype",
        }
    )
    mara_membership.pop("authority_level", None)
    upsert_membership(mara, mara_membership)

    worker_membership = dict(membership_for(worker, FACTION_ID) or {})
    worker_membership.update(
        {
            "faction_id": FACTION_ID,
            "active": bool(worker_membership.get("active", True)),
            "role": worker_membership.get("role") or "TEST_MEMBER",
            "rank_id": RANK_SUPERVISOR,
            "rank": "Supervisor de Prueba",
            "loyalty_bias": int(worker_membership.get("loyalty_bias", 10) or 0),
            "canon_status": "prototype",
        }
    )
    worker_membership.pop("authority_level", None)
    upsert_membership(worker, worker_membership)

    state = _plain_dict(plaza.db.world_event_state)
    if "test_ranked_order" not in state:
        state["test_ranked_order"] = 0
        plaza.db.world_event_state = state

    _upsert_rule(
        plaza,
        {
            "id": ORDER_RULE_ID,
            "event_id": ORDER_ID,
            "enabled": True,
            "goal_type": "ORDER",
            "response_mode": "ACK",
            "field": "test_ranked_order",
            "op": "gte",
            "value": 1,
            "activate_value": 1,
            "deactivate_value": 0,
            "priority": 55,
            "target_room_id": PLAZA_ID,
            "target_room_key": plaza.key,
            "activity": "respondiendo a una orden jerarquica de prueba en la plaza",
            "npc_ids": [],
            "job_ids": [],
            "faction_ids": [FACTION_ID],
            "faction_id": FACTION_ID,
            "authority_id": AUTHORITY_ID,
            "authority_name": "Autoridad de Prueba de Darsena",
            "issuer_id": None,
            "issuer_name": None,
            "required_issuer_authority": 20,
            "issuer_rank_ids": [],
            "recipient_rank_ids": [RANK_MEMBER],
            "recipient_roles": [],
            "exclude_issuer": True,
            "order_kind": "RANKED_DIRECTIVE",
            "canon_status": "prototype",
        },
    )
    plaza.tags.add(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY)
    if plaza.db.world_event_instances is None:
        plaza.db.world_event_instances = []
    if plaza.db.world_order_issue_context is None:
        plaza.db.world_order_issue_context = {}

    refresh_world_event_rules()
    plaza.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.25 aplicado: Faction Rank + Authority.")
    caller.msg(f"{FACTION_ID}: {RANK_MEMBER}=authority10 | {RANK_SUPERVISOR}=authority30.")
    caller.msg(f"Mara -> {RANK_MEMBER}; Trabajador B -> {RANK_SUPERVISOR}. Loyalty v0.24 preservada.")
    caller.msg(
        f"Orden prototype: {ORDER_ID} | required_issuer_authority=20 | recipient_rank={RANK_MEMBER} | INACTIVE."
    )
    caller.msg("La autoridad mínima pertenece a esta orden; no existe una regla universal de obediencia por rango.")
    caller.msg("Al emitir, la audiencia se congela con los miembros elegibles de ese occurrence.")
    caller.msg("siza-order-toggle sigue siendo un bypass de debug; siza-order-issue sí valida autoridad real.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, relationships, events ni dangers.")
    caller.msg(f"Prueba: siza-order-authority {ORDER_ID} Mara | siza-order-authority {ORDER_ID} Trabajador B")


build()
