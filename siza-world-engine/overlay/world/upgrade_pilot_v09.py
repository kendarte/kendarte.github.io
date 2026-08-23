from evennia import search_object, search_tag

from services.need_engine import NEED_SITE_CATEGORY, NEED_SITE_TAG


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v09_needs"
UPGRADE_CATEGORY = "siza_upgrade"
RULE_ID = "NEED-MARA-FATIGUE-001"
AFFORDANCE_ID = "AFFORDANCE-CANTINA-REST-001"


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


def find_mara():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if obj.db.npc_id == "NPC-KAL-DAR-MARA-001":
            return obj
    return None


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def build():
    mara = find_mara()
    cantina = find_room("Cantina de Turno", "CAR-KAL-DAR-006")
    if not mara or not cantina:
        caller.msg("No puedo aplicar v0.9: falta Mara Vensal o Cantina de Turno.")
        return

    try:
        already = mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    except Exception:
        already = False

    if already:
        caller.msg("Kalnaj Pilot v0.9 ya estaba aplicado; no se reinició fatigue.")
        caller.msg("Use siza-needs Mara para inspeccionar el estado actual.")
        return

    needs = _plain_dict(mara.db.needs)
    if "fatigue" not in needs:
        needs["fatigue"] = 2
    mara.db.needs = needs

    rules = []
    found_rule = False
    for raw in _plain_list(mara.db.need_rules):
        try:
            rule = {str(key): value for key, value in raw.items()}
        except Exception:
            rules.append(raw)
            continue
        if str(rule.get("id") or "") == RULE_ID:
            found_rule = True
            rule = {
                "id": RULE_ID,
                "enabled": True,
                "need_key": "fatigue",
                "op": "gte",
                "value": 7,
                "priority": 70,
                "affordance": "REST",
                "activity": "buscando un lugar donde descansar",
                "canon_status": "prototype",
            }
        rules.append(rule)

    if not found_rule:
        rules.append(
            {
                "id": RULE_ID,
                "enabled": True,
                "need_key": "fatigue",
                "op": "gte",
                "value": 7,
                "priority": 70,
                "affordance": "REST",
                "activity": "buscando un lugar donde descansar",
                "canon_status": "prototype",
            }
        )
    mara.db.need_rules = rules

    affordances = []
    found_affordance = False
    for raw in _plain_list(cantina.db.need_affordances):
        try:
            affordance = {str(key): value for key, value in raw.items()}
        except Exception:
            affordances.append(raw)
            continue
        if str(affordance.get("id") or "") == AFFORDANCE_ID:
            found_affordance = True
            affordance = {
                "id": AFFORDANCE_ID,
                "kind": "REST",
                "need_key": "fatigue",
                "enabled": True,
                "activity": "descansando en la cantina",
                "completion_effects": [
                    {"field": "fatigue", "op": "set", "value": 2}
                ],
                "canon_status": "prototype",
            }
        affordances.append(affordance)

    if not found_affordance:
        affordances.append(
            {
                "id": AFFORDANCE_ID,
                "kind": "REST",
                "need_key": "fatigue",
                "enabled": True,
                "activity": "descansando en la cantina",
                "completion_effects": [
                    {"field": "fatigue", "op": "set", "value": 2}
                ],
                "canon_status": "prototype",
            }
        )
    cantina.db.need_affordances = affordances
    cantina.tags.add(NEED_SITE_TAG, category=NEED_SITE_CATEGORY)
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.9 aplicado: NPC need state + world REST affordance.")
    caller.msg("Todo el contenido de necesidad de esta prueba tiene canon_status=prototype.")
    caller.msg("Mara.fatigue inicia en 2; fatigue >= 7 produce NEED priority=70.")
    caller.msg("Cantina ofrece REST; al resolverlo, fatigue vuelve a 2.")
    caller.msg("No hay incremento automático de fatigue todavía.")
    caller.msg("Prueba: siza-needs Mara | siza-needset Mara fatigue 9")


build()
