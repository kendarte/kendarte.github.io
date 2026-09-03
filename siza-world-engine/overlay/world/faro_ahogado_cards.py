"""Executable authoring data for the Faro Ahogado vertical slice.

The card art is presentation.  This module is the deterministic contract used
by the World Engine: every printed choice has an explicit trigger, gate,
check, success/failure branch and persistent mutation plan.
"""

from copy import deepcopy


FARO_AHOGADO_CARD_BUILD = "faro-ahogado-cards-0.1"

ALLOWED_CARD_KINDS = {"CHOICE", "CREATURE", "CREATURE_EVENT", "EVENT", "LAND"}
ALLOWED_CHECK_MODES = {"DIRECT", "CONFRONT"}
ALLOWED_STATS = {"FUE", "AGI", "COO", "INT", "PER", "PSI", "DRIVER"}
ALLOWED_EFFECTS = {
    "ADD_LAND_TAG",
    "ADJUST_CAMPAIGN_VALUE",
    "ADJUST_ENTITY_STAT",
    "ADJUST_KARMA",
    "ADJUST_NEXT_CHECK_DIFFICULTY",
    "ADJUST_PLAYER_STAT",
    "BLOCK_ADVANCE",
    "BLOCK_RECOVERY",
    "CALL_CARD",
    "CANCEL_NEXT_STAT_LOSS",
    "COPY_TARGET_PROFILE",
    "GRANT_REWARD",
    "MARK_MILESTONE",
    "MOVE_ENTITY",
    "PREPARE_OMEN",
    "REMOVE_ENTITY",
    "REMOVE_LAND_TAG",
    "REMOVE_MARK",
    "REPLACE_ENTITY",
    "REQUIRE_TARGET_CHECK",
    "REVEAL_CARD",
    "SEARCH_AND_STAGE_LAND",
    "SET_CAMPAIGN_VALUE",
    "SET_ENTITY_STATE",
    "SET_ESCORT",
    "SET_TEMPORARY_MODIFIER",
    "SPAWN_ENTITY",
    "WIN_CAMPAIGN",
}

EXTERNAL_CONTENT_IDS = {
    "FA-CARD-CULTISTA-ANGULO-NEGRO",
    "FA-CARD-EVENTO-ANIMA",
    "FA-CARD-EVENTO-SANTO",
    "FA-CARD-FE-TORCIDA",
    "FA-CARD-GRITO-EN-LA-COSTA",
    "FA-CARD-LOS-FAROLES-SE-APAGAN",
    "FA-CARD-RITO-HILOS-NEGROS",
    "FA-CARD-ROSTRO-PRESTADO",
    "FA-CARD-TURBA-IRACUNDA",
}


def _effect(op, **payload):
    return {"op": op, "persistence": "WORLD", **payload}


def _check(stat, difficulty, *, printed_stat=None, mode="DIRECT", target_stat=None):
    value = {"mode": mode, "stat": stat, "difficulty": difficulty}
    if printed_stat:
        value["printed_stat"] = printed_stat
    if target_stat:
        value["target_stat"] = target_stat
    return value


def _rule(rule_id, trigger, *, label=None, requirements=None, check=None, success=None, failure=None):
    return {
        "id": rule_id,
        "trigger": trigger,
        "label": label,
        "requirements": list(requirements or []),
        "check": check,
        "on_success": list(success or []),
        "on_failure": list(failure or []),
    }


FARO_AHOGADO_CARDS = [
    {
        "id": "FA-CARD-ALDEANOS-PARANOICOS",
        "name": "Aldeanos Paranoicos",
        "kind": "CHOICE",
        "tags": ["PUEBLO", "SOCIAL"],
        "rules": [
            _rule("REVEAL", "ON_REVEAL", success=[
                _effect("SPAWN_ENTITY", entity_id="FA-TOKEN-ALDEANO", count=2, state="PASSIVE", destination="CURRENT_LAND")
            ]),
            _rule("HABLAR", "PLAYER_CHOICE", label="Hablar", check=_check("PSI", 8), success=[
                _effect("SET_ENTITY_STATE", target="SPAWNED_ALDEANOS", state="PASSIVE"),
                _effect("ADJUST_KARMA", amount=1),
            ], failure=[_effect("CALL_CARD", card_id="FA-CARD-TURBA-IRACUNDA")]),
            _rule("LEER_SITUACION", "PLAYER_CHOICE", label="Leer la situación", check=_check("PER", 8), success=[
                _effect("MOVE_ENTITY", target="ACTIVE_PLAYER", direction="BACK", distance=1, preserve_spawned_entities=True)
            ], failure=[_effect("SET_ENTITY_STATE", target="SPAWNED_ALDEANOS", state="HOSTILE")]),
            _rule("AMENAZAR", "PLAYER_CHOICE", label="Amenazar", check=_check("FUE", 7, printed_stat="POW"), success=[
                _effect("SET_ENTITY_STATE", target="SPAWNED_ALDEANOS", state="APARTED"),
                _effect("ADJUST_KARMA", amount=-1),
            ], failure=[_effect("CALL_CARD", card_id="FA-CARD-TURBA-IRACUNDA")]),
        ],
    },
    {
        "id": "FA-CARD-VISION-DEL-AGUA",
        "name": "Visión del Agua",
        "kind": "CHOICE",
        "tags": ["AGUA", "REVELACION"],
        "rules": [
            _rule("CONFESAR_MIEDO", "PLAYER_CHOICE", label="Confesar miedo", requirements=[
                {"kind": "CURRENT_LAND_HAS_ANY_TAG", "values": ["PLAZA_DEL_POZO", "AGUA"]}
            ], check=_check("PSI", 7), success=[_effect("ADJUST_PLAYER_STAT", stat="PSI", amount=1)], failure=[
                _effect("ADJUST_PLAYER_STAT", stat="PSI", amount=-1),
                _effect("REVEAL_CARD", source="PATH", count=1, visibility="ACTIVE_PLAYER_ONLY"),
            ]),
            _rule("BUSCAR_REFLEJO", "PLAYER_CHOICE", label="Buscar reflejo", requirements=[
                {"kind": "CURRENT_LAND_HAS_ANY_TAG", "values": ["PLAZA_DEL_POZO", "AGUA"]}
            ], check=_check("PER", 7), success=[
                _effect("REVEAL_CARD", source="ADVENTURE_DECK", count=2, visibility="ACTIVE_PLAYER_ONLY"),
                _effect("SEARCH_AND_STAGE_LAND", source="REVEALED_PAIR", placement="BOTTOM_OPTIONAL", count=1),
            ], failure=[_effect("CALL_CARD", card_id="FA-CARD-ROSTRO-EN-EL-VIDRIO")]),
            _rule("LAVAR_MARCA", "PLAYER_CHOICE", label="Lavar una marca", requirements=[
                {"kind": "CURRENT_LAND_HAS_ANY_TAG", "values": ["PLAZA_DEL_POZO", "AGUA"]},
                {"kind": "PLAYER_SELECTS_ONE", "values": ["REMOVE_VORSHA_MARK", "CANCEL_NEXT_PSI_PER_LOSS"]},
            ], success=[
                _effect("REMOVE_MARK", target="ACTIVE_PLAYER", mark="VORSHA_MINOR", conditional_choice="REMOVE_VORSHA_MARK"),
                _effect("CANCEL_NEXT_STAT_LOSS", target="ACTIVE_PLAYER", stats=["PSI", "PER"], conditional_choice="CANCEL_NEXT_PSI_PER_LOSS"),
                _effect("ADJUST_CAMPAIGN_VALUE", field="fog_level", amount=1),
            ]),
        ],
    },
    {
        "id": "FA-CARD-NINA-DE-LAS-FLORES-CREATURE",
        "name": "Niña de las Flores",
        "kind": "CREATURE",
        "tags": ["PUEBLO", "ALDEANO_ESPECIAL", "NO_HOSTIL"],
        "printed_stats": {"POW": 0, "DEF": 1, "PSI": 2, "PER": 2},
        "rules": [
            _rule("ESCORT_BONUS", "WHILE_ESCORTING", success=[
                _effect("SET_TEMPORARY_MODIFIER", target="ESCORTING_PLAYER", stat="PSI", amount=1, duration="WHILE_ESCORTING")
            ]),
            _rule("NEGATIVE_PSI_REPLACEMENT", "ENTITY_STAT_BECOMES_NEGATIVE", requirements=[
                {"kind": "SOURCE_CARD_IS_SELF"}, {"kind": "ENTITY_STAT_LT", "stat": "PSI", "value": 0}
            ], success=[
                _effect("CALL_CARD", card_id="FA-CARD-ROSTRO-PRESTADO"),
                _effect("REPLACE_ENTITY", target="SELF", replacement_card_id="FA-CARD-ALTERNO-ROSAS-MARCHITAS"),
                _effect("MARK_MILESTONE", value="REPLACEMENT_PROOF"),
            ]),
            _rule("SAFE_LAND_REWARD", "ENTITY_ENTERS_SAFE_LAND", success=[
                _effect("ADJUST_KARMA", amount=1),
                _effect("GRANT_REWARD", reward_type="MINOR_PRIZE", count=1),
            ]),
        ],
    },
    {
        "id": "FA-CARD-LA-NINA-DE-LAS-FLORES",
        "name": "La Niña de las Flores",
        "kind": "CHOICE",
        "tags": ["PUEBLO", "ALDEANO_ESPECIAL"],
        "rules": [
            _rule("REVEAL", "ON_REVEAL", success=[
                _effect("SPAWN_ENTITY", entity_id="FA-CARD-NINA-DE-LAS-FLORES-CREATURE", count=1, destination="CURRENT_LAND")
            ]),
            _rule("ESCOLTAR", "PLAYER_CHOICE", label="Escoltarla", success=[
                _effect("SET_ESCORT", entity_id="FA-CARD-NINA-DE-LAS-FLORES-CREATURE", player="ACTIVE_PLAYER"),
                _effect("SET_TEMPORARY_MODIFIER", target="ACTIVE_PLAYER", field="advance", amount=-1, duration="WHILE_ESCORTING"),
            ]),
            _rule("ESCONDER", "PLAYER_CHOICE", label="Esconderla", check=_check("PER", 7), success=[
                _effect("MOVE_ENTITY", target="FA-CARD-NINA-DE-LAS-FLORES-CREATURE", destination="CHOSEN_REVEALED_SAFE_LAND"),
                _effect("ADJUST_KARMA", amount=1),
            ], failure=[_effect("CALL_CARD", card_id="FA-CARD-LOS-FAROLES-SE-APAGAN")]),
            _rule("PREGUNTAR", "PLAYER_CHOICE", label="Preguntarle qué vio", check=_check("PSI", 7), success=[
                _effect("REVEAL_CARD", source="RESERVE", card_id="FA-CARD-ALTERNO-ROSAS-MARCHITAS", visibility="ACTIVE_PLAYER_ONLY"),
                _effect("PREPARE_OMEN", card_id="FA-CARD-ALTERNO-ROSAS-MARCHITAS"),
                _effect("MARK_MILESTONE", value="REPLACEMENT_SUSPICION"),
            ], failure=[
                _effect("ADJUST_ENTITY_STAT", target="FA-CARD-NINA-DE-LAS-FLORES-CREATURE", stat="PSI", amount=-1)
            ]),
        ],
    },
    {
        "id": "FA-CARD-PORTAVOZ-SEDA-NEGRA",
        "name": "Portavoz de la Seda Negra",
        "kind": "CREATURE_EVENT",
        "tags": ["CULTO", "SACERDOTE"],
        "printed_stats": {"POW": 1, "DEF": 3, "PSI": 5, "PER": 4},
        "rules": [
            _rule("ENTER", "ON_ENTER", success=[_effect("ADJUST_CAMPAIGN_VALUE", field="fog_level", amount=1)]),
            _rule("PUEBLO_DIFFICULTY", "WHILE_IN_PLAY", success=[
                _effect("ADJUST_NEXT_CHECK_DIFFICULTY", target_cards_with_tag="PUEBLO", amount=1, duration="WHILE_IN_PLAY")
            ]),
            _rule("CALL_PROCESSION", "CULTIST_COUNT_CHANGED", requirements=[
                {"kind": "ENTITY_COUNT_GTE", "tag": "CULTISTA", "value": 3}
            ], success=[_effect("CALL_CARD", card_id="FA-CARD-PROCESION-SIN-ROSTROS")]),
        ],
    },
    {
        "id": "FA-CARD-CAPILLA-HUNDIDA",
        "name": "Capilla Hundida",
        "kind": "LAND",
        "tags": ["PUEBLO", "SANTO", "AGUA", "CLOSED"],
        "rules": [
            _rule("BLOCK_CLOSED", "BEFORE_TRAVERSE", requirements=[{"kind": "SELF_HAS_TAG", "value": "CLOSED"}], success=[
                _effect("BLOCK_ADVANCE", reason="LAND_CLOSED", required_item="FA-ITEM-LLAVE-ADVENIDOS")
            ]),
            _rule("OPEN_WITH_KEY", "PLAYER_ACTION", label="Abrir con la Llave de los Advenidos", requirements=[
                {"kind": "PLAYER_HAS_ITEM", "item_id": "FA-ITEM-LLAVE-ADVENIDOS"}, {"kind": "SELF_HAS_TAG", "value": "CLOSED"}
            ], success=[
                _effect("REMOVE_LAND_TAG", target="SELF", tag="CLOSED"),
                _effect("CALL_CARD", card_id="FA-CARD-EVENTO-SANTO"),
                _effect("MARK_MILESTONE", value="CAPILLA_OPENED"),
            ]),
            _rule("CORRUPT_SANTO", "LAND_GAINS_TAG", requirements=[{"kind": "GAINED_TAG_IS", "value": "NIEBLA"}], success=[
                _effect("REMOVE_LAND_TAG", target="SELF", tag="SANTO"),
                _effect("CALL_CARD", card_id="FA-CARD-EVENTO-ANIMA"),
            ]),
        ],
    },
    {
        "id": "FA-CARD-ROSTRO-DE-NADIE",
        "name": "Rostro de Nadie",
        "kind": "CREATURE_EVENT",
        "tags": ["ALTERNO", "NIEBLA"],
        "printed_stats": {"POW": 1, "DEF": 1, "PSI": 3, "PER": 5},
        "rules": [
            _rule("ENTER_PER", "ON_ENTER", check=_check("PER", 8), failure=[_effect("BLOCK_ADVANCE", target="ACTIVE_PLAYER", duration="CURRENT_TURN")]),
            _rule("NARRATIVE_EVASION", "BEFORE_TARGETED", requirements=[{"kind": "CURRENT_LAND_HAS_TAG", "value": "NIEBLA"}], success=[
                _effect("REQUIRE_TARGET_CHECK", stat="PER", difficulty=7, failure="TARGETING_CANCELLED")
            ]),
        ],
    },
    {
        "id": "FA-CARD-ALTERNO-ROSAS-MARCHITAS",
        "name": "Alterno de las Rosas Marchitas",
        "kind": "CREATURE_EVENT",
        "tags": ["ALTERNO", "NIEBLA", "FLOR"],
        "printed_stats": {"POW": 2, "DEF": 2, "PSI": 4, "PER": 4},
        "rules": [
            _rule("REPLACEMENT_ENTER", "ON_REPLACE_ENTITY", requirements=[{"kind": "REPLACED_CARD_IS", "card_id": "FA-CARD-NINA-DE-LAS-FLORES-CREATURE"}], success=[
                _effect("ADD_LAND_TAG", target="CHOSEN_REVEALED_PUEBLO_LAND", tag="NIEBLA"),
                _effect("MARK_MILESTONE", value="REPLACEMENT_PROOF"),
            ]),
            _rule("BLOCK_PSI_RECOVERY", "WHILE_IN_PLAY", success=[
                _effect("BLOCK_RECOVERY", stat="PSI", targets="CHARACTERS_IN_CURRENT_LAND", duration="WHILE_IN_PLAY")
            ]),
            _rule("WITHER_PSI", "PLAYER_ACTION", label="Marchitar Psique", check=_check("PSI", 8), success=[
                _effect("ADJUST_ENTITY_STAT", target="CHOSEN_TARGET", stat="PSI", amount=-1)
            ]),
        ],
    },
    {
        "id": "FA-CARD-PROCESION-SIN-ROSTROS",
        "name": "La Procesión Sin Rostros",
        "kind": "CHOICE",
        "tags": ["CULTO", "NIEBLA", "PUEBLO"],
        "rules": [
            _rule("REVEAL", "ON_REVEAL", requirements=[{"kind": "ANY_REVEALED_LAND_HAS_TAG", "value": "NIEBLA"}], success=[
                _effect("SPAWN_ENTITY", entity_id="FA-CARD-CULTISTA-ANGULO-NEGRO", count=1, destination="CHOSEN_REVEALED_NIEBLA_LAND"),
                _effect("SPAWN_ENTITY", entity_id="FA-TOKEN-ALDEANO", count=2, state="PASSIVE", destination="SAME_LAND"),
                _effect("MARK_MILESTONE", value="CULT_PRESENCE_CONFIRMED"),
            ]),
            _rule("INTERRUMPIR", "PLAYER_CHOICE", label="Interrumpir", check=_check("FUE", 8, printed_stat="POW"), success=[
                _effect("SET_ENTITY_STATE", target="SPAWNED_CULTIST", state="HOSTILE"),
                _effect("REMOVE_ENTITY", target="SPAWNED_ALDEANOS", reason="ESCAPED"),
            ], failure=[_effect("CALL_CARD", card_id="FA-CARD-RITO-HILOS-NEGROS")]),
            _rule("SEGUIR", "PLAYER_CHOICE", label="Seguirlos", check=_check("PER", 8), success=[
                _effect("SEARCH_AND_STAGE_LAND", source="ADVENTURE_DECK", tags_any=["CASA_DE_LAS_VELAS", "CULTO"], placement="NEXT_THREE"),
                _effect("MARK_MILESTONE", value="CULT_NETWORK_IDENTIFIED"),
                _effect("MARK_MILESTONE", value="ROUTE_IDENTIFIED"),
            ], failure=[_effect("ADJUST_PLAYER_STAT", stat="PER", amount=-1)]),
            _rule("DISPERSAR", "PLAYER_CHOICE", label="Dispersarlos", check=_check("PSI", 8), success=[
                _effect("REMOVE_ENTITY", target="SPAWNED_ALDEANOS", reason="DISPERSED"),
                _effect("ADJUST_CAMPAIGN_VALUE", field="fog_level", amount=-1, minimum=0),
            ], failure=[_effect("ADJUST_ENTITY_STAT", target="SPAWNED_ALDEANOS", stat="PER", amount=-1)]),
        ],
    },
    {
        "id": "FA-CARD-VOZ-EN-LA-NIEBLA",
        "name": "Voz en la Niebla",
        "kind": "EVENT",
        "tags": ["NIEBLA", "MENTE"],
        "rules": [
            _rule("RESOLVE", "ON_REVEAL", check=_check("PER", 8), failure=[
                _effect("ADJUST_ENTITY_STAT", target="CHOSEN_TARGET", stat="PSI", amount=-1),
                _effect("ADJUST_ENTITY_STAT", target="CHOSEN_TARGET", stat="PER", amount=-1),
            ]),
            _rule("VORSHA_CONVERSION_WINDOW", "AFTER_RESOLVE", requirements=[
                {"kind": "ENTITY_STAT_EQ", "target": "CHOSEN_TARGET", "stat": "PSI", "value": -1}
            ], success=[
                _effect("SET_ENTITY_STATE", target="CHOSEN_TARGET", state="VORSHA_CONVERSION_ELIGIBLE"),
                _effect("MARK_MILESTONE", value="REPLACEMENT_SUSPICION"),
            ]),
        ],
    },
    {
        "id": "FA-CARD-VECINO-REEMPLAZADO",
        "name": "Vecino Reemplazado",
        "kind": "CREATURE_EVENT",
        "tags": ["ALTERNO", "NIEBLA"],
        "printed_stats": {"POW": "X", "DEF": "X", "PSI": "X", "PER": "X"},
        "rules": [
            _rule("ENTER_BY_REPLACEMENT", "ON_CALLED_BY_CARD", requirements=[{"kind": "CALLER_CARD_IS", "card_id": "FA-CARD-ROSTRO-PRESTADO"}], success=[
                _effect("SET_ENTITY_STATE", target="SELF", state="ACTIVE", derived_x={"source": "REPLACED_ENTITY_NEGATIVE_PSI", "absolute": True, "minimum": 1}),
                _effect("MARK_MILESTONE", value="REPLACEMENT_PROOF"),
            ]),
            _rule("FOG_BONUS", "WHILE_IN_PLAY", requirements=[{"kind": "CURRENT_LAND_HAS_TAG", "value": "NIEBLA"}], success=[
                _effect("SET_TEMPORARY_MODIFIER", target="SELF", stat="POW", amount=1, duration="WHILE_IN_NIEBLA"),
                _effect("SET_TEMPORARY_MODIFIER", target="SELF", stat="DEF", amount=1, duration="WHILE_IN_NIEBLA"),
            ]),
            _rule("DAMAGE_PER", "AFTER_DEALS_DAMAGE_TO_CHARACTER", check=_check("PER", 8), failure=[
                _effect("ADJUST_ENTITY_STAT", target="DAMAGED_CHARACTER", stat="PER", amount=-1)
            ]),
        ],
    },
    {
        "id": "FA-CARD-FARO-AHOGADO",
        "name": "Faro Ahogado",
        "kind": "LAND",
        "tags": ["OBJETIVO", "COSTA", "TORRE", "NIEBLA", "CLOSED"],
        "rules": [
            _rule("OPEN_WITH_LANTERN", "PLAYER_ACTION", label="Abrir el acceso con la Linterna Etérica", requirements=[
                {"kind": "PLAYER_HAS_ITEM", "item_id": "FA-ITEM-LINTERNA-ETERICA"},
                {"kind": "SELF_HAS_TAG", "value": "CLOSED"},
                {"kind": "NO_HOSTILE_CREATURE_IN_CURRENT_LAND"},
            ], success=[
                _effect("REMOVE_LAND_TAG", target="SELF", tag="CLOSED"),
                _effect("MARK_MILESTONE", value="FARO_ACCESS_SECURED"),
            ]),
            _rule("ACTIVATE", "PLAYER_ACTION", label="Activar el Faro", requirements=[
                {"kind": "PLAYER_HAS_ITEM", "item_id": "FA-ITEM-LINTERNA-ETERICA"},
                {"kind": "SELF_LACKS_TAG", "value": "CLOSED"},
                {"kind": "NO_HOSTILE_CREATURE_IN_CURRENT_LAND"},
                {"kind": "PLAYER_SELECTS_ONE", "values": ["PER", "DRIVER"]},
            ], check={"mode": "DIRECT", "stat_from_choice": ["PER", "DRIVER"], "difficulty": 9}, success=[
                _effect("SET_CAMPAIGN_VALUE", field="master_exiled", value=True),
                _effect("SET_CAMPAIGN_VALUE", field="faro_activated", value=True),
                _effect("MARK_MILESTONE", value="FARO_RESOLVED"),
                _effect("WIN_CAMPAIGN", ending="FARO_ACTIVATED"),
            ]),
            _rule("FACE_UP_PRESSURE", "END_OF_TURN_WHILE_FACE_UP", success=[
                _effect("CALL_CARD", card_id="FA-CARD-EVENTO-ANIMA"),
                _effect("ADJUST_CAMPAIGN_VALUE", field="fog_level", amount=1),
                _effect("ADJUST_CAMPAIGN_VALUE", field="faro_face_up_turns", amount=1),
            ]),
        ],
    },
    {
        "id": "FA-CARD-PESCADOR-OLVIDO-MAR",
        "name": "El Pescador que Olvidó el Mar",
        "kind": "CHOICE",
        "tags": ["PUEBLO", "ALDEANO_ESPECIAL"],
        "rules": [
            _rule("REVEAL", "ON_REVEAL", success=[
                _effect("SPAWN_ENTITY", entity_id="FA-NPC-PESCADOR-PERDIDO", count=1, destination="CURRENT_LAND")
            ]),
            _rule("ESCUCHAR", "PLAYER_CHOICE", label="Escucharlo", check=_check("PSI", 7), success=[
                _effect("ADJUST_CAMPAIGN_VALUE", field="fog_level", amount=-1, minimum=0, requirement="CURRENT_LAND_HAS_AGUA")
            ], failure=[_effect("ADJUST_ENTITY_STAT", target="FA-NPC-PESCADOR-PERDIDO", stat="PSI", amount=-1)]),
            _rule("PEDIR_RUTA", "PLAYER_CHOICE", label="Pedirle ruta", check=_check("PER", 7), success=[
                _effect("SEARCH_AND_STAGE_LAND", source="ADVENTURE_DECK", tags_any=["COSTA", "AGUA"], placement="NEXT_TWO"),
                _effect("MARK_MILESTONE", value="COAST_ROUTE_IDENTIFIED"),
                _effect("MARK_MILESTONE", value="ROUTE_IDENTIFIED"),
            ], failure=[_effect("CALL_CARD", card_id="FA-CARD-GRITO-EN-LA-COSTA")]),
            _rule("DEJAR_ATRAS", "PLAYER_CHOICE", label="Dejarlo atrás", success=[
                _effect("SET_ENTITY_STATE", target="FA-NPC-PESCADOR-PERDIDO", state="ABANDONED"),
                _effect("ADJUST_ENTITY_STAT", target="FA-NPC-PESCADOR-PERDIDO", stat="PER", amount=-1, timing="END_OF_SECTION"),
            ]),
            _rule("VORSHA_FOLLOWUP", "ENTITY_STAT_BECOMES_NEGATIVE", requirements=[
                {"kind": "TARGET_IS", "entity_id": "FA-NPC-PESCADOR-PERDIDO"}, {"kind": "ENTITY_STAT_LT", "stat": "PER", "value": 0}
            ], success=[
                _effect("CALL_CARD", card_id="FA-CARD-FE-TORCIDA", authority="VORSHA_OPTIONAL"),
                _effect("CALL_CARD", card_id="FA-CARD-CULTISTA-ANGULO-NEGRO", authority="VORSHA_OPTIONAL"),
            ]),
        ],
    },
    {
        "id": "FA-CARD-ROSTRO-EN-EL-VIDRIO",
        "name": "Rostro en el Vidrio",
        "kind": "CREATURE_EVENT",
        "tags": ["ANIMA", "NIEBLA", "REFLEJO"],
        "printed_stats": {"POW": 0, "DEF": 0, "PSI": 0, "PER": 0},
        "rules": [
            _rule("PHYSICAL_IMMUNITY", "BEFORE_PHYSICAL_DAMAGE", success=[
                _effect("SET_ENTITY_STATE", target="SELF", state="PHYSICAL_DAMAGE_IMMUNE", duration="WHILE_IN_PLAY")
            ]),
            _rule("COPY_TARGET", "COMBAT_START", success=[
                _effect("COPY_TARGET_PROFILE", target="CHOSEN_TARGET", recipient="SELF", fields=["PARAMETERS", "ATTRIBUTES"], duration="END_OF_COMBAT")
            ]),
            _rule("ENTER_PER", "ON_ENTER", check=_check("PER", 9), failure=[
                _effect("ADJUST_ENTITY_STAT", target="CHOSEN_TARGET", stat="PER", amount=-2)
            ]),
        ],
    },
]


FARO_AHOGADO_INITIAL_STATE = {
    "fog_level": 0,
    "karma": 0,
    "faro_face_up_turns": 0,
    "faro_activated": False,
    "master_exiled": False,
    "milestones": [],
    "called_cards": [],
    "prepared_omens": [],
    "rewards": [],
}


def card_by_id(card_id):
    wanted = str(card_id or "").strip()
    return next((deepcopy(card) for card in FARO_AHOGADO_CARDS if card["id"] == wanted), None)


def rule_by_id(card_id, rule_id):
    card = card_by_id(card_id)
    if not card:
        return None
    wanted = str(rule_id or "").strip()
    return next((deepcopy(rule) for rule in card.get("rules", []) if rule["id"] == wanted), None)


def build_card_resolution_plan(card_id, rule_id, outcome="SUCCESS"):
    """Return the authored persistent mutation plan; never roll or mutate here."""
    card = card_by_id(card_id)
    rule = rule_by_id(card_id, rule_id)
    if not card:
        return {"status": "UNKNOWN_CARD", "accepted": False, "card_id": str(card_id or ""), "build": FARO_AHOGADO_CARD_BUILD}
    if not rule:
        return {"status": "UNKNOWN_RULE", "accepted": False, "card_id": card["id"], "rule_id": str(rule_id or ""), "build": FARO_AHOGADO_CARD_BUILD}
    normalized_outcome = str(outcome or "SUCCESS").upper().strip()
    if normalized_outcome not in {"SUCCESS", "FAILURE"}:
        return {"status": "INVALID_OUTCOME", "accepted": False, "card_id": card["id"], "rule_id": rule["id"], "build": FARO_AHOGADO_CARD_BUILD}
    effects = rule["on_success"] if normalized_outcome == "SUCCESS" else rule["on_failure"]
    return {
        "status": "PLANNED",
        "accepted": True,
        "card_id": card["id"],
        "card_name": card["name"],
        "rule_id": rule["id"],
        "trigger": rule["trigger"],
        "requirements": deepcopy(rule["requirements"]),
        "check": deepcopy(rule["check"]),
        "outcome": normalized_outcome,
        "effects": deepcopy(effects),
        "authority": {"roll": "WORLD_ENGINE", "mutation": "WORLD_ENGINE", "narration": "NON_AUTHORITATIVE"},
        "build": FARO_AHOGADO_CARD_BUILD,
    }


def _iter_effects(card):
    for rule in card.get("rules", []):
        yield from rule.get("on_success", [])
        yield from rule.get("on_failure", [])


def validate_faro_ahogado_cards(cards=None):
    rows = list(FARO_AHOGADO_CARDS if cards is None else cards)
    errors = []
    ids = [str(card.get("id") or "") for card in rows]
    if len(ids) != 14:
        errors.append(f"EXPECTED_14_CARDS:{len(ids)}")
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_CARD_ID")
    known_calls = set(ids) | EXTERNAL_CONTENT_IDS
    for card in rows:
        card_id = str(card.get("id") or "")
        if not card_id:
            errors.append("CARD_WITHOUT_ID")
            continue
        if card.get("kind") not in ALLOWED_CARD_KINDS:
            errors.append(f"INVALID_CARD_KIND:{card_id}:{card.get('kind')}")
        rule_ids = [str(rule.get("id") or "") for rule in card.get("rules", [])]
        if not rule_ids or "" in rule_ids:
            errors.append(f"CARD_WITHOUT_VALID_RULES:{card_id}")
        if len(rule_ids) != len(set(rule_ids)):
            errors.append(f"DUPLICATE_RULE_ID:{card_id}")
        for rule in card.get("rules", []):
            check = rule.get("check") or {}
            if check:
                if check.get("mode") not in ALLOWED_CHECK_MODES:
                    errors.append(f"INVALID_CHECK_MODE:{card_id}:{rule.get('id')}")
                stat = check.get("stat")
                choices = set(check.get("stat_from_choice") or [])
                if stat and stat not in ALLOWED_STATS:
                    errors.append(f"INVALID_CHECK_STAT:{card_id}:{rule.get('id')}:{stat}")
                if choices and not choices.issubset(ALLOWED_STATS):
                    errors.append(f"INVALID_CHOICE_STAT:{card_id}:{rule.get('id')}")
            for effect in list(rule.get("on_success", [])) + list(rule.get("on_failure", [])):
                op = str(effect.get("op") or "")
                if op not in ALLOWED_EFFECTS:
                    errors.append(f"INVALID_EFFECT:{card_id}:{rule.get('id')}:{op}")
                if effect.get("persistence") != "WORLD":
                    errors.append(f"NON_PERSISTENT_EFFECT:{card_id}:{rule.get('id')}:{op}")
                if op == "CALL_CARD" and effect.get("card_id") not in known_calls:
                    errors.append(f"UNKNOWN_CALLED_CARD:{card_id}:{effect.get('card_id')}")
    return {
        "status": "VALID" if not errors else "INVALID",
        "valid": not errors,
        "card_count": len(rows),
        "rule_count": sum(len(card.get("rules", [])) for card in rows),
        "external_dependencies": sorted(EXTERNAL_CONTENT_IDS),
        "errors": errors,
        "build": FARO_AHOGADO_CARD_BUILD,
    }


FARO_AHOGADO_CARD_VALIDATION = validate_faro_ahogado_cards()
