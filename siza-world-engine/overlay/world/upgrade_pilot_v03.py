from evennia import create_object, search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
DOOR_GROUP = "DOOR-KAL-DAR-TRASTIENDA"
DOOR_CATEGORY = "siza_door"


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def find_exit(exit_id, keys):
    for key in keys:
        for obj in search_object(key):
            if obj.db.exit_id == exit_id:
                return obj
    return None


def find_entity(attr_name, attr_value):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if getattr(obj.db, attr_name, None) == attr_value:
            return obj
    return None


def ensure_world_object(location):
    existing = find_entity("object_id", "OBJ-KAL-DAR-CANTINA-001")
    if existing:
        return existing, False

    obj = create_object(
        "typeclasses.siza_objects.WorldObject",
        key="Tablilla de turnos",
        aliases=["tablilla", "tabla de turnos", "turnos"],
        location=location,
        tags=[(ENTITY_TAG, ENTITY_CATEGORY)],
        attributes=[
            ("object_id", "OBJ-KAL-DAR-CANTINA-001"),
            ("desc", "Una tablilla de servicio recoge referencias de turnos para el personal de la dársena."),
            ("portable", False),
            ("state", {"condition": "usable"}),
            ("canon_status", "prototype"),
        ],
    )
    return obj, True


def ensure_mara(location):
    existing = find_entity("npc_id", "NPC-KAL-DAR-MARA-001")
    if existing:
        return existing, False

    npc = create_object(
        "typeclasses.npcs.NPC",
        key="Mara Vensal",
        aliases=["Mara"],
        location=location,
        tags=[(ENTITY_TAG, ENTITY_CATEGORY)],
        attributes=[
            ("npc_id", "NPC-KAL-DAR-MARA-001"),
            ("desc", "Mara Vensal viste ropa de trabajo práctica y lleva una libreta pequeña sujeta al cinturón."),
            ("canon_status", "prototype"),
            ("job", {"id": "JOB-DARSENA-TEST", "name": "trabajadora de dársena", "status": "prototype"}),
            ("knowledge", {"TURNOS": 2, "PESCADERIA": 2, "CANTINA": 1, "INGENIERIA_MANARAL": 0}),
            ("knowledge_facts", [
                {
                    "id": "MARA-KNOW-TURNOS-001",
                    "topic": "turnos",
                    "aliases": ["turno", "turnos", "carga"],
                    "knowledge_key": "TURNOS",
                    "required_level": 1,
                    "response": "Mara asiente. «La Plaza de Recepción es donde las familias y los trabajadores esperan noticias de los turnos.»",
                },
                {
                    "id": "MARA-KNOW-PESCADERIA-001",
                    "topic": "pescadería",
                    "aliases": ["pescaderia", "pescadería", "trastienda"],
                    "knowledge_key": "PESCADERIA",
                    "required_level": 1,
                    "response": "Mara responde: «La pescadería comunica con una trastienda mediante una puerta.»",
                },
                {
                    "id": "MARA-KNOW-CANTINA-001",
                    "topic": "cantina",
                    "aliases": ["cantina", "bar"],
                    "knowledge_key": "CANTINA",
                    "required_level": 1,
                    "response": "Mara responde: «La cantina funciona como un local de servicio de las dársenas.»",
                },
            ]),
            ("dialogue_greeting", "Mara Vensal te presta atención."),
            ("memories", []),
            ("relationships", {}),
        ],
    )
    return npc, True


def upgrade_room_profiles(cantina, pescaderia, trastienda):
    cantina.db.space_profile = {
        "room_type": "interior / local de servicio",
        "scale": "pequeña",
        "geometry": "una sala principal rectangular",
        "orientation": "el acceso comunica con la Plaza de Recepción",
        "focal_points": ["un mostrador de servicio ocupa parte de una pared lateral"],
        "status": "prototype",
    }
    pescaderia.db.space_profile = {
        "room_type": "interior / local de trabajo y comercio",
        "scale": "pequeña",
        "geometry": "un espacio principal de atención con una zona de trabajo al fondo",
        "orientation": "la salida comunica con la Calle de Servicio y la trastienda se conecta mediante una puerta",
        "focal_points": ["un mostrador de trabajo organiza la zona de atención"],
        "status": "prototype",
    }
    trastienda.db.space_profile = {
        "room_type": "interior / almacenamiento",
        "scale": "muy pequeña",
        "geometry": "un único recinto de almacenaje",
        "orientation": "la puerta comunica directamente con la pescadería",
        "focal_points": ["varias cajas ocupan parte del espacio de almacenamiento"],
        "status": "prototype",
    }


def upgrade_door():
    door_in = find_exit(
        "EXIT-KAL-DAR-007-A",
        ["abrir la puerta de la trastienda", "entrar a la trastienda"],
    )
    door_out = find_exit(
        "EXIT-KAL-DAR-007-B",
        ["volver a la pescaderia", "volver a la pescadería"],
    )
    if not door_in or not door_out:
        return False

    door_in.key = "entrar a la trastienda"
    door_out.key = "volver a la pescadería"

    for exit_obj in (door_in, door_out):
        exit_obj.db.door_group_id = DOOR_GROUP
        exit_obj.db.door_name = "la puerta de la trastienda"
        exit_obj.tags.add(DOOR_GROUP, category=DOOR_CATEGORY)

    return True


def build():
    cantina = find_room("Cantina de Turno", "CAR-KAL-DAR-006")
    pescaderia = find_room("Pescaderia de Darsena", "CAR-KAL-DAR-007")
    trastienda = find_room("Trastienda de la Pescaderia", "CAR-KAL-DAR-008")

    missing = [
        name for name, obj in [
            ("Cantina", cantina),
            ("Pescadería", pescaderia),
            ("Trastienda", trastienda),
        ] if not obj
    ]
    if missing:
        caller.msg("No puedo aplicar v0.3. Faltan Rooms: " + ", ".join(missing))
        return

    upgrade_room_profiles(cantina, pescaderia, trastienda)
    obj, obj_created = ensure_world_object(cantina)
    mara, mara_created = ensure_mara(cantina)
    door_ok = upgrade_door()

    caller.msg("Kalnaj Pilot v0.3 aplicado sin reconstruir Rooms.")
    caller.msg(f"Objeto persistente: {obj.key} ({'creado' if obj_created else 'ya existía'}).")
    caller.msg(f"NPC persistente: {mara.key} ({'creado' if mara_created else 'ya existía'}).")
    caller.msg("Puerta Pescadería/Trastienda enlazada." if door_ok else "ATENCION: no pude enlazar la puerta de la trastienda.")
    caller.msg("Todo el contenido nuevo de v0.3 tiene canon_status=prototype.")


build()
