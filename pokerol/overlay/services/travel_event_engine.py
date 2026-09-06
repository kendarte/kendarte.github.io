"""Room-to-room travel event generator for POKEROL.

Every successful room transition may generate a local episodic beat. The engine
keeps this separate from the persistent World Event Engine: most travel beats are
small encounters, while unresolved/important beats can later be promoted into
persistent consequences or world events.
"""

from __future__ import annotations

import random
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


TRAVEL_EVENT_BUILD = "0.1.0-anime-travel-beats"
HISTORY_LIMIT = 24
ROOM_HISTORY_LIMIT = 60

BASE_EVENT_CHANCE = {
    "laboratory interior": 0.18,
    "pokemon center interior": 0.16,
    "shop interior": 0.16,
    "school interior": 0.18,
    "small city street": 0.32,
    "city gate": 0.38,
    "urban fringe": 0.42,
    "rural settlement": 0.34,
    "village green": 0.42,
    "meadow": 0.58,
    "country route": 0.62,
    "route clearing": 0.56,
    "rolling ridge": 0.58,
    "grass hollow": 0.66,
    "shallow stream": 0.64,
    "small grove": 0.67,
    "forest": 0.76,
    "dense forest": 0.80,
    "forest clearing": 0.75,
    "forest stream": 0.78,
}

# These are broad anime-adventure archetypes rather than episode copies. Content
# authors can add exact campaign-specific templates in room.db.travel_event_profile.
ARCHETYPES = {
    "WILD_POKEMON": [
        {
            "id": "wild-curious",
            "title": "Pokémon curioso",
            "premise": "Un Pokémon salvaje observa al grupo y decide acercarse por curiosidad.",
            "stakes": ["trust", "capture", "observation"],
        },
        {
            "id": "wild-territorial",
            "title": "Territorio ocupado",
            "premise": "Un Pokémon salvaje interpreta la llegada como una intrusión en su territorio.",
            "stakes": ["deescalation", "battle", "route_access"],
        },
        {
            "id": "wild-foraging",
            "title": "Comida disputada",
            "premise": "Un Pokémon salvaje está buscando comida y reacciona a los suministros del grupo.",
            "stakes": ["food", "trust", "tracking"],
        },
    ],
    "POKEMON_HELP": [
        {
            "id": "pokemon-injured",
            "title": "Pokémon herido",
            "premise": "Hay señales claras de un Pokémon salvaje herido que intenta ocultarse.",
            "stakes": ["rescue", "medicine", "trust"],
        },
        {
            "id": "pokemon-trapped",
            "title": "Pokémon atrapado",
            "premise": "Un Pokémon ha quedado atrapado por el terreno, basura humana o vegetación.",
            "stakes": ["rescue", "world_move", "trust"],
        },
        {
            "id": "pokemon-lost",
            "title": "Pokémon perdido",
            "premise": "Un Pokémon joven parece separado de su grupo o entrenador.",
            "stakes": ["tracking", "escort", "relationship"],
        },
    ],
    "NPC_HELP": [
        {
            "id": "traveler-needs-help",
            "title": "Viajero en problemas",
            "premise": "Un viajero necesita ayuda con una situación que no requiere necesariamente combatir.",
            "stakes": ["help", "social", "resource"],
        },
        {
            "id": "research-request",
            "title": "Petición de campo",
            "premise": "Un investigador o estudiante busca ayuda para observar o recuperar algo del bioma.",
            "stakes": ["investigation", "knowledge", "reward"],
        },
        {
            "id": "missing-pokemon-owner",
            "title": "Buscando a su Pokémon",
            "premise": "Una persona busca a un Pokémon que se separó de ella en la zona.",
            "stakes": ["tracking", "escort", "trust"],
        },
    ],
    "TRAINER": [
        {
            "id": "trainer-challenge",
            "title": "Entrenador desafiante",
            "premise": "Otro entrenador propone una batalla amistosa o una prueba de habilidad.",
            "stakes": ["battle", "sportsmanship", "reputation"],
        },
        {
            "id": "trainer-technique",
            "title": "Entrenamiento compartido",
            "premise": "Un entrenador practica una técnica peculiar y acepta comparar métodos.",
            "stakes": ["training", "knowledge", "relationship"],
        },
    ],
    "RIVAL": [
        {
            "id": "rival-crossing",
            "title": "Cruce con el rival",
            "premise": "El rival aparece siguiendo su propia ruta y convierte el encuentro en una competencia.",
            "stakes": ["rivalry", "battle", "race", "information"],
        }
    ],
    "TEAM_TROUBLE": [
        {
            "id": "rocket-scheme",
            "title": "Problemas con el Team Rocket",
            "premise": "Una operación oportunista intenta robar, engañar o capturar Pokémon aprovechando la zona.",
            "stakes": ["rescue", "chase", "battle", "investigation"],
        },
        {
            "id": "suspicious-trap",
            "title": "Trampa sospechosa",
            "premise": "Algo en el camino parece preparado para atraer Pokémon o viajeros hacia una trampa.",
            "stakes": ["perception", "investigation", "rescue"],
        },
    ],
    "DISCOVERY": [
        {
            "id": "unusual-tracks",
            "title": "Rastros inusuales",
            "premise": "El terreno muestra rastros que no encajan con la actividad normal del bioma.",
            "stakes": ["tracking", "mystery", "knowledge"],
        },
        {
            "id": "hidden-cache",
            "title": "Hallazgo inesperado",
            "premise": "Algo útil o extraño ha quedado oculto entre el terreno y la vegetación.",
            "stakes": ["perception", "item", "story_hook"],
        },
    ],
    "ENVIRONMENT": [
        {
            "id": "blocked-route",
            "title": "Paso bloqueado",
            "premise": "Un obstáculo natural o accidente vuelve el camino más complicado de lo habitual.",
            "stakes": ["world_move", "detour", "rescue"],
        },
        {
            "id": "weather-shift",
            "title": "Cambio brusco del clima",
            "premise": "El clima cambia lo suficiente para afectar visibilidad, terreno o comportamiento Pokémon.",
            "stakes": ["shelter", "navigation", "ecology"],
        },
    ],
    "MYSTERY": [
        {
            "id": "strange-sound",
            "title": "Algo entre los árboles",
            "premise": "Un sonido, luz o movimiento difícil de identificar invita a investigar.",
            "stakes": ["perception", "mystery", "choice"],
        },
        {
            "id": "local-rumor-manifest",
            "title": "El rumor parece real",
            "premise": "Algo que los viajeros comentan sobre esta zona parece estar ocurriendo de verdad.",
            "stakes": ["investigation", "knowledge", "risk"],
        },
    ],
}

DEFAULT_TYPE_WEIGHTS = {
    "WILD_POKEMON": 28,
    "POKEMON_HELP": 12,
    "NPC_HELP": 11,
    "TRAINER": 10,
    "RIVAL": 5,
    "TEAM_TROUBLE": 6,
    "DISCOVERY": 11,
    "ENVIRONMENT": 10,
    "MYSTERY": 7,
}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _clamp(value, low, high):
    return max(low, min(high, value))


def _room_profile(room):
    raw = _dict(getattr(room.db, "travel_event_profile", {})) if room else {}
    return raw


def _room_type(room):
    if not room:
        return ""
    space = _dict(getattr(room.db, "space_profile", {}))
    return str(space.get("room_type") or "").strip().lower()


def _base_chance(room):
    profile = _room_profile(room)
    if "event_chance" in profile:
        try:
            return _clamp(float(profile["event_chance"]), 0.0, 1.0)
        except (TypeError, ValueError):
            pass
    room_type = _room_type(room)
    if room_type in BASE_EVENT_CHANCE:
        return BASE_EVENT_CHANCE[room_type]
    if "forest" in room_type:
        return 0.76
    if "route" in room_type or "meadow" in room_type:
        return 0.60
    if "city" in room_type or "settlement" in room_type:
        return 0.36
    if "interior" in room_type:
        return 0.18
    return 0.48


def _populations(room):
    return [row for row in _list(getattr(room.db, "pokemon_populations", [])) if _dict(row)] if room else []


def _weighted_choice(rows, weight_key="weight", rng=None):
    rng = rng or random.SystemRandom()
    normalized = []
    total = 0.0
    for row in rows:
        item = _dict(row)
        try:
            weight = max(0.0, float(item.get(weight_key, 0) or 0))
        except (TypeError, ValueError):
            weight = 0.0
        if weight <= 0:
            continue
        total += weight
        normalized.append((total, item))
    if not normalized or total <= 0:
        return None
    needle = rng.random() * total
    for ceiling, item in normalized:
        if needle <= ceiling:
            return item
    return normalized[-1][1]


def _recent_types(actor):
    history = _list(getattr(actor.db, "travel_event_history", [])) if actor else []
    return [str(row.get("event_type") or "") for row in history[-4:] if _dict(row)]


def _type_weights(actor, room):
    weights = dict(DEFAULT_TYPE_WEIGHTS)
    profile = _room_profile(room)
    for key, value in _dict(profile.get("weights")).items():
        try:
            weights[str(key).upper()] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue

    populations = _populations(room)
    if not populations:
        weights["WILD_POKEMON"] *= 0.15
        weights["POKEMON_HELP"] *= 0.35

    room_type = _room_type(room)
    if "forest" in room_type:
        weights["WILD_POKEMON"] *= 1.35
        weights["POKEMON_HELP"] *= 1.20
        weights["MYSTERY"] *= 1.20
        weights["TRAINER"] *= 0.75
    elif "city" in room_type or "settlement" in room_type or "interior" in room_type:
        weights["NPC_HELP"] *= 1.35
        weights["TRAINER"] *= 1.20
        weights["WILD_POKEMON"] *= 0.55
    elif "route" in room_type or "meadow" in room_type:
        weights["TRAINER"] *= 1.20
        weights["WILD_POKEMON"] *= 1.10

    recent = _recent_types(actor)
    for event_type in recent:
        if event_type in weights:
            weights[event_type] *= 0.45

    return weights


def _choose_event_type(actor, room, rng=None):
    rows = [
        {"event_type": key, "weight": value}
        for key, value in _type_weights(actor, room).items()
    ]
    chosen = _weighted_choice(rows, rng=rng)
    return str((chosen or {}).get("event_type") or "DISCOVERY")


def _choose_species(room, rng=None):
    rng = rng or random.SystemRandom()
    rows = []
    for raw in _populations(room):
        pop = _dict(raw)
        species_id = str(pop.get("species_id") or "").strip()
        if not species_id:
            continue
        try:
            abundance = max(0.01, float(pop.get("abundance", 1.0) or 1.0))
        except (TypeError, ValueError):
            abundance = 1.0
        rows.append({**pop, "weight": abundance})
    chosen = _weighted_choice(rows, rng=rng)
    if not chosen:
        return None
    level_range = _list(chosen.get("level_range"))
    if len(level_range) >= 2:
        try:
            low, high = int(level_range[0]), int(level_range[1])
            if high < low:
                low, high = high, low
            level = rng.randint(max(1, low), max(1, high))
        except (TypeError, ValueError):
            level = None
    else:
        level = None
    return {
        "species_id": chosen.get("species_id"),
        "level": level,
        "habitat": chosen.get("habitat"),
        "behavior": chosen.get("behavior"),
        "activity": chosen.get("activity"),
        "clues": _list(chosen.get("clues")),
    }


def _authored_archetypes(room, event_type):
    profile = _room_profile(room)
    library = _dict(profile.get("archetypes"))
    rows = [_dict(row) for row in _list(library.get(event_type)) if _dict(row)]
    return rows


def _choose_archetype(room, event_type, rng=None):
    rng = rng or random.SystemRandom()
    rows = _authored_archetypes(room, event_type) or ARCHETYPES.get(event_type, [])
    return deepcopy(rng.choice(rows)) if rows else {
        "id": "generic-beat",
        "title": "Algo ocurre en el camino",
        "premise": "La llegada al lugar desencadena una situación que exige una decisión.",
        "stakes": ["choice"],
    }


def _archive_previous_pending(actor, destination):
    previous = _dict(getattr(actor.db, "pending_travel_event", {})) if actor else {}
    if not previous or str(previous.get("status") or "").upper() not in {"ACTIVE", "PENDING"}:
        return None
    archived = dict(previous)
    archived["status"] = "LEFT_BEHIND"
    archived["left_at"] = datetime.now(timezone.utc).isoformat()
    archived["left_for_room_id"] = str(getattr(destination.db, "room_id", "") or "") if destination else None
    history = _list(getattr(actor.db, "travel_event_history", []))
    history.append(archived)
    actor.db.travel_event_history = history[-HISTORY_LIMIT:]
    actor.db.pending_travel_event = None
    return archived


def _persist_event(actor, room, packet):
    actor.db.pending_travel_event = dict(packet)
    actor_history = _list(getattr(actor.db, "travel_event_history", []))
    actor_history.append(dict(packet))
    actor.db.travel_event_history = actor_history[-HISTORY_LIMIT:]

    room_history = _list(getattr(room.db, "travel_event_history", []))
    room_history.append(dict(packet))
    room.db.travel_event_history = room_history[-ROOM_HISTORY_LIMIT:]


def _format_intro(packet):
    title = str(packet.get("title") or "Algo ocurre")
    premise = str(packet.get("premise") or "").strip()
    species = _dict(packet.get("wild_pokemon"))
    species_text = ""
    if species.get("species_id"):
        species_text = f" [{species.get('species_id')}" + (f" · Lv {species.get('level')}" if species.get("level") else "") + "]"
    return f"\n[EVENTO DE VIAJE] {title}{species_text}\n{premise}"


def roll_travel_event(actor, source_room, destination_room, exit_obj=None, *, rng=None):
    """Roll one episodic beat after a successful room transition.

    Returns a packet even when no event fires. Only fired events are persisted as
    pending travel events.
    """
    if not actor or not destination_room:
        return {"status": "INVALID_TRAVEL", "triggered": False, "build": TRAVEL_EVENT_BUILD}

    profile = _room_profile(destination_room)
    if profile.get("enabled") is False:
        return {"status": "DISABLED", "triggered": False, "build": TRAVEL_EVENT_BUILD}

    rng = rng or random.SystemRandom()
    abandoned = _archive_previous_pending(actor, destination_room)
    chance = _base_chance(destination_room)
    roll = rng.randint(1, 100)
    threshold = int(round(chance * 100))

    base = {
        "build": TRAVEL_EVENT_BUILD,
        "roll": roll,
        "threshold": threshold,
        "source_room_id": str(getattr(source_room.db, "room_id", "") or "") if source_room else None,
        "destination_room_id": str(getattr(destination_room.db, "room_id", "") or ""),
        "destination_room_key": str(destination_room.key),
        "exit_id": str(getattr(getattr(exit_obj, "db", None), "exit_id", "") or "") if exit_obj else None,
        "abandoned_previous": abandoned,
    }

    if roll > threshold:
        return {**base, "status": "NO_EVENT", "triggered": False}

    event_type = _choose_event_type(actor, destination_room, rng=rng)
    archetype = _choose_archetype(destination_room, event_type, rng=rng)
    wild = _choose_species(destination_room, rng=rng) if event_type in {"WILD_POKEMON", "POKEMON_HELP"} else None

    packet = {
        **base,
        "status": "ACTIVE",
        "triggered": True,
        "travel_event_id": f"TRAVEL-{uuid4().hex[:12].upper()}",
        "event_type": event_type,
        "archetype_id": archetype.get("id"),
        "title": archetype.get("title"),
        "premise": archetype.get("premise"),
        "stakes": _list(archetype.get("stakes")),
        "wild_pokemon": wild,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "resolution": None,
    }
    _persist_event(actor, destination_room, packet)
    actor.msg(_format_intro(packet))
    return packet


def resolve_pending_travel_event(actor, resolution, *, notes=None):
    pending = _dict(getattr(actor.db, "pending_travel_event", {})) if actor else {}
    if not pending:
        return {"status": "NO_PENDING_TRAVEL_EVENT", "resolved": False}
    resolved = dict(pending)
    resolved["status"] = "RESOLVED"
    resolved["resolution"] = str(resolution or "RESOLVED").strip().upper()
    resolved["resolution_notes"] = str(notes or "").strip() or None
    resolved["resolved_at"] = datetime.now(timezone.utc).isoformat()
    actor.db.pending_travel_event = None
    history = _list(getattr(actor.db, "travel_event_history", []))
    history.append(resolved)
    actor.db.travel_event_history = history[-HISTORY_LIMIT:]
    return {"status": "TRAVEL_EVENT_RESOLVED", "resolved": True, "event": resolved}
