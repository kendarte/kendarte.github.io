from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v05_decision_layer"
UPGRADE_CATEGORY = "siza_upgrade"


def find_mara():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if obj.db.npc_id == "NPC-KAL-DAR-MARA-001":
            return obj
    return None


def build():
    mara = find_mara()
    if not mara:
        caller.msg("No puedo aplicar v0.5: Mara Vensal no existe.")
        return

    mara.db.decision_enabled = False
    mara.db.decision_priorities = {
        "DANGER": 100,
        "EVENT": 80,
        "NEED": 70,
        "JOB": 60,
        "RELATIONSHIP": 50,
        "ROUTINE": 10,
    }

    # These are prototype authored test goals. They are inactive until explicitly
    # toggled from the admin/debug commands. No need math or job schedule is frozen here.
    mara.db.decision_goals = [
        {
            "id": "TEST-EVENT-MARA-PLAZA-001",
            "type": "EVENT",
            "priority": 80,
            "active": False,
            "target_room_id": "CAR-KAL-DAR-003",
            "target_room_key": "Plaza de Recepcion",
            "activity": "revisando un aviso urgente de prueba en la plaza",
            "one_shot": True,
            "status": "prototype",
        },
        {
            "id": "TEST-JOB-MARA-PESCADERIA-001",
            "type": "JOB",
            "priority": 60,
            "active": False,
            "target_room_id": "CAR-KAL-DAR-007",
            "target_room_key": "Pescaderia de Darsena",
            "activity": "atendiendo una tarea de trabajo de prueba en la pescadería",
            "one_shot": True,
            "status": "prototype",
        },
    ]

    mara.db.current_goal = None
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.5 aplicado: Decision Layer inspectable instalado.")
    caller.msg("El World Tick SIGUE usando la rutina v0.4; decision_enabled=False.")
    caller.msg("No se congeló matemática de necesidades ni horarios de Job.")
    caller.msg("Prueba: siza-decide Mara")
    caller.msg("Evento de prueba: siza-goal-toggle Mara TEST-EVENT-MARA-PLAZA-001 on")


build()
