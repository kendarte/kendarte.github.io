from evennia import create_object, search_object, search_tag

from services.consequence_engine import upsert_consequence_rule
from services.knowledge_fact_engine import upsert_knowledge_fact


SEED_TAG = "darkhaven_academy_v01"
SEED_CATEGORY = "siza_campaign_seed"
ENTITY_TAG = "darkhaven_academy_entity_v01"
ENTITY_CATEGORY = "siza_campaign_entity"
CAMPAIGN_ID = "CAMPAIGN-DARKHAVEN-TUTORIAL-V01"

ENTRY_ROOM_ID = "DH7-ROOM-001"
COURTYARD_ROOM_ID = "DH7-ROOM-002"
KITCHEN_ROOM_ID = "DH7-ROOM-014"
TRAINING_ROOM_ID = "DH7-ROOM-010"
BRIEFING_ROOM_ID = "DH7-ROOM-009"

GEAR_OBJECT_ID = "OBJ-DH7-TUT-GEAR-001"
GEAR_ACTION_ID = "ACT-DH7-TUT-GEAR-001"
GEAR_RULE_ID = "RULE-DH7-TUT-GEAR-001"
TRAINING_OBJECT_ID = "OBJ-DH7-TUT-TRAINING-001"
TRAINING_ACTION_ID = "ACT-DH7-TUT-TRAINING-001"
TRAINING_RULE_ID = "RULE-DH7-TUT-TRAINING-001"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _upsert_by_id(rows, replacement):
    wanted = str(replacement.get("id") or "")
    output = []
    replaced = False
    for raw in _plain_list(rows):
        item = _record(raw)
        if not item:
            continue
        if str(item.get("id") or "") == wanted:
            output.append(dict(replacement))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(replacement))
    return output


def _find_by_attr(attr_name, value):
    wanted = str(value or "")
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, attr_name, "") or "") == wanted:
            return obj
    for obj in search_tag(SEED_TAG, category=SEED_CATEGORY):
        if str(getattr(obj.db, attr_name, "") or "") == wanted:
            return obj
    return None


def _ensure_aliases(obj, aliases):
    for alias in aliases or []:
        try:
            obj.aliases.add(alias)
        except Exception:
            pass


ROOMS = [
    ("DH7-ROOM-001", "Puerta de Darkhaven", "Acceso principal de la antigua prisión convertida en instituto. El portón mira al mar y todavía parece diseñado para decidir quién entra y quién no vuelve a salir.", "acceso fortificado", "DH7-ACCESS"),
    ("DH7-ROOM-002", "Patio Central de la Antigua Prisión", "Uno de los antiguos patios de castigo funciona ahora como corazón de circulación de Darkhaven. Uniformes negros, Mistcoats y órdenes de turno cruzan la piedra mojada.", "patio central", "DH7-CENTRAL"),
    ("DH7-ROOM-003", "Sala de Guardia", "Puesto operativo de seguridad interna. Aquí se cruzan turnos, llaves, informes y gente a la que Orlan ya conoce por la forma de caminar.", "sala operativa", "DH7-OPERATIONS"),
    ("DH7-ROOM-004", "Mando Regional de Sector 7", "Centro desde el que Sector 7 coordina puestos provinciales, especialistas y respuestas que superaron la capacidad local.", "centro de mando", "DH7-COMMAND"),
    ("DH7-ROOM-005", "Sala de Comunicaciones", "Equipos cristalinos y mecanismos físicos enlazan Darkhaven con faros, puestos y equipos desplegados por Caribia.", "comunicaciones", "DH7-COMMAND"),
    ("DH7-ROOM-006", "Dirección de Orphim Trimago", "El despacho de Trimago conserva la posición dominante de la antigua administración de la prisión. Desde aquí dirige una escuela, un cuartel y su experimento político favorito.", "despacho", "DH7-ADMIN"),
    ("DH7-ROOM-007", "Archivos de Sector 7", "Salas cerradas reúnen expedientes de incidentes, anomalías, expediciones, reliquias y operaciones que no caben en los registros de un puesto ordinario.", "archivo institucional", "DH7-RESEARCH"),
    ("DH7-ROOM-008", "Aulas de Darkhaven", "Vitrales, bancos y pizarras ocupan espacios donde antes sólo había disciplina carcelaria. Aquí se enseñan protocolos, campo, artefactos y teoría de niebla.", "aulas", "DH7-ACADEMIC"),
    ("DH7-ROOM-009", "Sala de Briefing de Fireteams", "Mapas físicos, tablillas de riesgo y listas de equipo rodean una mesa preparada para unidades que salen a faros, rescates y Deep Dives.", "briefing operativo", "DH7-ACADEMIC"),
    ("DH7-ROOM-010", "Patio de Entrenamiento y Esgrima", "Otro antiguo patio de castigo sirve ahora para esgrima, pruebas de coordinación y entrenamiento de Fireteams. Las marcas nuevas cubren cicatrices mucho más viejas.", "patio de entrenamiento", "DH7-TRAINING"),
    ("DH7-ROOM-011", "Dormitorios del Fireteam 7", "Antiguas celdas adaptadas alojan a los miembros del Fireteam 7. Cada puerta sigue teniendo proporciones carcelarias aunque detrás haya uniformes, Pages y pertenencias personales.", "dormitorios", "DH7-RESIDENTIAL"),
    ("DH7-ROOM-012", "Dormitorios Generales", "Un bloque de celdas transformado en residencia para estudiantes, asistentes y personal de turno.", "dormitorios", "DH7-RESIDENTIAL"),
    ("DH7-ROOM-013", "Comedor de Darkhaven", "Mesas largas convierten el comedor en uno de los pocos lugares donde rango, Fireteam, castigo y hambre terminan sentados demasiado cerca.", "comedor", "DH7-SUPPORT"),
    ("DH7-ROOM-014", "Cocina y Taller de Berta", "Berta cocina, repara, suelda, mezcla alquimia práctica y decide quién necesita comer antes de seguir haciendo estupideces.", "cocina-taller", "DH7-SUPPORT"),
    ("DH7-ROOM-015", "Laboratorio de Artefactos y Reliquias", "Mesas reforzadas reciben artefactos, Pages, reliquias y anomalías suficientemente estables como para estudiarlas sin enviarlas directamente a contención.", "laboratorio esotécnico", "DH7-RESEARCH"),
    ("DH7-ROOM-016", "Atelier de Relena Dao", "Telas tratadas, patrones, estructuras de Fashion Frame y herramientas finas ocupan el espacio impecable donde Relena diseña cuerpos, uniformes y santidad con la misma mirada técnica.", "atelier-laboratorio", "DH7-RESEARCH"),
    ("DH7-ROOM-017", "Taller FrameSmith de Maine", "Maine repara manacores, Spellblades, ManaDrivers y Deep Dive Frames entre bancos pesados, piezas abiertas y herramientas demasiado grandes para manos ordinarias.", "taller pesado", "DH7-HEAVY"),
    ("DH7-ROOM-018", "Bahía de Equipos Pesados y Deep Dive Frames", "Deep Dive Frames y equipos de contención pesada esperan inspección, carga o despliegue.", "bahía de equipo", "DH7-HEAVY"),
    ("DH7-ROOM-019", "Depósito de Equipo Darkhaven", "Respiradores, detectores, barreras, suministros y herramientas de respuesta llenan estanterías identificadas por puesto y nivel de riesgo.", "depósito", "DH7-HEAVY"),
    ("DH7-ROOM-020", "Enfermería de Respuesta", "Camillas y equipo médico reciben trauma, exposición y a cualquiera que regrese del campo con algo que no debería haber traído consigo.", "enfermería", "DH7-MEDICAL"),
    ("DH7-ROOM-021", "Aislamiento de Exposición", "Celdas médicas sellables mantienen separados a pacientes cuya niebla, memoria o cuerpo todavía no permiten confiar en una recuperación ordinaria.", "aislamiento", "DH7-CONTAINMENT"),
    ("DH7-ROOM-022", "Contención Compleja", "El bloque más restringido aprovecha la arquitectura carcelaria original para contener objetos, entidades y fenómenos que requieren algo más que una puerta cerrada.", "contención compleja", "DH7-CONTAINMENT"),
    ("DH7-ROOM-023", "Sala de Observación de Anomalías", "Una galería protegida permite documentar fenómenos contenidos sin entrar en contacto directo con ellos.", "observación", "DH7-CONTAINMENT"),
    ("DH7-ROOM-024", "Torre de Vigilancia", "Una antigua torre de guardia domina muros, mar y niebla. Darkhaven cambió de función; la necesidad de vigilar no.", "torre", "DH7-TOWERS"),
    ("DH7-ROOM-025", "Muelle de Despliegue", "Una plataforma operativa sobre el mar recibe transporte rápido, equipo pesado y Fireteams que salen de Sector 7 hacia incidentes provinciales.", "muelle operativo", "DH7-DEPLOYMENT"),
]

SENSORY = {
    "DH7-ROOM-001": {"sight": ["muros de antigua prisión", "portón de ingreso", "Mistcoats mojados"], "hearing": ["mar", "bisagras pesadas"], "smell": ["sal", "piedra húmeda"]},
    "DH7-ROOM-002": {"sight": ["patio de piedra", "estudiantes y agentes", "torres de vigilancia"], "hearing": ["órdenes", "pasos", "conversaciones"], "smell": ["lluvia", "sal"]},
    "DH7-ROOM-010": {"sight": ["armas de práctica", "blancos de entrenamiento"], "hearing": ["acero", "órdenes de Orlan"]},
    "DH7-ROOM-014": {"sight": ["fogones", "herramientas", "bultos de ingreso"], "hearing": ["cocina", "metal trabajado"], "smell": ["comida de Berta", "metal caliente"]},
    "DH7-ROOM-017": {"sight": ["ManaDrivers abiertos", "Deep Dive Frames en reparación"], "hearing": ["herramientas pesadas"], "smell": ["aceite", "metal"]},
    "DH7-ROOM-024": {"sight": ["mar", "niebla", "muros de Darkhaven"], "hearing": ["viento"]},
}

CONNECTIONS = [
    ("DH7-ROOM-001", "DH7-ROOM-002", "entrar al Patio Central", "volver al portón", "DH7-EXIT-001", ["DH-TUT-ARRIVAL"]),
    ("DH7-ROOM-002", "DH7-ROOM-003", "ir a la Sala de Guardia", "volver al Patio Central", "DH7-EXIT-002", []),
    ("DH7-ROOM-003", "DH7-ROOM-004", "ir al Mando Regional", "volver a Guardia", "DH7-EXIT-003", []),
    ("DH7-ROOM-004", "DH7-ROOM-005", "ir a Comunicaciones", "volver al Mando Regional", "DH7-EXIT-004", []),
    ("DH7-ROOM-004", "DH7-ROOM-006", "subir a Dirección", "bajar al Mando Regional", "DH7-EXIT-005", []),
    ("DH7-ROOM-006", "DH7-ROOM-007", "ir a los Archivos", "volver a Dirección", "DH7-EXIT-006", []),
    ("DH7-ROOM-007", "DH7-ROOM-015", "ir al Laboratorio de Artefactos", "volver a los Archivos", "DH7-EXIT-007", []),
    ("DH7-ROOM-015", "DH7-ROOM-016", "ir al Atelier de Relena", "volver al Laboratorio", "DH7-EXIT-008", []),
    ("DH7-ROOM-002", "DH7-ROOM-008", "ir a las Aulas", "volver al Patio Central", "DH7-EXIT-009", []),
    ("DH7-ROOM-008", "DH7-ROOM-009", "ir a Briefing de Fireteams", "volver a las Aulas", "DH7-EXIT-010", []),
    ("DH7-ROOM-009", "DH7-ROOM-010", "ir al Patio de Entrenamiento", "volver a Briefing", "DH7-EXIT-011", []),
    ("DH7-ROOM-010", "DH7-ROOM-009", "presentarme en Briefing", "volver al Patio de Entrenamiento", "DH7-EXIT-012", ["DH-TUT-BRIEFING"]),
    ("DH7-ROOM-002", "DH7-ROOM-011", "ir a Dormitorios del Fireteam 7", "volver al Patio Central", "DH7-EXIT-013", []),
    ("DH7-ROOM-011", "DH7-ROOM-012", "ir a Dormitorios Generales", "volver al Fireteam 7", "DH7-EXIT-014", []),
    ("DH7-ROOM-011", "DH7-ROOM-013", "ir al Comedor", "volver a Dormitorios", "DH7-EXIT-015", []),
    ("DH7-ROOM-013", "DH7-ROOM-014", "entrar a la Cocina de Berta", "volver al Comedor", "DH7-EXIT-016", []),
    ("DH7-ROOM-013", "DH7-ROOM-020", "ir a la Enfermería", "volver al Comedor", "DH7-EXIT-017", []),
    ("DH7-ROOM-020", "DH7-ROOM-021", "ir a Aislamiento", "volver a Enfermería", "DH7-EXIT-018", []),
    ("DH7-ROOM-003", "DH7-ROOM-019", "ir al Depósito de Equipo", "volver a Guardia", "DH7-EXIT-019", []),
    ("DH7-ROOM-019", "DH7-ROOM-017", "ir al Taller FrameSmith", "volver al Depósito", "DH7-EXIT-020", []),
    ("DH7-ROOM-017", "DH7-ROOM-018", "ir a la Bahía de Deep Dive", "volver al Taller FrameSmith", "DH7-EXIT-021", []),
    ("DH7-ROOM-018", "DH7-ROOM-025", "ir al Muelle de Despliegue", "volver a la Bahía", "DH7-EXIT-022", []),
    ("DH7-ROOM-015", "DH7-ROOM-022", "ir a Contención Compleja", "volver al Laboratorio", "DH7-EXIT-023", []),
    ("DH7-ROOM-022", "DH7-ROOM-023", "ir a Observación", "volver a Contención", "DH7-EXIT-024", []),
    ("DH7-ROOM-002", "DH7-ROOM-024", "subir a la Torre de Vigilancia", "bajar al Patio Central", "DH7-EXIT-025", []),
    ("DH7-ROOM-002", "DH7-ROOM-010", "ir al Patio de Entrenamiento", "volver al Patio Central", "DH7-EXIT-026", []),
]


def _find_room(room_id):
    return _find_by_attr("room_id", room_id)


def _ensure_room(room_id, key, desc, room_type, zone_id):
    room = _find_room(room_id)
    created = False
    if not room:
        room = create_object("typeclasses.rooms.Room", key=key, tags=[(SEED_TAG, SEED_CATEGORY)])
        created = True
    room.key = key
    room.db.room_id = room_id
    room.db.zone_id = zone_id
    room.db.region_id = "CARIBIA"
    room.db.settlement_id = "DARKHAVEN-ZONA-7"
    room.db.district_id = "DARKHAVEN-ZONA-7"
    room.db.desc = desc
    room.db.canon_status = "derived"
    room.db.campaign_id = CAMPAIGN_ID
    room.db.sensory_facts = SENSORY.get(room_id, {"sight": [], "hearing": [], "smell": [], "touch": [], "taste": []})
    room.db.space_profile = {
        "room_type": room_type,
        "scale": "mediana",
        "geometry": "arquitectura de antigua prisión adaptada al uso actual",
        "orientation": "Darkhaven Zona 7",
        "focal_points": [],
        "status": "vertical_slice",
    }
    room.db.world_state = _plain_dict(getattr(room.db, "world_state", {}))
    return room, created


def _ensure_exit(source, destination, key, exit_id, tags=None, aliases=None):
    exit_obj = _find_by_attr("exit_id", exit_id)
    created = False
    if not exit_obj:
        exit_obj = create_object(
            "typeclasses.exits.Exit",
            key=key,
            aliases=aliases or [],
            location=source,
            destination=destination,
            tags=[(ENTITY_TAG, ENTITY_CATEGORY)],
        )
        created = True
    exit_obj.key = key
    exit_obj.location = source
    exit_obj.destination = destination
    exit_obj.db.exit_id = exit_id
    exit_obj.db.door_state = "open"
    exit_obj.db.is_locked = False
    exit_obj.db.hidden = False
    exit_obj.db.canon_status = "vertical_slice"
    exit_obj.db.campaign_id = CAMPAIGN_ID
    exit_obj.db.campaign_tags = list(tags or [])
    _ensure_aliases(exit_obj, aliases or [])
    return exit_obj, created


def _orientation_fact():
    return {
        "id": "DH7-FACT-TUT-ORIENTATION-001",
        "topic": "ingreso a Darkhaven",
        "aliases": ["ingreso", "nuevo", "nueva", "qué hago", "que hago", "equipo", "berta", "mistcoat", "manadriver"],
        "knowledge_key": "DARKHAVEN_INGRESO",
        "required_level": 1,
        "campaign_tags": ["DH-TUT-ORIENTATION"],
        "canon_status": "vertical_slice",
        "text": (
            "Los recién llegados reciben su bulto de ingreso con Berta en la cocina. "
            "Desde el patio se pasa por los dormitorios del Fireteam 7 y el comedor. "
            "Después del equipo, Sir Orlan espera una prueba breve en el patio de entrenamiento antes del briefing."
        ),
        "response": (
            "«Si Trimago te dejó entrar, alguien cometió un error o espera algo de ti.» "
            "Squeek señala el bloque residencial. «Berta tiene tu bulto en la cocina: Mistcoat, ManaDriver de servicio y lo básico. "
            "Cruzas por dormitorios y comedor. Después Orlan te mira moverte en el patio de entrenamiento. "
            "Si no te rompe nada, el briefing está al lado.»"
        ),
    }


NPCS = [
    {
        "npc_id": "NPC-DH7-DINO", "key": "Dino", "room_id": "DH7-ROOM-001",
        "aliases": ["Dino"], "desc": "Estudiante terciario y asistente operativo. Funciona como rumor, reacción y textura cotidiana de Darkhaven.",
        "greeting": "Dino sostiene una tablilla bajo el portón. «Nereida, ¿verdad? El patio está al otro lado. Squeek sabe qué hicieron con tu ingreso. No te metas en Contención por accidente.»",
        "job": {"id": "ROLE-DH7-STUDENT-ASSISTANT", "name": "Estudiante terciario · Asistente operativo"},
        "knowledge": {"DARKHAVEN": 3, "DARKHAVEN_INGRESO": 2}, "fact": _orientation_fact(),
    },
    {
        "npc_id": "NPC-DH7-SQUEEK", "key": "Squeek", "room_id": "DH7-ROOM-002",
        "aliases": ["Squeek"], "desc": "Estudiante terciario y asistente operativo. Vive entre pasillos, rumores y pequeños trabajos de Darkhaven.",
        "greeting": "Squeek te mira como si ya hubiera oído que llegabas. «¿Ingreso? Sí. Pregunta antes de acabar cargando cajas durante seis horas.»",
        "job": {"id": "ROLE-DH7-STUDENT-ASSISTANT", "name": "Estudiante terciario · Asistente operativo"},
        "knowledge": {"DARKHAVEN": 3, "DARKHAVEN_INGRESO": 3}, "fact": _orientation_fact(),
    },
    {
        "npc_id": "NPC-DH7-BASILIZA", "key": "Basiliza", "room_id": "DH7-ROOM-011", "aliases": ["Gwen"],
        "desc": "Estudiante voluntaria de estética gótica, elegante, precisa y peligrosa. Busca información sobre Trinasty bajo una identidad que nació de Gwen.",
        "greeting": "Basiliza te observa como si ya hubiera decidido qué parte de la verdad piensa decirte.",
        "job": {"id": "ROLE-FIRETEAM7-SUPPORT", "name": "Fireteam 7 · Support"},
        "knowledge": {"DARKHAVEN": 2, "TRINASTY": 3, "RELIQUIAS": 2},
        "combat": {"enabled": True, "deck_id": "starter_darkhaven_vigilancia_v01", "tcg_profile": {"role": "Support"}, "loadout": {}, "world_status": {}, "encounter_tags": ["DARKHAVEN", "FIRETEAM-7", "SUPPORT"]},
    },
    {
        "npc_id": "NPC-DH7-DRASHTON", "key": "Drashton Windrago", "room_id": "DH7-ROOM-011", "aliases": ["Drash", "Windrago"],
        "desc": "Heredero problemático de los dragones de tormenta Windrago. Arrogante, gracioso, brutal, carismático y peligrosamente cómodo en combate.",
        "greeting": "Drash sonríe como si cualquier conversación pudiera convertirse en una pelea entretenida.",
        "job": {"id": "ROLE-FIRETEAM7-DPS2", "name": "Fireteam 7 · DPS"},
        "knowledge": {"DARKHAVEN": 2, "WINDRAGO": 3, "COMBATE": 3},
        "combat": {"enabled": True, "deck_id": "vertical_dragon_thunder_classic", "tcg_profile": {"role": "DPS"}, "loadout": {}, "world_status": {}, "encounter_tags": ["DARKHAVEN", "FIRETEAM-7", "WINDRAGO", "DPS"]},
    },
    {
        "npc_id": "NPC-DH7-ROXY", "key": "Roxy Soleonus", "room_id": "DH7-ROOM-011", "aliases": ["Roxy", "Soleonus"],
        "desc": "DPS de la casa solar Soleonus. Provocadora, brillante socialmente, atrevida y mucho más perceptiva de lo que deja ver.",
        "greeting": "Roxy te dedica una mirada rápida que parece leer la habitación antes de responder.",
        "job": {"id": "ROLE-FIRETEAM7-DPS1", "name": "Fireteam 7 · DPS"},
        "knowledge": {"DARKHAVEN": 2, "SOLEONUS": 3, "COMBATE": 2},
        "combat": {"enabled": True, "deck_id": "starter_darkhaven_ruptura_v01", "tcg_profile": {"role": "DPS"}, "loadout": {}, "world_status": {}, "encounter_tags": ["DARKHAVEN", "FIRETEAM-7", "SOLEONUS", "DPS"]},
    },
    {
        "npc_id": "NPC-DH7-AXEL", "key": "Axel Likabalier", "room_id": "DH7-ROOM-011", "aliases": ["Axel", "Likabalier"],
        "desc": "Joven de una casa caballeresca en decadencia. Correcto, formal y cargado por la expectativa de restaurar su linaje.",
        "greeting": "Axel se endereza por reflejo antes de hablar, como si cada conversación también fuera una prueba de protocolo.",
        "job": {"id": "ROLE-FIRETEAM7-TANK", "name": "Fireteam 7 · Tank"},
        "knowledge": {"DARKHAVEN": 2, "LIKABALIER": 3, "CABALLERIA": 2},
        "combat": {"enabled": True, "deck_id": "starter_darkhaven_contencion_v01", "tcg_profile": {"role": "Tank"}, "loadout": {}, "world_status": {}, "encounter_tags": ["DARKHAVEN", "FIRETEAM-7", "LIKABALIER", "TANK"]},
    },
    {
        "npc_id": "NPC-DH7-TRIMAGO", "key": "Orphim Trimago", "room_id": "DH7-ROOM-006", "aliases": ["Trimago", "Director Trimago", "Orphim"],
        "desc": "Director de Darkhaven Zona 7. Carismático, oportunista, manipulador, brillante y peligrosamente encantador.",
        "greeting": "Trimago sonríe con la tranquilidad de alguien que ya está calculando para qué podría servirle esta conversación.",
        "job": {"id": "JOB-DH7-DIRECTOR", "name": "Director de Darkhaven Zona 7"},
        "knowledge": {"DARKHAVEN": 5, "SECTOR7": 5, "POLITICA": 4, "ANOMALIAS": 3},
    },
    {
        "npc_id": "NPC-DH7-RELENA", "key": "Relena Dao", "room_id": "DH7-ROOM-016", "aliases": ["Relena", "Pitonisa Dao"],
        "desc": "Pitonisa, estudiosa de artefactos, diseñadora de uniformes, Fashion Frames y parte del sistema de creación de spells de Darkhaven.",
        "greeting": "Relena aparta la vista de su trabajo con una calma impecable.",
        "job": {"id": "JOB-DH7-RELENA", "name": "Pitonisa · Artefactos y Fashion Frames"},
        "knowledge": {"DARKHAVEN": 4, "ARTEFACTOS": 5, "FASHION_FRAMES": 5, "TRINASTY": 4},
    },
    {"npc_id": "NPC-DH7-DAO-A", "key": "Gemela Dao A", "room_id": "DH7-ROOM-016", "aliases": ["gemela Dao", "gemela A"], "desc": "Homúnculo mágico creado a partir del ADN de Relena. Asistente y modelo de Fashion Frame.", "greeting": "La gemela espera una instrucción con una atención demasiado perfecta.", "job": {"id": "ROLE-DH7-DAO-ASSISTANT", "name": "Asistente de Relena"}, "knowledge": {"DARKHAVEN": 2, "FASHION_FRAMES": 3}},
    {"npc_id": "NPC-DH7-DAO-B", "key": "Gemela Dao B", "room_id": "DH7-ROOM-016", "aliases": ["gemela Dao", "gemela B"], "desc": "Homúnculo mágico creado a partir del ADN de Relena. Asistente y modelo de Fashion Frame.", "greeting": "La segunda gemela te mira con la misma serenidad ensayada que su hermana.", "job": {"id": "ROLE-DH7-DAO-ASSISTANT", "name": "Asistente de Relena"}, "knowledge": {"DARKHAVEN": 2, "FASHION_FRAMES": 3}},
    {
        "npc_id": "NPC-DH7-ORLAN", "key": "Sir Orlan", "room_id": "DH7-ROOM-010", "aliases": ["Orlan", "capitán Orlan"],
        "desc": "Viejo caballero, capitán de guardia y mentor de esgrima. No necesita mana para parecer más sólido que la mayoría de nobles.",
        "greeting": "Orlan te mide la postura, no el apellido. «Cuando tengas el equipo, prueba el blanco. No busco elegancia. Quiero ver si puedes terminar una acción cuando algo ofrece resistencia.»",
        "job": {"id": "JOB-DH7-ORLAN", "name": "Capitán de guardia · Mentor de esgrima"},
        "knowledge": {"DARKHAVEN": 3, "CABALLERIA": 5, "ESGRIMA": 5, "LIKABALIER": 4},
    },
    {
        "npc_id": "NPC-DH7-ARLITA", "key": "Arlita", "room_id": "DH7-ROOM-015", "aliases": ["pictomante"],
        "desc": "Pictomante de origen humilde, talentosa y amable. Acompaña exploraciones para crear nuevas Pages de criaturas, lugares y fenómenos.",
        "greeting": "Arlita cierra su cuaderno de trabajo y te presta atención.",
        "job": {"id": "JOB-DH7-ARLITA", "name": "Pictomante de campo"},
        "knowledge": {"DARKHAVEN": 3, "PICTOMANCIA": 5, "PAGES": 4, "ANOMALIAS": 3},
    },
    {
        "npc_id": "NPC-DH7-MAINE", "key": "Maine", "room_id": "DH7-ROOM-017", "aliases": ["FrameSmith"],
        "desc": "Mestia / Manabeast y FrameSmith pesado. Repara manacores, Spellblades, ManaDrivers y Deep Dive Frames.",
        "greeting": "Maine deja una herramienta pesada sobre el banco antes de mirarte.",
        "job": {"id": "JOB-DH7-MAINE", "name": "FrameSmith pesado"},
        "knowledge": {"DARKHAVEN": 3, "FRAMESMITH": 5, "MANACORES": 5, "DEEP_DIVE": 5},
    },
    {
        "npc_id": "NPC-DH7-BERTA", "key": "Berta", "room_id": "DH7-ROOM-014", "aliases": ["cocinera"],
        "desc": "Cocinera, alquimista, soldadora, carpintera, reparadora y consejera. Su comida parece castigo, pero funciona.",
        "greeting": "Berta mira el bulto marcado con tu nombre. «Ahí está lo tuyo. Reclámalo tú. Si no puedes resolver un bulto con una etiqueta, Orlan me lo devuelve.»",
        "job": {"id": "JOB-DH7-BERTA", "name": "Cocinera · Alquimista · Reparadora"},
        "knowledge": {"DARKHAVEN": 4, "COCINA": 5, "ALQUIMIA": 4, "REPARACION": 4},
    },
]


def _ensure_npc(spec):
    npc = _find_by_attr("npc_id", spec["npc_id"])
    created = False
    if not npc:
        npc = create_object(
            "typeclasses.npcs.NPC",
            key=spec["key"],
            aliases=spec.get("aliases") or [],
            location=_find_room(spec["room_id"]),
            tags=[(ENTITY_TAG, ENTITY_CATEGORY)],
        )
        created = True
    npc.key = spec["key"]
    npc.location = _find_room(spec["room_id"])
    npc.db.npc_id = spec["npc_id"]
    npc.db.desc = spec.get("desc") or ""
    npc.db.dialogue_greeting = spec.get("greeting") or ""
    npc.db.job = dict(spec.get("job") or {})
    npc.db.knowledge = dict(spec.get("knowledge") or {})
    npc.db.canon_status = "vertical_slice"
    npc.db.campaign_id = CAMPAIGN_ID
    npc.db.simulation_enabled = False
    npc.db.decision_enabled = False
    if spec.get("combat") is not None:
        npc.db.combat_profile = dict(spec.get("combat") or {})
    _ensure_aliases(npc, spec.get("aliases") or [])
    if spec.get("fact"):
        upsert_knowledge_fact(npc, spec["fact"])
    return npc, created


def _ensure_world_object(location, object_id, key, aliases, desc, action):
    obj = _find_by_attr("object_id", object_id)
    created = False
    if not obj:
        obj = create_object(
            "typeclasses.siza_objects.WorldObject",
            key=key,
            aliases=aliases,
            location=location,
            tags=[(ENTITY_TAG, ENTITY_CATEGORY)],
        )
        created = True
    obj.key = key
    obj.location = location
    obj.db.object_id = object_id
    obj.db.desc = desc
    obj.db.portable = False
    obj.db.hidden = False
    obj.db.canon_status = "vertical_slice"
    obj.db.campaign_id = CAMPAIGN_ID
    state = _plain_dict(getattr(obj.db, "state", {}))
    state.setdefault("completed", False)
    obj.db.state = state
    obj.db.object_actions = _upsert_by_id(getattr(obj.db, "object_actions", []), action)
    _ensure_aliases(obj, aliases)
    return obj, created


def _install_tutorial_objects():
    kitchen = _find_room(KITCHEN_ROOM_ID)
    training = _find_room(TRAINING_ROOM_ID)
    gear_action = {
        "id": GEAR_ACTION_ID,
        "name": "reclamar el equipo de ingreso",
        "activity": "reclamar el equipo de ingreso",
        "input_phrases": [
            "reclamar el bulto", "reclamo el bulto", "recoger el equipo", "recojo el equipo",
            "abrir el bulto de ingreso", "tomar mi Mistcoat", "tomar mi ManaDriver",
        ],
        "enabled": True,
        "object_state_requirements": [{"field": "completed", "op": "EQ", "value": False, "name": "El bulto aún no fue reclamado"}],
        "metadata": {"campaign_id": CAMPAIGN_ID, "campaign_tags": ["DH-TUT-GEAR"], "contents": ["Mistcoat de servicio", "ManaDriver de servicio"]},
        "canon_status": "vertical_slice",
    }
    gear_obj, gear_created = _ensure_world_object(
        kitchen, GEAR_OBJECT_ID, "Bulto de ingreso de Nereida",
        ["bulto", "bulto de ingreso", "equipo de ingreso", "Mistcoat", "ManaDriver"],
        "Un paquete resistente lleva tu nombre escrito a mano. Dentro están el Mistcoat amarillo de servicio, un ManaDriver básico y correas de equipo.",
        gear_action,
    )

    training_action = {
        "id": TRAINING_ACTION_ID,
        "name": "golpear el blanco de práctica",
        "activity": "golpear el blanco de práctica",
        "input_phrases": [
            "golpear el blanco", "golpeo el blanco", "atacar el blanco", "practicar con el blanco",
            "hacer la prueba de Orlan", "intento la prueba de Orlan",
        ],
        "enabled": True,
        "metadata": {"campaign_id": CAMPAIGN_ID, "campaign_tags": ["DH-TUT-TRAINING"]},
        "check": {
            "id": "DH7-CHECK-TUT-TRAINING-001",
            "trigger": "OBSTACLE",
            "mode": "DIRECT",
            "stat": "COO",
            "difficulty": 5,
            "metadata": {"fiction": "Un blanco móvil de entrenamiento obliga a coordinar postura, timing y golpe."},
        },
        "canon_status": "vertical_slice",
    }
    training_obj, training_created = _ensure_world_object(
        training, TRAINING_OBJECT_ID, "Blanco móvil de Orlan",
        ["blanco", "blanco de práctica", "blanco movil", "prueba de Orlan"],
        "Un blanco mecánico gira sobre una base lastrada. Tiene marcas viejas de Spellblades y golpes convencionales; Orlan lo usa para separar pose de coordinación.",
        training_action,
    )

    upsert_consequence_rule({
        "id": GEAR_RULE_ID, "enabled": True, "canon_status": "vertical_slice",
        "when": {"action_type": "OBJECT_ACTION_COMPLETED", "object_action_id": GEAR_ACTION_ID, "outcome": "COMPLETED"},
        "state_effects": [
            {"scope": "ACTION_OBJECT", "namespace": "state", "field": "completed", "op": "SET", "value": True},
            {"scope": "ACTION_SITE", "namespace": "world_state", "field": "nereida_ingreso_equipo_reclamado", "op": "SET", "value": True},
        ],
    })
    upsert_consequence_rule({
        "id": TRAINING_RULE_ID, "enabled": True, "canon_status": "vertical_slice",
        "when": {"action_type": "OBJECT_ACTION_COMPLETED", "object_action_id": TRAINING_ACTION_ID},
        "state_effects": [
            {"scope": "ACTION_SITE", "namespace": "world_state", "field": "nereida_prueba_orlan_realizada", "op": "SET", "value": True},
        ],
    })
    return {
        "gear": {"dbref": int(gear_obj.id), "created": gear_created},
        "training": {"dbref": int(training_obj.id), "created": training_created},
    }


def install():
    rooms = {}
    room_created = 0
    for room_id, key, desc, room_type, zone_id in ROOMS:
        room, created = _ensure_room(room_id, key, desc, room_type, zone_id)
        rooms[room_id] = room
        room_created += int(created)

    exit_created = 0
    for source_id, dest_id, forward_key, return_key, base_id, forward_tags in CONNECTIONS:
        source = rooms[source_id]
        destination = rooms[dest_id]
        _, created_a = _ensure_exit(source, destination, forward_key, base_id + "A", forward_tags)
        _, created_b = _ensure_exit(destination, source, return_key, base_id + "B", [])
        exit_created += int(created_a) + int(created_b)

    npc_created = 0
    npc_rows = []
    for spec in NPCS:
        npc, created = _ensure_npc(spec)
        npc_created += int(created)
        npc_rows.append({"npc_id": spec["npc_id"], "key": npc.key, "dbref": int(npc.id), "created": created})

    tutorial = _install_tutorial_objects()

    courtyard = rooms[COURTYARD_ROOM_ID]
    courtyard.db.campaign_presence = ["NPC-DH7-SQUEEK"]
    entry = rooms[ENTRY_ROOM_ID]
    entry.db.campaign_presence = ["NPC-DH7-DINO"]

    return {
        "status": "INSTALLED",
        "campaign_id": CAMPAIGN_ID,
        "entry_room_id": ENTRY_ROOM_ID,
        "entry_room_dbref": int(entry.id),
        "rooms": len(rooms),
        "rooms_created": room_created,
        "exits_created": exit_created,
        "npcs": len(npc_rows),
        "npcs_created": npc_created,
        "tutorial_objects": tutorial,
    }
