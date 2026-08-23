from evennia import search_object


UPGRADE_TAG = "kalnaj_pilot_v02_perception"


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def apply_room_data(room, space_profile=None, perception_facts=None):
    if not room:
        return False
    if room.tags.has(UPGRADE_TAG, category="siza_upgrade"):
        return True

    if space_profile is not None:
        room.db.space_profile = space_profile
    if perception_facts is not None:
        room.db.perception_facts = perception_facts

    room.tags.add(UPGRADE_TAG, category="siza_upgrade")
    return True


def build():
    cantina = find_room("Cantina de Turno", "CAR-KAL-DAR-006")
    pescaderia = find_room("Pescaderia de Darsena", "CAR-KAL-DAR-007")
    trastienda = find_room("Trastienda de la Pescaderia", "CAR-KAL-DAR-008")
    plaza = find_room("Plaza de Recepcion", "CAR-KAL-DAR-003")

    missing = [
        name
        for name, room in [
            ("Cantina", cantina),
            ("Pescaderia", pescaderia),
            ("Trastienda", trastienda),
            ("Plaza", plaza),
        ]
        if not room
    ]
    if missing:
        caller.msg("No puedo aplicar v0.2. Faltan Rooms: " + ", ".join(missing))
        return

    apply_room_data(
        cantina,
        {
            "room_type": "interior / local de servicio",
            "scale": "pequena",
            "geometry": "una sala principal rectangular",
            "orientation": "el acceso a la Plaza de Recepcion queda en uno de los extremos",
            "focal_points": ["un mostrador de servicio ocupa parte de una pared lateral"],
            "status": "prototype",
        },
        [
            {
                "id": "TEST-CANTINA-SIGHT-001",
                "sense": "sight",
                "difficulty": 4,
                "target": "mostrador",
                "keywords": ["mostrador", "barra", "cantina", "marcas"],
                "fact": "En el borde inferior del mostrador hay marcas recientes de roce.",
            },
            {
                "id": "TEST-CANTINA-SIGHT-002",
                "sense": "sight",
                "difficulty": 6,
                "target": "mostrador",
                "keywords": ["mostrador", "barra", "cantina", "marcas"],
                "fact": "Las marcas de roce cambian de direccion cerca del extremo del mostrador.",
            },
            {
                "id": "TEST-CANTINA-HEARING-001",
                "sense": "hearing",
                "difficulty": 5,
                "target": "conversaciones",
                "keywords": ["conversaciones", "voces", "escuchar", "cantina"],
                "fact": "Entre las conversaciones bajas se repite el nombre de un turno de carga.",
            },
        ],
    )

    apply_room_data(
        pescaderia,
        {
            "room_type": "interior / local de trabajo y comercio",
            "scale": "pequena",
            "geometry": "un espacio principal de atencion con zona de trabajo al fondo",
            "orientation": "la salida devuelve a la Calle de Servicio; la trastienda queda al fondo",
            "focal_points": ["mostrador de trabajo", "cajas de almacenamiento hacia el fondo"],
            "status": "prototype",
        },
        [
            {
                "id": "TEST-PESCADERIA-SIGHT-001",
                "sense": "sight",
                "difficulty": 4,
                "target": "cajas",
                "keywords": ["caja", "cajas", "fondo", "almacenamiento"],
                "fact": "Una de las cajas del fondo tiene marcas de manipulacion reciente.",
            },
            {
                "id": "TEST-PESCADERIA-SMELL-001",
                "sense": "smell",
                "difficulty": 6,
                "target": "cajas",
                "keywords": ["caja", "cajas", "olor", "salmuera"],
                "fact": "La salmuera es mas intensa junto a las cajas del fondo.",
            },
        ],
    )

    apply_room_data(
        trastienda,
        {
            "room_type": "interior / almacenamiento",
            "scale": "muy pequena",
            "geometry": "un solo recinto de almacenaje",
            "orientation": "la puerta comunica directamente con la pescaderia",
            "focal_points": ["cajas de almacenamiento"],
            "status": "prototype",
        },
        [
            {
                "id": "TEST-TRASTIENDA-SIGHT-001",
                "sense": "sight",
                "difficulty": 5,
                "target": "cajas",
                "keywords": ["caja", "cajas", "tapa", "almacenamiento"],
                "fact": "El polvo alrededor de la tapa de una caja esta alterado recientemente.",
            }
        ],
    )

    apply_room_data(
        plaza,
        {
            "room_type": "exterior / espacio de recepcion",
            "scale": "media",
            "geometry": "un espacio abierto que distribuye el paso hacia varios servicios de las darsenas",
            "orientation": "desde aqui se accede al patio, la Casa de Remedio, la cantina y la Calle de Servicio",
            "focal_points": ["familias esperando", "trabajadores de turno"],
            "status": "prototype",
        },
        [],
    )

    caller.msg("Kalnaj Pilot v0.2 aplicado sin reconstruir Rooms.")
    caller.msg("Datos nuevos: space_profile + perception_facts de prueba (status=prototype).")
    caller.msg("Pruebas: 'miro alrededor', 'examino el mostrador', 'escucho las conversaciones'.")


build()
