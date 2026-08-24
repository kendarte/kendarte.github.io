from evennia import create_object, search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v34_rumor_multihop"
UPGRADE_CATEGORY = "siza_upgrade"
TEST_TAG = "kalnaj_pilot_v34_information_receiver"
TEST_CATEGORY = "siza_test"
PLAZA_ID = "CAR-KAL-DAR-003"
RECEIVER_ID = "TEST-NPC-KAL-DAR-INFORMANT-C"


def _find_plaza():
    for obj in search_object("Plaza de Recepcion"):
        if str(getattr(obj.db, "room_id", "") or "") == PLAZA_ID:
            return obj
    return None


def _find_receiver():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == RECEIVER_ID:
            return obj
    return None


def _ensure_receiver(plaza):
    existing = _find_receiver()
    if existing:
        if existing.db.event_information is None:
            existing.db.event_information = {}
        return existing, False

    npc = create_object(
        "typeclasses.npcs.NPC",
        key="Informante de Prueba C",
        aliases=["Informante C", "Prueba C", "Informant C"],
        location=plaza,
        tags=[
            (ENTITY_TAG, ENTITY_CATEGORY),
            (TEST_TAG, TEST_CATEGORY),
        ],
        attributes=[
            ("npc_id", RECEIVER_ID),
            ("is_npc", True),
            ("desc", "NPC técnico para validar propagación multi-hop de información; no pertenece al canon."),
            ("canon_status", "prototype"),
            ("test_harness", True),
            ("simulation_enabled", False),
            ("decision_enabled", False),
            ("event_information", {}),
            ("knowledge", {}),
            ("knowledge_facts", []),
            ("memories", []),
            ("relationships", {}),
            ("current_activity", "esperando una prueba de información"),
        ],
    )
    return npc, True


def build():
    plaza = _find_plaza()
    if not plaza:
        caller.msg("No puedo aplicar v0.34: falta Plaza de Recepcion.")
        return

    if plaza.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.34 ya estaba aplicado; no se duplicó Informante de Prueba C.")
        return

    receiver, created = _ensure_receiver(plaza)
    receiver.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    plaza.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.34 aplicado: Rumor / Information Multi-Hop.")
    caller.msg(
        f"Harness: {receiver.key} ({'creado' if created else 'ya existía'}) | npc_id={RECEIVER_ID} | location=Plaza de Recepcion."
    )
    caller.msg("Informante C es prototype, no tiene job/facción/lore y simulation_enabled=False.")
    caller.msg("La cadena esperada es B(WITNESSED) -> Mara(REPORTED hop1) -> C(REPORTED hop2).")
    caller.msg("origin_npc_id debe seguir apuntando a B; source_npc_id pasa a Mara en el registro de C.")
    caller.msg("C no pertenece a la audiencia del EVENT y recibir información no lo convierte en destinatario mecánico.")
    caller.msg("No se modificó ningún NPC existente, event, occurrence, posición, hora, job, claim, skill, Knowledge, trait, memoria, relación, orden, facción ni danger.")
    caller.msg("Prueba: siza-information Mara | siza-information Informante C")


build()
