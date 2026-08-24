from evennia import search_tag

from services.consequence_engine import consequence_rules, get_consequence_registry, upsert_consequence_rule


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v37_information_shared_actions"
UPGRADE_CATEGORY = "siza_upgrade"

WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
INFORMANT_ID = "TEST-NPC-KAL-DAR-INFORMANT-C"
MARA_ID = "NPC-KAL-DAR-MARA-001"
EVENT_ID = "TEST-WORLD-EVENT-PESCADERIA-LOCAL-001"
RULE_ID = "TEST-CONSEQUENCE-INFORMATION-FORWARD-MARA-001"


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == str(npc_id):
            return obj
    return None


def build():
    worker = _find_npc(WORKER_ID)
    informant = _find_npc(INFORMANT_ID)
    mara = _find_npc(MARA_ID)
    if not worker or not informant or not mara:
        caller.msg("No puedo aplicar v0.37: faltan Trabajador B, Informante C o Mara.")
        return

    if informant.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.37 ya estaba aplicado; no se duplicó la consequence rule.")
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
            "action_type": "INFORMATION_SHARED",
            "event_id": EVENT_ID,
            "actor_npc_id": WORKER_ID,
            "target_npc_id": INFORMANT_ID,
        },
        "recipient_mode": "TARGET",
        "social_intent": {
            "kind": "INFORM",
            "target_npc_id": MARA_ID,
            "event_id": "$event_id",
            "occurrence": "$occurrence",
            "priority": 50,
        },
        "canon_status": "prototype",
    }
    upsert_consequence_rule(rule)
    registry = get_consequence_registry(create=True)
    informant.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.37 aplicado: INFORMATION_SHARED como acción encadenable.")
    caller.msg(
        f"Rule: {RULE_ID} | B comparte {EVENT_ID} con C -> C crea INFORM hacia Mara priority=50 | DISABLED."
    )
    caller.msg("La rule sólo responde a B -> C para este EVENT; no existe propagación universal ni broadcast automático.")
    caller.msg("El occurrence se toma de la transmisión real mediante $occurrence.")
    caller.msg("Informante C conserva simulation_enabled=False y decision_enabled=False; el harness no lo vuelve autónomo por defecto.")
    caller.msg("No se modificó posición, hora, events, información previa, jobs, claims, skills, Knowledge, traits, memories, orders, factions ni dangers.")
    caller.msg("Prueba: siza-consequences | siza-consequence-toggle TEST-CONSEQUENCE-INFORMATION-FORWARD-MARA-001 on")


build()
