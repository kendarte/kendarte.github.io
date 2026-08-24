from evennia import search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v33_event_information_propagation"
UPGRADE_CATEGORY = "siza_upgrade"
PESCADERIA_ID = "CAR-KAL-DAR-007"
MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_B_ID = "TEST-NPC-KAL-DAR-WORKER-B"


def _find_site():
    for obj in search_object("Pescaderia de Darsena"):
        if str(getattr(obj.db, "room_id", "") or "") == PESCADERIA_ID:
            return obj
    return None


def _find_npc(npc_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == str(npc_id):
            return obj
    return None


def build():
    site = _find_site()
    mara = _find_npc(MARA_ID)
    worker = _find_npc(WORKER_B_ID)
    if not site or not mara or not worker:
        caller.msg("No puedo aplicar v0.33: faltan Pescaderia, Mara o Trabajador B.")
        return

    if site.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.33 ya estaba aplicado; no se alteró información persistente.")
        return

    if mara.db.event_information is None:
        mara.db.event_information = {}
    if worker.db.event_information is None:
        worker.db.event_information = {}

    site.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.33 aplicado: Witness -> Communication -> Information.")
    caller.msg("aware_npc_ids sigue representando testigos directos y no se modifica al informar a otro NPC.")
    caller.msg("La información transmitida se guarda aparte en npc.db.event_information con source, occurrence y hops.")
    caller.msg("siza-inform exige que source conozca el occurrence y esté físicamente junto al target.")
    caller.msg("No hay broadcast automático, telepatía, rumor global ni trust/reputation en v0.33.")
    caller.msg("No se modificó hora, posición, events, jobs, claims, skills, Knowledge, traits, memories, relationships, orders, factions ni dangers.")
    caller.msg("Prueba: siza-information Mara | siza-information Trabajador B")


build()
