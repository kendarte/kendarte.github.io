"""Content-only depth pass for the 25 Darkhaven rooms.

This patch writes narrative room content and DM-facing room data into existing
Darkhaven rooms. It is idempotent and only creates/updates static scene props
for room-local interaction anchors. It never deletes rooms, exits, characters,
player state, inventory, or campaign progress.
"""

from evennia import create_object
from evennia.objects.models import ObjectDB


BUILD = "0.1.0-darkhaven-room-content-depth"

ROOMS = [
    ("DH7-ROOM-001", "Puerta de Darkhaven", "Acceso fortificado principal. Dos portones de hierro encierran el paso de piedra, con garita y tablero de ingreso. Hay tránsito constante de guardias y estudiantes, olor a sal y piedra húmeda. Conserva visualmente partes de la antigua prisión.", ["Portones de hierro", "Garita de ingreso", "Tablero de registro", "Estandartes de Darkhaven", "Cadena de cierre"]),
    ("DH7-ROOM-002", "Patio Central de la Antigua Prisión", "Gran patio rectangular rodeado por las antiguas alas de celdas. Es el núcleo de distribución de Darkhaven. Tiene rutas pintadas, bancas de piedra y tablones de anuncios; estudiantes cruzan, descansan y entrenan aquí.", ["Rutas pintadas", "Bancas de piedra", "Tablón de anuncios", "Marcas de entrenamiento", "Campana de patio"]),
    ("DH7-ROOM-003", "Sala de Guardia", "Sala operativa junto al patio. Tiene mostrador, casilleros, pared de llaves, listas de turno y radios. Controla accesos y circulación y sirve para cambios de guardia y revisión de equipo.", ["Mostrador de guardia", "Pared de llaves", "Listas de turno", "Casilleros metálicos", "Radio de patrulla"]),
    ("DH7-ROOM-004", "Mando Regional de Sector 7", "Centro de mando administrativo. Mesas con mapas provinciales, comunicados, fichas de incidentes, archivadores y una pizarra de cambios. La información operacional se actualiza constantemente.", ["Mapas provinciales", "Pizarra de cambios", "Fichas de incidentes", "Archivadores operativos", "Mesa central"]),
    ("DH7-ROOM-005", "Sala de Comunicaciones", "Sala técnica adyacente al Mando Regional. Contiene racks de radio, auriculares, lámparas de señal y una mesa de coordinación. Recibe mensajes procedentes de puestos y faros.", ["Racks de radio", "Auriculares de operador", "Lámparas de señal", "Mesa de coordinación", "Registro de mensajes"]),
    ("DH7-ROOM-006", "Dirección de Orphim Trimago", "Despacho construido sobre una antigua oficina de mando de la prisión. Tiene escritorio, vitrinas de objetos recuperados, plantas, biblioteca y ventanales hacia el patio. Aquí se concentran documentos de admisión y material de dirección.", ["Escritorio de dirección", "Vitrinas de objetos recuperados", "Biblioteca privada", "Plantas de sombra", "Ventanales al patio"]),
    ("DH7-ROOM-007", "Archivos de Sector 7", "Gran archivo institucional formado por dependencias carcelarias reconvertidas. Estanterías altas crean corredores estrechos llenos de cajas y expedientes; también hay gabinetes sellados y una mesa de consulta.", ["Estanterías altas", "Cajas de expedientes", "Gabinetes sellados", "Mesa de consulta", "Escalera de archivo"]),
    ("DH7-ROOM-008", "Aulas de Darkhaven", "Conjunto de aulas conectadas mediante una galería. Pizarras gastadas, bancos móviles y paneles de práctica ocupan las salas. Hay apuntes, protecciones de entrenamiento y rastros de ejercicios recientes.", ["Pizarras gastadas", "Bancos móviles", "Paneles de práctica", "Protecciones de entrenamiento", "Apuntes clavados"]),
    ("DH7-ROOM-009", "Sala de Briefing de Fireteams", "Espacio operativo entre las aulas y las zonas de despliegue. Una mesa larga sostiene un plano modular; las paredes contienen mapas, fotografías de campo y tablillas de evaluación. Aquí se preparan equipos y misiones.", ["Mesa de briefing", "Plano modular", "Fotografías de campo", "Tablillas de evaluación", "Mapas de misión"]),
    ("DH7-ROOM-010", "Patio de Entrenamiento y Esgrima", "Patio amurallado dedicado al entrenamiento. Arena compacta, placas de impacto, líneas de práctica, armeros y postes de esgrima dividen el espacio. Está preparado para combates, ejercicios y pruebas.", ["Arena compacta", "Placas de impacto", "Líneas de práctica", "Armeros", "Postes de esgrima"]),
    ("DH7-ROOM-011", "Dormitorios del Fireteam 7", "Cuatro antiguas celdas convertidas en habitaciones alrededor de una pequeña sala común. Hay camas, casilleros y una mesa cubierta de piezas, notas y tazas. Es un espacio claramente habitado por el equipo.", ["Camas del fireteam", "Casilleros personales", "Mesa común", "Notas sueltas", "Tazas usadas"]),
    ("DH7-ROOM-012", "Dormitorios Generales", "Bloque residencial formado por una larga galería de antiguas celdas. Puertas de habitaciones, ropa tendida, libros y tablones personales hacen visible la vida cotidiana de los estudiantes.", ["Puertas de habitaciones", "Ropa tendida", "Tablones personales", "Libros prestados", "Bancos de pasillo"]),
    ("DH7-ROOM-013", "Comedor de Darkhaven", "Gran comedor institucional con mesas largas de madera, bandejas metálicas, avisos y ventanas altas. Se oyen conversaciones, cubiertos y discusiones sobre misiones; desde la cocina llega la comida de Berta.", ["Mesas largas", "Bandejas metálicas", "Avisos del comedor", "Ventanas altas", "Barra de servicio"]),
    ("DH7-ROOM-014", "Cocina y Taller de Berta", "Una mezcla deliberada de cocina y taller. Fogones, ollas y mesa de corte comparten espacio con herramientas, soldadura, madera y un banco de reparación. Huele a comida, metal caliente y trabajo.", ["Fogones", "Ollas pesadas", "Mesa de corte", "Banco de reparación", "Herramientas de Berta"]),
    ("DH7-ROOM-015", "Laboratorio de Artefactos y Reliquias", "Laboratorio esotécnico reforzado. Mesas de trabajo, vitrinas selladas, bandejas de material clasificado, lentes, pinzas y diagramas rodean reliquias en proceso de estudio.", ["Mesas de trabajo", "Vitrinas selladas", "Bandejas clasificadas", "Lentes de aumento", "Diagramas de reliquias"]),
    ("DH7-ROOM-016", "Atelier de Relena Dao", "Taller-laboratorio dedicado al diseño y prueba de Fashion Frames y uniformes. Está lleno de maniquíes, bastidores, telas tratadas, moldes, patrones, diagramas y herramientas finas.", ["Maniquíes", "Bastidores de tela", "Telas tratadas", "Patrones técnicos", "Herramientas finas"]),
    ("DH7-ROOM-017", "Taller FrameSmith de Maine", "Gran taller industrial. Tiene puente grúa, bancos reforzados, cables, núcleos abiertos, manacores y herramientas de precisión. Aquí se reparan y calibran Frames, Spellblades y maquinaria pesada.", ["Puente grúa", "Bancos reforzados", "Núcleos abiertos", "Manacores", "Herramientas de precisión"]),
    ("DH7-ROOM-018", "Bahía de Equipos Pesados y Deep Dive Frames", "Nave de carga adaptada donde los Deep Dive Frames descansan sobre soportes de mantenimiento. Mangueras, líneas de diagnóstico y contenedores ocupan la bahía mientras se realizan pruebas mecánicas.", ["Deep Dive Frames", "Soportes de mantenimiento", "Mangueras de diagnóstico", "Contenedores estancos", "Líneas de carga"]),
    ("DH7-ROOM-019", "Depósito de Equipo Darkhaven", "Gran almacén reforzado con estanterías numeradas hasta el techo. Contiene cajas, respiradores, detectores, barreras y herramientas de respuesta. Los préstamos y devoluciones se controlan desde una mesa central.", ["Estanterías numeradas", "Cajas de equipo", "Respiradores", "Detectores", "Mesa de préstamo"]),
    ("DH7-ROOM-020", "Enfermería de Respuesta", "Sala clínica preparada para emergencias. Camillas, biombos, carros médicos, monitores, mantas y suministros separados por colores permiten evaluación y tratamiento rápido.", ["Camillas", "Biombos", "Carros médicos", "Monitores", "Suministros por color"]),
    ("DH7-ROOM-021", "Aislamiento de Exposición", "Sector médico reforzado entre Enfermería y Contención. Una antesala con lavamanos y armarios de protección conduce a cámaras selladas con mirillas, juntas gruesas y luces de estado.", ["Lavamanos de descontaminación", "Armarios de protección", "Cámaras selladas", "Mirillas gruesas", "Luces de estado"]),
    ("DH7-ROOM-022", "Contención Compleja", "Bloque restringido construido sobre la infraestructura carcelaria. Un corredor de seguridad conecta puertas reforzadas, paneles de lectura, anclajes de contención y vitrinas especiales de transporte.", ["Puertas reforzadas", "Paneles de lectura", "Anclajes de contención", "Vitrinas de transporte", "Corredor de seguridad"]),
    ("DH7-ROOM-023", "Sala de Observación de Anomalías", "Galería protegida situada sobre Contención. Un gran vidrio permite observar el bloque desde asientos escalonados; hay monitores y cuadernos donde se registran pequeños cambios de las anomalías.", ["Vidrio de observación", "Asientos escalonados", "Monitores", "Cuadernos de registro", "Panel de anotaciones"]),
    ("DH7-ROOM-024", "Torre de Vigilancia", "Torre vertical de piedra que domina el patio, los tejados, los muros y el mar. El puesto superior contiene prismáticos, mesa de guardia y marcas de distancia. Se oyen viento y campanas de señal.", ["Prismáticos", "Mesa de guardia", "Marcas de distancia", "Ventanas estrechas", "Campana de señal"]),
    ("DH7-ROOM-025", "Muelle de Despliegue", "Salida marítima de Darkhaven. Una rampa de concreto baja hacia el agua entre amarres, cajas estancas y el muelle de servicio. Cabrestantes, chalecos y equipo de viaje esperan preparados para operaciones.", ["Rampa de concreto", "Amarres", "Cajas estancas", "Cabrestantes", "Chalecos de despliegue"]),
]


def _clean(value):
    return str(value or "").strip()


def _slug(value):
    text = "".join(ch if ch.isalnum() else "-" for ch in _clean(value).upper())
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-") or "ITEM"


def _objects_by_attr(attr):
    found = {}
    for obj in ObjectDB.objects.all():
        value = getattr(obj.db, attr, None)
        if value:
            found[str(value)] = obj
    return found


def _set_db(obj, field, value):
    if getattr(obj.db, field, None) != value:
        setattr(obj.db, field, value)
        return True
    return False


def _state_key(room_id, suffix):
    return _clean(room_id).lower().replace("-", "_") + "_" + suffix


def _scene_entities(room_id, room_name, focal_points):
    entities = []
    for index, name in enumerate(list(focal_points or [])[:5], start=1):
        object_id = f"{room_id}-SCENE-{index:02d}"
        lower = name.lower()
        entities.append({
            "id": object_id,
            "object_id": object_id,
            "name": name,
            "aliases": [lower],
            "visible_description": f"{name} ayuda a leer la función, tensión o historia visible de {room_name}.",
            "interaction_facts": [{
                "topic": f"detalle de {room_name}",
                "text": f"{name} revela cómo se usa este cuarto y qué presión organiza la escena.",
            }],
            "object_actions": [{
                "id": f"ACT-{_slug(object_id)}-EXAMINAR",
                "name": f"Examinar {name}",
                "input_phrases": [f"examinar {lower}", f"revisar {lower}", f"observar {lower}", f"mirar {lower}"],
                "completion_text": f"Revisas {lower} y entiendes mejor cómo funciona este lugar.",
                "narrative": f"Te acercas a {lower}. El detalle aclara el uso del cuarto sin convertir la escena en una lista.",
            }],
            "canon_status": "vertical_slice",
        })
    return entities


def _payload(room_id, room_name, desc, focal_points):
    return {
        "desc": desc,
        "canon_status": "vertical_slice",
        "sensory_facts": {
            "sight": list(focal_points or []),
            "hearing": ["actividad del cuarto", "pasos cercanos", "ruido institucional de Darkhaven"],
            "smell": ["piedra húmeda", "metal usado", "aire de costa"],
            "light": "luz funcional según el uso del cuarto",
            "temperature": "humedad fría de la antigua prisión reconvertida",
            "atmosphere": "espacio institucional activo con memoria carcelaria debajo",
        },
        "space_profile": {
            "room_type": room_name,
            "function": "escena jugable de Darkhaven Zona 7",
            "focal_points": list(focal_points or []),
            "movement_logic": "La descripción principal es sólo narrativa. Personas, objetos y salidas van por botones/capas separadas.",
        },
        "perception_facts": [
            {"id": f"{room_id}-PER-001", "stat": "PER", "difficulty": 6, "label": "Leer detalles visibles", "success_text": f"Detectas qué elementos de {room_name} reciben más uso, control o desgaste.", "failure_text": "Percibes la escena general, pero no separas los detalles importantes del ruido.", "unlock_state": _state_key(room_id, "per_leido")},
            {"id": f"{room_id}-INT-001", "stat": "INT", "difficulty": 7, "label": "Entender la función del cuarto", "success_text": f"Comprendes cómo {room_name} encaja en la operación diaria de Darkhaven.", "failure_text": "Reconoces objetos y tránsito, pero la lógica interna del lugar aún no queda clara.", "unlock_state": _state_key(room_id, "int_entendido")},
            {"id": f"{room_id}-PSI-001", "stat": "PSI", "difficulty": 8, "label": "Sentir la memoria del lugar", "success_text": "La antigua prisión se siente debajo de la academia como una segunda arquitectura.", "failure_text": "Sólo percibes humedad, vigilancia y la incomodidad normal de Darkhaven.", "unlock_state": _state_key(room_id, "psi_sentido")},
        ],
        "job_tasks": [
            f"examinar {focal_points[0].lower()}" if focal_points else f"observar {room_name}",
            f"revisar {focal_points[1].lower()}" if len(focal_points or []) > 1 else f"buscar detalles en {room_name}",
            f"escuchar {room_name}",
            f"buscar pistas en {room_name}",
            f"observar el flujo de {room_name}",
        ],
        "conditions": {
            "observation_rule": "room_description sólo narrativa; no Personas, A la vista, Ves, Salidas, Exits, Characters ni You see.",
            "free_action_rule": "Las acciones no visibles se resuelven por acción libre usando objetos, percepción y contexto del cuarto.",
        },
        "world_state": {
            _state_key(room_id, "visited"): False,
            _state_key(room_id, "per_leido"): False,
            _state_key(room_id, "int_entendido"): False,
            _state_key(room_id, "psi_sentido"): False,
        },
        "state_presentations": [
            {"state": "base", "text": desc},
            {"state": "per_success", "text": f"El patrón visible de {room_name} empieza a separarse del ruido general."},
            {"state": "int_success", "text": f"La función de {room_name} dentro de Darkhaven queda más clara."},
            {"state": "psi_success", "text": "La prisión antigua pesa debajo de la función actual del cuarto."},
        ],
        "dm_context": {
            "role": "Room State profundo para narrador, acciones libres y tiradas.",
            "use": ["desc", "sensory_facts", "space_profile", "perception_facts", "scene_manifest.entities", "job_tasks", "state_presentations"],
            "do_not": ["inventar salidas", "mezclar personas/objetos/salidas en room_description", "decir No entiendo si puede mapear la intención a percepción, objeto, NPC o movimiento"],
        },
        "scene_manifest": {"entities": _scene_entities(room_id, room_name, focal_points)},
    }


def _apply_room(room, payload):
    changed = []
    for field in ("desc", "canon_status", "sensory_facts", "space_profile", "perception_facts", "job_tasks", "conditions", "state_presentations", "dm_context", "scene_manifest"):
        if _set_db(room, field, payload[field]):
            changed.append(field)
    existing = getattr(room.db, "world_state", None)
    existing = dict(existing) if isinstance(existing, dict) else {}
    merged = dict(payload["world_state"])
    merged.update(existing)
    if _set_db(room, "world_state", merged):
        changed.append("world_state")
    return changed


def _apply_props(room, payload, props):
    created = updated = unchanged = 0
    conflicts = []
    for entity in payload["scene_manifest"]["entities"]:
        object_id = _clean(entity.get("object_id"))
        name = _clean(entity.get("name"))
        prop = props.get(object_id)
        if prop is not None and bool(getattr(prop.db, "is_npc", False)):
            conflicts.append({"object_id": object_id, "reason": "object_id pertenece a NPC"})
            continue
        if prop is not None and getattr(prop, "location", None) is not room:
            conflicts.append({"object_id": object_id, "reason": "prop existe en otro Room; se conserva"})
            continue
        was_created = prop is None
        if was_created:
            prop = create_object("typeclasses.siza_objects.WorldObject", key=name, location=room)
            prop.db.object_id = object_id
            props[object_id] = prop
            created += 1
        changed = []
        if prop.key != name:
            prop.key = name
            changed.append("key")
        desired = {
            "scene_entity_id": _clean(entity.get("id")) or object_id,
            "desc": _clean(entity.get("visible_description")),
            "portable": False,
            "hidden": False,
            "state": {},
            "interaction_facts": list(entity.get("interaction_facts") or []),
            "object_actions": list(entity.get("object_actions") or []),
            "state_visibility_requirements": [],
            "canon_status": "vertical_slice",
        }
        for field, value in desired.items():
            if getattr(prop.db, field, None) != value:
                setattr(prop.db, field, value)
                changed.append(field)
        try:
            aliases = sorted(alias for alias in entity.get("aliases") or [] if alias)
            current = sorted(str(value) for value in prop.aliases.all())
            if current != aliases:
                prop.aliases.clear()
                for alias in aliases:
                    prop.aliases.add(alias)
                changed.append("aliases")
        except Exception:
            pass
        if not was_created:
            if changed:
                updated += 1
            else:
                unchanged += 1
    return created, updated, unchanged, conflicts


def apply():
    rooms = _objects_by_attr("room_id")
    props = _objects_by_attr("object_id")
    report = {"status": "PATCHED", "build": BUILD, "rooms_source": len(ROOMS), "rooms_updated": 0, "rooms_unchanged": 0, "rooms_missing": [], "props_created": 0, "props_updated": 0, "props_unchanged": 0, "conflicts": []}
    for room_id, room_name, desc, focal_points in ROOMS:
        room = rooms.get(room_id)
        if not room:
            report["rooms_missing"].append(room_id)
            continue
        payload = _payload(room_id, room_name, desc, focal_points)
        changed = _apply_room(room, payload)
        if changed:
            report["rooms_updated"] += 1
        else:
            report["rooms_unchanged"] += 1
        created, updated, unchanged, conflicts = _apply_props(room, payload, props)
        report["props_created"] += created
        report["props_updated"] += updated
        report["props_unchanged"] += unchanged
        if conflicts:
            report["conflicts"].append({"room_id": room_id, "conflicts": conflicts})
    report["rooms_missing_count"] = len(report["rooms_missing"])
    report["conflicts_count"] = sum(len(item["conflicts"]) for item in report["conflicts"])
    return report
