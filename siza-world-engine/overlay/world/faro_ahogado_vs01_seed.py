from evennia import create_object, search_object, search_tag

from services.consequence_engine import upsert_consequence_rule
from services.knowledge_fact_engine import upsert_knowledge_fact


SEED_TAG = "faro_ahogado_vs01"
SEED_CATEGORY = "siza_campaign_seed"
ENTITY_TAG = "faro_ahogado_vs01_entity"
ENTITY_CATEGORY = "siza_campaign_entity"
CAMPAIGN_ID = "CAMPAIGN-FARO-AHOGADO-VS01"

PLAZA_ROOM_ID = "CAR-KAL-DAR-003"
PATIO_ROOM_ID = "CAR-KAL-DAR-002"
MUELLES_ROOM_ID = "CAR-KAL-CITY-DAR-006"

MUTUAL_NPC_ID = "NPC-FA-VS01-MUTUAL-001"
BUZO_NPC_ID = "NPC-FA-VS01-BUZO-001"
ROUTE_EXIT_ID = "EXIT-FA-VS01-MUELLES-A"
RETURN_EXIT_ID = "EXIT-FA-VS01-MUELLES-B"

FORMAL_OBJECT_ID = "OBJ-FA-VS01-ASIGNACION-001"
FORMAL_ACTION_ID = "ACT-FA-VS01-MEANS-FORMAL-001"
FORMAL_RULE_ID = "RULE-FA-VS01-MEANS-FORMAL-001"
RELEVO_OBJECT_ID = "OBJ-FA-VS01-RELEVO-001"
RELEVO_ACTION_ID = "ACT-FA-VS01-MEANS-RELEVO-001"
RELEVO_RULE_ID = "RULE-FA-VS01-MEANS-RELEVO-001"
MEANS_SELECTED_FIELD = "faro_means_selected"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _upsert_by_id(rows, replacement):
    output = []
    replaced = False
    wanted = str(replacement.get("id") or "")
    for raw in _plain_list(rows):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == wanted:
            output.append(dict(replacement))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(replacement))
    return output


def _find_room(room_id):
    for obj in search_tag(SEED_TAG, category=SEED_CATEGORY):
        if str(getattr(obj.db, "room_id", "") or "") == room_id:
            return obj
    for key in ("Plaza de Recepcion", "Patio de Mineral", "Muelles de Descenso"):
        for obj in search_object(key):
            if str(getattr(obj.db, "room_id", "") or "") == room_id:
                return obj
    return None


def _find_entity(attr_name, attr_value):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, attr_name, "") or "") == str(attr_value):
            return obj
    return None


def _find_exit(exit_id):
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "exit_id", "") or "") == exit_id:
            return obj
    return None


def _ensure_aliases(obj, aliases):
    if not obj:
        return
    for alias in aliases:
        try:
            obj.aliases.add(alias)
        except Exception:
            pass


def _ensure_muelles():
    room = _find_room(MUELLES_ROOM_ID)
    created = False
    if not room:
        room = create_object(
            "typeclasses.rooms.Room",
            key="Muelles de Descenso",
            tags=[(SEED_TAG, SEED_CATEGORY)],
        )
        created = True
    room.key = "Muelles de Descenso"
    room.db.room_id = MUELLES_ROOM_ID
    room.db.zone_id = "CAR-KAL-DARSENAS-CAMPANA"
    room.db.region_id = "CAR-KALNAJ"
    room.db.settlement_id = "CAR-KAL-KALNAJ"
    room.db.district_id = "CAR-KAL-DARSENAS-CAMPANA"
    room.db.desc = (
        "Un conjunto de plataformas de trabajo desciende hacia las campanas, armaduras y equipos "
        "que operan bajo el nivel de las Dársenas de Campana. Aquí se preparan los turnos y las expediciones de profundidad. "
        "Una mesa de asignaciones de la Mutual organiza los turnos formales; cerca de ella, una lista de relevo recoge vacantes de cuadrillas incompletas."
    )
    room.db.sensory_facts = {
        "sight": [
            "campanas de descenso",
            "armaduras de profundidad",
            "equipos preparando turnos",
            "mesa de asignaciones de la Mutual",
            "lista de relevo de cuadrilla",
        ],
        "hearing": ["cadenas tensándose", "órdenes de cuadrilla", "agua golpeando bajo las plataformas"],
        "smell": ["metal húmedo", "aceite de maquinaria", "sal"],
    }
    room.db.space_profile = {
        "room_type": "muelle industrial de profundidad",
        "scale": "mediana",
        "geometry": "plataformas escalonadas alrededor de mecanismos de descenso",
        "orientation": "el acceso superior comunica con el Patio de Mineral",
        "focal_points": ["campanas de descenso", "zona de armaduras", "mesa de turnos"],
        "status": "vertical_slice",
    }
    room.db.canon_status = "prototype"
    room.db.campaign_id = CAMPAIGN_ID
    if getattr(room.db, "world_state", None) is None:
        room.db.world_state = {}
    return room, created


def _ensure_exit(source, destination, *, key, aliases, exit_id, campaign_tags):
    exit_obj = _find_exit(exit_id)
    created = False
    if not exit_obj:
        exit_obj = create_object(
            "typeclasses.exits.Exit",
            key=key,
            aliases=aliases,
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
    exit_obj.db.canon_status = "prototype"
    exit_obj.db.campaign_id = CAMPAIGN_ID
    exit_obj.db.campaign_tags = list(campaign_tags or [])
    _ensure_aliases(exit_obj, aliases)
    return exit_obj, created


def _mutual_fact():
    return {
        "id": "FA-FACT-LEAD-MUTUAL-ROUTE-001",
        "topic": "Faro Ahogado",
        "aliases": [
            "faro",
            "faro ahogado",
            "expedicion",
            "expedición",
            "salida",
            "ruta",
            "campana",
            "campanas",
            "muelles",
            "muelles de descenso",
        ],
        "knowledge_key": "FA_EXPEDICION",
        "required_level": 1,
        "campaign_tags": ["FA-BEAT-LEAD"],
        "canon_status": "vertical_slice",
        "text": (
            "Las expediciones de profundidad salen por los Muelles de Descenso. El acceso operativo está en el Patio de Mineral, "
            "y la Mutual Campana Honda controla la asignación formal de campanas y turnos."
        ),
        "response": (
            "La oficial baja la voz. «Si buscas Faro Ahogado, no sale nada desde el embarcadero de superficie. "
            "Las expediciones de profundidad se preparan en los Muelles de Descenso. El paso está en el Patio de Mineral. "
            "La Mutual asigna las campanas y los turnos; para bajar con una expedición tendrás que entrar en una de esas listas.»"
        ),
    }


def _buzo_fact():
    return {
        "id": "FA-FACT-LEAD-BUZO-ROUTE-001",
        "topic": "Faro Ahogado",
        "aliases": [
            "faro",
            "faro ahogado",
            "expedicion",
            "expedición",
            "ruta",
            "bajar",
            "descenso",
            "cuadrilla",
            "muelles",
            "muelles de descenso",
        ],
        "knowledge_key": "FA_EXPEDICION",
        "required_level": 1,
        "campaign_tags": ["FA-BEAT-LEAD"],
        "canon_status": "vertical_slice",
        "text": (
            "Los equipos que salen hacia zonas de profundidad usan los Muelles de Descenso, accesibles desde el Patio de Mineral. "
            "Además del registro formal de la Mutual, una cuadrilla incompleta puede incorporar a alguien antes de bajar."
        ),
        "response": (
            "El buzo mira hacia el Patio de Mineral. «Faro Ahogado es trabajo de profundidad. Baja a los Muelles de Descenso desde el patio. "
            "La Mutual lleva las listas, sí, pero cuando una cuadrilla pierde una mano antes del descenso busca reemplazo allí mismo. "
            "No es la vía limpia, pero es una vía.»"
        ),
    }


def _ensure_npc(location, *, npc_id, key, aliases, desc, job, greeting, fact):
    npc = _find_entity("npc_id", npc_id)
    created = False
    if not npc:
        npc = create_object(
            "typeclasses.npcs.NPC",
            key=key,
            aliases=aliases,
            location=location,
            tags=[(ENTITY_TAG, ENTITY_CATEGORY)],
        )
        created = True
    npc.key = key
    npc.location = location
    npc.db.npc_id = npc_id
    npc.db.desc = desc
    npc.db.canon_status = "vertical_slice"
    npc.db.campaign_id = CAMPAIGN_ID
    npc.db.job = dict(job)
    knowledge = dict(getattr(npc.db, "knowledge", {}) or {})
    knowledge["FA_EXPEDICION"] = max(2, int(knowledge.get("FA_EXPEDICION", 0) or 0))
    npc.db.knowledge = knowledge
    npc.db.dialogue_greeting = greeting
    if getattr(npc.db, "memories", None) is None:
        npc.db.memories = []
    if getattr(npc.db, "relationships", None) is None:
        npc.db.relationships = {}
    npc.db.simulation_enabled = False
    _ensure_aliases(npc, aliases)
    upsert_knowledge_fact(npc, fact)
    return npc, created


def _means_action(action_id, name, input_phrases, means_path):
    return {
        "id": action_id,
        "name": name,
        "activity": name,
        "input_phrases": list(input_phrases),
        "enabled": True,
        "knowledge_requirements": [
            {
                "knowledge_key": "FA_EXPEDICION",
                "min_level": 1,
                "name": "Conocimiento sobre la expedición de Faro Ahogado",
            }
        ],
        "state_requirements": [
            {
                "field": MEANS_SELECTED_FIELD,
                "op": "NOT_EXISTS",
                "value": None,
                "name": "Aún no se ha elegido un medio de descenso",
            }
        ],
        "object_state_requirements": [
            {
                "field": "claimed",
                "op": "EQ",
                "value": False,
                "name": "Esta opción todavía está disponible",
            }
        ],
        "metadata": {
            "campaign_id": CAMPAIGN_ID,
            "campaign_tags": ["FA-BEAT-MEANS"],
            "means_path": means_path,
        },
        "canon_status": "vertical_slice",
    }


def _ensure_means_object(location, *, object_id, key, aliases, desc, action):
    obj = _find_entity("object_id", object_id)
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
    state.setdefault("claimed", False)
    obj.db.state = state
    obj.db.object_actions = _upsert_by_id(getattr(obj.db, "object_actions", []), action)
    _ensure_aliases(obj, aliases)
    return obj, created


def _install_means_rules():
    upsert_consequence_rule(
        {
            "id": FORMAL_RULE_ID,
            "enabled": True,
            "canon_status": "vertical_slice",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": FORMAL_ACTION_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": "claimed",
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": MEANS_SELECTED_FIELD,
                    "op": "SET",
                    "value": "FORMAL",
                },
            ],
        }
    )
    upsert_consequence_rule(
        {
            "id": RELEVO_RULE_ID,
            "enabled": True,
            "canon_status": "vertical_slice",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": RELEVO_ACTION_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": "claimed",
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": MEANS_SELECTED_FIELD,
                    "op": "SET",
                    "value": "RELEVO",
                },
            ],
        }
    )


def install():
    plaza = _find_room(PLAZA_ROOM_ID)
    patio = _find_room(PATIO_ROOM_ID)
    if not plaza or not patio:
        missing = []
        if not plaza:
            missing.append(PLAZA_ROOM_ID)
        if not patio:
            missing.append(PATIO_ROOM_ID)
        return {
            "status": "MISSING_BASE_ROOMS",
            "missing": missing,
            "campaign_id": CAMPAIGN_ID,
        }

    muelles, muelles_created = _ensure_muelles()
    route_exit, route_created = _ensure_exit(
        patio,
        muelles,
        key="bajar a los Muelles de Descenso",
        aliases=["muelles de descenso", "bajar a los muelles", "ir a los muelles de descenso", "voy a los muelles de descenso"],
        exit_id=ROUTE_EXIT_ID,
        campaign_tags=["FA-BEAT-ROUTE"],
    )
    return_exit, return_created = _ensure_exit(
        muelles,
        patio,
        key="volver al Patio de Mineral",
        aliases=["patio de mineral", "volver al patio", "subir al patio"],
        exit_id=RETURN_EXIT_ID,
        campaign_tags=[],
    )

    mutual, mutual_created = _ensure_npc(
        plaza,
        npc_id=MUTUAL_NPC_ID,
        key="Oficial de Mutual Campana Honda",
        aliases=["oficial", "mutual", "oficial de la mutual", "campana honda"],
        desc=(
            "Una oficial de la Mutual Campana Honda revisa listas de regreso y de ingreso mientras responde preguntas de trabajadores y familias."
        ),
        job={"id": "JOB-FA-VS01-MUTUAL-TURNOS", "name": "enlace de turnos de Mutual Campana Honda", "status": "vertical_slice"},
        greeting="La oficial aparta la vista de las listas y te presta atención.",
        fact=_mutual_fact(),
    )
    buzo, buzo_created = _ensure_npc(
        plaza,
        npc_id=BUZO_NPC_ID,
        key="Buzo de relevo",
        aliases=["buzo", "relevo", "buzo de relevo", "trabajador de profundidad"],
        desc=(
            "Un buzo de relevo espera junto a un arnés húmedo y una bolsa de herramientas, pendiente de las noticias de los turnos de profundidad."
        ),
        job={"id": "JOB-FA-VS01-BUZO-RELEVO", "name": "buzo de relevo de profundidad", "status": "vertical_slice"},
        greeting="El buzo deja de revisar su arnés y espera tu pregunta.",
        fact=_buzo_fact(),
    )

    formal_action = _means_action(
        FORMAL_ACTION_ID,
        "Registrarse para un turno de descenso",
        [
            "registrarme para un turno de descenso",
            "solicitar un turno de descenso",
            "anotarme en la lista de campanas",
            "conseguir una asignación formal",
            "me registro en la mesa de asignaciones",
        ],
        "FORMAL",
    )
    formal_obj, formal_created = _ensure_means_object(
        muelles,
        object_id=FORMAL_OBJECT_ID,
        key="Mesa de asignaciones de la Mutual",
        aliases=["mesa de asignaciones", "registro de turnos", "lista de campanas", "mesa de turnos"],
        desc=(
            "Una mesa de la Mutual Campana Honda organiza nombres, campanas y turnos de descenso. "
            "Quien ya conoce el procedimiento puede solicitar aquí una asignación formal."
        ),
        action=formal_action,
    )

    relevo_action = _means_action(
        RELEVO_ACTION_ID,
        "Tomar una plaza de relevo",
        [
            "anotarme como relevo",
            "tomar una plaza de relevo",
            "unirme a una cuadrilla incompleta",
            "cubrir el puesto de relevo",
            "me anoto en la lista de relevo",
        ],
        "RELEVO",
    )
    relevo_obj, relevo_created = _ensure_means_object(
        muelles,
        object_id=RELEVO_OBJECT_ID,
        key="Lista de relevo de cuadrilla",
        aliases=["lista de relevo", "lista de cuadrilla", "cuadrilla incompleta", "puesto de relevo"],
        desc=(
            "Una tablilla reúne vacantes de última hora en cuadrillas de profundidad. "
            "Cubrir una de esas plazas permite bajar sin esperar una asignación ordinaria."
        ),
        action=relevo_action,
    )

    _install_means_rules()
    plaza.db.campaign_presence = [MUTUAL_NPC_ID, BUZO_NPC_ID]

    return {
        "status": "INSTALLED",
        "campaign_id": CAMPAIGN_ID,
        "lead_sources": [
            {"npc": mutual.key, "dbref": int(mutual.id), "created": mutual_created, "fact_id": "FA-FACT-LEAD-MUTUAL-ROUTE-001"},
            {"npc": buzo.key, "dbref": int(buzo.id), "created": buzo_created, "fact_id": "FA-FACT-LEAD-BUZO-ROUTE-001"},
        ],
        "route": {
            "room": muelles.key,
            "room_dbref": int(muelles.id),
            "room_created": muelles_created,
            "exit": route_exit.key,
            "exit_dbref": int(route_exit.id),
            "exit_created": route_created,
            "return_exit": return_exit.key,
            "return_exit_dbref": int(return_exit.id),
            "return_created": return_created,
        },
        "means": [
            {
                "path": "FORMAL",
                "object": formal_obj.key,
                "object_dbref": int(formal_obj.id),
                "object_created": formal_created,
                "action_id": FORMAL_ACTION_ID,
                "rule_id": FORMAL_RULE_ID,
            },
            {
                "path": "RELEVO",
                "object": relevo_obj.key,
                "object_dbref": int(relevo_obj.id),
                "object_created": relevo_created,
                "action_id": RELEVO_ACTION_ID,
                "rule_id": RELEVO_RULE_ID,
            },
        ],
    }


if __name__ == "__main__":
    print(install())
