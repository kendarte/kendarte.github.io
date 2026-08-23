from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v04_npc_routine"
UPGRADE_CATEGORY = "siza_upgrade"


def find_mara():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if obj.db.npc_id == "NPC-KAL-DAR-MARA-001":
            return obj
    return None


def build():
    mara = find_mara()
    if not mara:
        caller.msg("No puedo aplicar v0.4: Mara Vensal no existe. Ejecute primero upgrade_pilot_v03.")
        return

    # No canonical home has been authored for Mara. Keep it unset instead of
    # silently turning the Cantina into her residence.
    mara.db.home_room_id = None
    mara.db.rest_room_id = "CAR-KAL-DAR-006"
    mara.db.work_room_id = "CAR-KAL-DAR-007"
    mara.db.routine = [
        {
            "id": "ROUTINE-MARA-CANTINA",
            "room_id": "CAR-KAL-DAR-006",
            "room_key": "Cantina de Turno",
            "activity": "haciendo una pausa en la cantina",
            "status": "prototype",
        },
        {
            "id": "ROUTINE-MARA-PLAZA",
            "room_id": "CAR-KAL-DAR-003",
            "room_key": "Plaza de Recepcion",
            "activity": "revisando avisos de los turnos en la plaza",
            "status": "prototype",
        },
        {
            "id": "ROUTINE-MARA-PESCADERIA",
            "room_id": "CAR-KAL-DAR-007",
            "room_key": "Pescaderia de Darsena",
            "activity": "atendiendo una tarea de trabajo en la pescadería",
            "status": "prototype",
        },
    ]

    # Mara already begins in the Cantina in the pilot. Starting index 0 means
    # the first simstep recognizes that node as reached and begins the route to Plaza.
    mara.db.routine_index = 0
    mara.db.current_activity = "haciendo una pausa en la cantina"
    mara.db.destination_id = "CAR-KAL-DAR-006"
    mara.db.simulation_enabled = True
    mara.db.canon_status = "prototype"
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.4 aplicado: rutina persistente de Mara activada.")
    caller.msg("La rutina es PROTOTYPE y avanza solo con siza-simstep; no hay reloj automático todavía.")
    caller.msg("No se definió vivienda para Mara; home_room_id permanece vacío.")
    caller.msg("Pruebas: siza-npcstate Mara | siza-simstep Mara")


build()
