from evennia import search_tag

from services.consequence_engine import (
    CONSEQUENCE_BUILD,
    consequence_rules,
    get_consequence_registry,
    upsert_consequence_rule,
)


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v36_consequence_social_intent"
UPGRADE_CATEGORY = "siza_upgrade"

WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
INFORMANT_ID = "TEST-NPC-KAL-DAR-INFORMANT-C"
EVENT_ID = "TEST-WORLD-EVENT-PESCADERIA-LOCAL-001"
RULE_ID = "TEST-CONSEQUENCE-LOCAL-EVENT-INFORM-C-001"


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == str(npc_id):
            return obj
    return None


def build():
    worker = _find_npc(WORKER_ID)
    informant = _find_npc(INFORMANT_ID)
    if not worker or not informant:
        caller.msg("No puedo aplicar v0.36: faltan Trabajador B o Informante C.")
        return

    if worker.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.36 ya estaba aplicado; no se duplicó la consequence rule.")
        return

    existing_rules = {
        str(item.get("id") or ""): item
        for item in consequence_rules()
        if item.get("id")
    }
    previous = existing_rules.get(RULE_ID, {})
    rule = {
        "id": RULE_ID,
        "enabled": bool(previous.get("enabled", False)),
        "when": {
            "action_type": "EVENT_ACKNOWLEDGED",
            "event_id": EVENT_ID,
            "actor_npc_id": WORKER_ID,
        },
        "recipient_mode": "ACTOR",
        "social_intent": {
            "kind": "INFORM",
            "target_npc_id": INFORMANT_ID,
            "event_id": "$event_id",
            "occurrence": "$occurrence",
            "priority": 55,
        },
        "canon_status": "prototype",
    }
    upsert_consequence_rule(rule)
    registry = get_consequence_registry(create=True)
    registry.db.build = CONSEQUENCE_BUILD
    worker.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.36 aplicado: Consequence-driven Social Intent.")
    caller.msg(
        f"Rule: {RULE_ID} | EVENT_ACKNOWLEDGED {EVENT_ID} por Trabajador B -> INFORM a Informante C priority=55 | DISABLED."
    )
    caller.msg("El occurrence se toma de la acción real mediante $occurrence; no queda fijado a una prueba concreta.")
    caller.msg("Sin esta rule habilitada, atender un EVENT no crea ninguna obligación social automática.")
    caller.msg("No se modificó posición, hora, events, jobs, claims, skills, Knowledge, traits, memories, relationships, orders, factions ni dangers.")
    caller.msg("Prueba: siza-consequences | siza-consequence-toggle TEST-CONSEQUENCE-LOCAL-EVENT-INFORM-C-001 on")


build()
