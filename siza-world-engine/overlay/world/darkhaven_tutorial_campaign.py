DARKHAVEN_TUTORIAL_CAMPAIGN = {
    "id": "CAMPAIGN-DARKHAVEN-TUTORIAL-V01",
    "name": "Darkhaven — Ingreso",
    "canon_status": "vertical_slice",
    "campaign_note": (
        "Tutorial diegético del World Engine. El jugador no recibe una lista de controles: "
        "aprende los sistemas básicos respondiendo a situaciones reales de Darkhaven Zona 7."
    ),
    "objective": {
        "id": "DH-TUT-OBJECTIVE-ADMISSION",
        "text": "Completar el ingreso a Darkhaven y presentarse listo para incorporarse a un Fireteam.",
        "completion_authority": "WORLD_ENGINE_EVIDENCE",
    },
    "beats": [
        {
            "id": "DH-TUT-BEAT-ARRIVAL",
            "name": "Cruzar el portón",
            "state_goal": "El personaje entra a Darkhaven y alcanza el patio central siguiendo la recepción real del instituto.",
            "completion_authority": "WORLD_ENGINE_EVIDENCE",
            "completion_conditions": [
                {"source": "EVIDENCE", "path": "action_types", "op": "contains", "value": "MOVEMENT_EXECUTED"},
                {"source": "EVIDENCE", "path": "campaign_tags", "op": "contains", "value": "DH-TUT-ARRIVAL"},
            ],
        },
        {
            "id": "DH-TUT-BEAT-ORIENTATION",
            "name": "Encontrar dónde encajas",
            "state_goal": "El personaje obtiene de alguien de Darkhaven la información necesaria para continuar su ingreso.",
            "completion_authority": "WORLD_ENGINE_EVIDENCE",
            "completion_conditions": [
                {"source": "EVIDENCE", "path": "action_types", "op": "contains", "value": "KNOWLEDGE_FACT_SHARED"},
                {"source": "EVIDENCE", "path": "campaign_tags", "op": "contains", "value": "DH-TUT-ORIENTATION"},
            ],
        },
        {
            "id": "DH-TUT-BEAT-GEAR",
            "name": "Equipo de ingreso",
            "state_goal": "El personaje reclama el equipo básico que Darkhaven le asignó y aprende que los objetos del mundo tienen acciones y estado.",
            "completion_authority": "WORLD_ENGINE_EVIDENCE",
            "completion_conditions": [
                {"source": "EVIDENCE", "path": "action_types", "op": "contains", "value": "OBJECT_ACTION_EXECUTED"},
                {"source": "EVIDENCE", "path": "campaign_tags", "op": "contains", "value": "DH-TUT-GEAR"},
            ],
        },
        {
            "id": "DH-TUT-BEAT-TRAINING",
            "name": "Demostrar coordinación",
            "state_goal": "El personaje afronta una prueba física sencilla de Darkhaven y resuelve un check real del World Engine.",
            "completion_authority": "WORLD_ENGINE_EVIDENCE",
            "completion_conditions": [
                {"source": "EVIDENCE", "path": "action_types", "op": "contains", "value": "OBJECT_ACTION_EXECUTED"},
                {"source": "EVIDENCE", "path": "campaign_tags", "op": "contains", "value": "DH-TUT-TRAINING"},
            ],
        },
        {
            "id": "DH-TUT-BEAT-BRIEFING",
            "name": "Presentarse al Fireteam",
            "state_goal": "El personaje alcanza la sala de briefing después de completar su ingreso básico.",
            "completion_authority": "WORLD_ENGINE_EVIDENCE",
            "completion_conditions": [
                {"source": "EVIDENCE", "path": "action_types", "op": "contains", "value": "MOVEMENT_EXECUTED"},
                {"source": "EVIDENCE", "path": "campaign_tags", "op": "contains", "value": "DH-TUT-BRIEFING"},
            ],
        },
    ],
    "signal_projections": [],
    "deck": [
        {
            "id": "DH-TUT-CARD-ARRIVAL",
            "type": "BEAT",
            "name": "El portón se cierra detrás de ti",
            "enabled": True,
            "priority": 100,
            "active_beats": ["DH-TUT-BEAT-ARRIVAL"],
            "relevance_terms": ["entro", "patio", "porton", "portón", "darkhaven", "dino"],
            "world_queries": ["local_exits", "local_people", "visible_room_state"],
            "worldbook_topics": ["Darkhaven Zona 7 como antigua prisión convertida en instituto"],
            "director_intent": "GROUND_ARRIVAL_WITHOUT_EXPLAINING_CONTROLS",
        },
        {
            "id": "DH-TUT-CARD-ORIENTATION",
            "type": "OPPORTUNITY",
            "name": "Alguien sabe qué hacen con los recién llegados",
            "enabled": True,
            "priority": 95,
            "active_beats": ["DH-TUT-BEAT-ORIENTATION"],
            "requires_beats": ["DH-TUT-BEAT-ARRIVAL"],
            "relevance_terms": ["pregunto", "hablo", "donde", "dónde", "equipo", "ingreso", "berta", "squeek", "dino"],
            "world_queries": ["local_entities_with_relevant_knowledge", "active_local_facts", "local_route_objects_and_exits"],
            "worldbook_topics": ["vida cotidiana, ingreso y personal de Darkhaven"],
            "director_intent": "SURFACE_EXISTING_ORIENTATION_SOURCE",
        },
        {
            "id": "DH-TUT-CARD-GEAR",
            "type": "OPPORTUNITY",
            "name": "El bulto de ingreso está esperando",
            "enabled": True,
            "priority": 95,
            "active_beats": ["DH-TUT-BEAT-GEAR"],
            "requires_beats": ["DH-TUT-BEAT-ORIENTATION"],
            "relevance_terms": ["bulto", "equipo", "mistcoat", "manadriver", "reclamo", "recoger", "berta"],
            "world_queries": ["visible_local_objects", "available_object_actions", "local_exits"],
            "worldbook_topics": ["Mistcoat, ManaDriver y equipo básico de Darkhaven"],
            "director_intent": "POINT_TO_AUTHORED_GEAR_INTERACTION",
        },
        {
            "id": "DH-TUT-CARD-TRAINING",
            "type": "BEAT",
            "name": "Orlan no firma ingresos sin ver cómo te mueves",
            "enabled": True,
            "priority": 100,
            "active_beats": ["DH-TUT-BEAT-TRAINING"],
            "requires_beats": ["DH-TUT-BEAT-GEAR"],
            "relevance_terms": ["orlan", "entrenamiento", "golpeo", "blanco", "prueba", "practica", "práctica"],
            "world_queries": ["local_people", "visible_local_objects", "available_object_actions", "player_stats"],
            "worldbook_topics": ["Sir Orlan, entrenamiento y disciplina de Darkhaven"],
            "director_intent": "SURFACE_AUTHORED_TRAINING_CHECK",
        },
        {
            "id": "DH-TUT-CARD-BRIEFING",
            "type": "BEAT",
            "name": "El Fireteam espera",
            "enabled": True,
            "priority": 100,
            "active_beats": ["DH-TUT-BEAT-BRIEFING"],
            "requires_beats": ["DH-TUT-BEAT-TRAINING"],
            "relevance_terms": ["briefing", "fireteam", "equipo", "presentarme", "sala"],
            "world_queries": ["local_exits", "local_people", "active_campaign_state"],
            "worldbook_topics": ["Fireteam 7 y funcionamiento de las unidades de campo de Darkhaven"],
            "director_intent": "MOVE_PLAYER_INTO_NORMAL_PLAY",
        },
    ],
}

from services.dm_campaign_registry import register_campaign

register_campaign(DARKHAVEN_TUTORIAL_CAMPAIGN)
