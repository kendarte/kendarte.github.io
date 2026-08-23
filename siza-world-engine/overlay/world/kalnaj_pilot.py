from evennia import create_object, search_tag

SEED_TAG = "kalnaj_pilot_v01"
SEED_CATEGORY = "siza_seed"


def room(key, room_id, desc, sensory=None, canon_status="prototype"):
    obj = create_object(
        "typeclasses.rooms.Room",
        key=key,
        tags=[(SEED_TAG, SEED_CATEGORY)],
        attributes=[
            ("room_id", room_id),
            ("zone_id", "CAR-KAL-DARSENAS-CAMPANA"),
            ("region_id", "CAR-KALNAJ"),
            ("settlement_id", "CAR-KAL-KALNAJ"),
            ("district_id", "CAR-KAL-DARSENAS-CAMPANA"),
            ("desc", desc),
            ("sensory_facts", sensory or {}),
            ("canon_status", canon_status),
        ],
    )
    return obj


def connect(source, destination, key, exit_id, aliases=None, door_state="open", canon_status="prototype"):
    return create_object(
        "typeclasses.exits.Exit",
        key=key,
        aliases=aliases or [],
        location=source,
        destination=destination,
        tags=[(SEED_TAG, SEED_CATEGORY)],
        attributes=[
            ("exit_id", exit_id),
            ("door_state", door_state),
            ("is_locked", False),
            ("canon_status", canon_status),
        ],
    )


def two_way(a, b, a_to_b, b_to_a, base_id, aliases_ab=None, aliases_ba=None, canon_status="prototype"):
    connect(a, b, a_to_b, base_id + "A", aliases_ab, canon_status=canon_status)
    connect(b, a, b_to_a, base_id + "B", aliases_ba, canon_status=canon_status)


def build():
    existing = search_tag(SEED_TAG, category=SEED_CATEGORY)
    if existing:
        caller.msg("El seed Kalnaj Pilot v0.1 ya existe. No se crearon duplicados.")
        return

    embarcadero = room(
        "Embarcadero de Campana",
        "CAR-KAL-DAR-001",
        "Un embarcadero bajo de servicio recibe carga y personal de las Darsenas de Campana.",
        {"sight": ["superficies humedas", "carga minera"], "smell": ["humedad mineral"]},
        "derived",
    )
    patio = room(
        "Patio de Mineral",
        "CAR-KAL-DAR-002",
        "Un patio operativo donde la carga mineral pasa entre descenso, deposito y embarque.",
        {"sight": ["carga mineral humeda"], "hearing": ["trabajo de carga"]},
        "derived",
    )
    plaza = room(
        "Plaza de Recepcion",
        "CAR-KAL-DAR-003",
        "Un espacio de encuentro de las darsenas donde trabajadores y familias esperan noticias de los turnos.",
        {"sight": ["familias esperando", "trabajadores de turno"]},
        "derived",
    )
    calle = room(
        "Calle de Servicio",
        "CAR-KAL-DAR-004",
        "Una via de servicio conecta la plaza con locales de abastecimiento y dependencias de trabajo.",
        {"hearing": ["transito de carga y personal"]},
        "prototype",
    )
    remedio = room(
        "Casa de Remedio",
        "CAR-KAL-DAR-005",
        "Una Casa de Remedio atiende lesiones, agotamiento y necesidades de quienes regresan de los descensos.",
        {"smell": ["remedios", "telas limpias"]},
        "derived",
    )
    cantina = room(
        "Cantina de Turno",
        "CAR-KAL-DAR-006",
        "Un local de prueba usado para validar interiores, presencia de NPC y movimiento desde la plaza.",
        {"hearing": ["conversaciones bajas"]},
        "prototype",
    )
    pescaderia = room(
        "Pescaderia de Darsena",
        "CAR-KAL-DAR-007",
        "Un local de prueba usado para validar comercio, objetos y Knowledge dentro del piloto.",
        {"smell": ["salmuera", "pescado"], "sight": ["mostrador de trabajo"]},
        "prototype",
    )
    trastienda = room(
        "Trastienda de la Pescaderia",
        "CAR-KAL-DAR-008",
        "Una pequena trastienda de prueba separada del local principal por una puerta persistente.",
        {"sight": ["cajas de almacenamiento"]},
        "prototype",
    )

    two_way(
        embarcadero, patio,
        "hacia el patio", "hacia el embarcadero", "EXIT-KAL-DAR-001-",
        ["patio", "ir al patio", "voy al patio"],
        ["embarcadero", "ir al embarcadero", "voy al embarcadero"],
        "derived",
    )
    two_way(
        patio, plaza,
        "hacia la plaza", "hacia el patio", "EXIT-KAL-DAR-002-",
        ["plaza", "ir a la plaza", "voy a la plaza"],
        ["patio", "ir al patio", "voy al patio"],
        "prototype",
    )
    two_way(
        plaza, remedio,
        "entrar a la Casa de Remedio", "salir a la plaza", "EXIT-KAL-DAR-003-",
        ["casa de remedio", "remedio"], ["plaza"], "derived",
    )
    two_way(
        plaza, cantina,
        "entrar a la cantina", "salir a la plaza", "EXIT-KAL-DAR-004-",
        ["cantina", "bar", "voy al bar", "voy a la cantina"], ["plaza"], "prototype",
    )
    two_way(
        plaza, calle,
        "tomar la calle de servicio", "volver a la plaza", "EXIT-KAL-DAR-005-",
        ["calle", "calle de servicio"], ["plaza"], "prototype",
    )
    two_way(
        calle, pescaderia,
        "entrar a la pescaderia", "salir a la calle", "EXIT-KAL-DAR-006-",
        ["pescaderia", "voy a la pescaderia"], ["calle"], "prototype",
    )
    door_in = connect(
        pescaderia,
        trastienda,
        "abrir la puerta de la trastienda",
        "EXIT-KAL-DAR-007-A",
        ["trastienda", "ir a la trastienda"],
        door_state="open",
        canon_status="prototype",
    )
    connect(
        trastienda,
        pescaderia,
        "volver a la pescaderia",
        "EXIT-KAL-DAR-007-B",
        ["pescaderia", "salir"],
        door_state="open",
        canon_status="prototype",
    )
    door_in.db.prototype_test = "persistent_door_state"

    caller.move_to(embarcadero, quiet=True)
    caller.msg("Kalnaj Pilot v0.1 creado: 8 Rooms. Te movi al Embarcadero de Campana.")
    caller.msg("Prueba: patio -> plaza -> bar/cantina o calle -> pescaderia -> trastienda.")


build()
