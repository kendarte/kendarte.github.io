"""Bridge local Travel Beats into authoritative Pokémon encounters."""

from copy import deepcopy

from services.pokemon_battle_runtime import start_pokemon_battle_from_party
from services.pokemon_species_registry import spawn_species_profile


BRIDGE_BUILD = "0.2.0-wild-contact-medium"
AQUATIC_HINTS = (
    "water", "pond", "stream", "river", "lake", "creek", "pool", "canal",
    "agua", "estanque", "arroyo", "rio", "río", "lago", "acuatic", "acuátic",
)


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


def _text(value):
    return str(value or "").strip()


def _room_water_bodies(actor):
    room = getattr(actor, "location", None) if actor else None
    return [_dict(row) for row in _list(getattr(getattr(room, "db", None), "water_bodies", [])) if _dict(row)]


def _aquatic_habitat(value):
    raw = _text(value).lower()
    return bool(raw and any(hint in raw for hint in AQUATIC_HINTS))


def _resolve_spawn_medium(actor, wild):
    bodies = _room_water_bodies(actor)
    if not bodies:
        return None
    explicit = _text(_dict(wild).get("water_body_id"))
    if explicit:
        for body in bodies:
            if _text(body.get("id")) == explicit:
                return {"id": explicit, "kind": _text(body.get("kind")), "source": "POPULATION_EXPLICIT"}
    habitat = _text(_dict(wild).get("habitat"))
    if not _aquatic_habitat(habitat):
        return None
    low = habitat.lower()
    for body in bodies:
        kind = _text(body.get("kind")).lower()
        if kind and kind in low and _text(body.get("id")):
            return {"id": _text(body.get("id")), "kind": kind, "source": "HABITAT_KIND_MATCH"}
    first = bodies[0]
    body_id = _text(first.get("id"))
    return {"id": body_id, "kind": _text(first.get("kind")), "source": "AQUATIC_SINGLE_OR_FIRST"} if body_id else None


def activate_travel_event_encounter(actor, packet):
    event = _dict(packet)
    if not actor or not bool(event.get("triggered")):
        return {"accepted": False, "status": "NO_TRIGGERED_EVENT", "build": BRIDGE_BUILD}
    if _text(event.get("event_type")).upper() != "WILD_POKEMON":
        return {"accepted": False, "status": "EVENT_NOT_COMBAT_FORCED", "build": BRIDGE_BUILD}

    wild = _dict(event.get("wild_pokemon"))
    species_id = _text(wild.get("species_id"))
    if not species_id:
        return {"accepted": False, "status": "NO_WILD_SPECIES", "build": BRIDGE_BUILD}

    profile = spawn_species_profile(species_id, level=wild.get("level"), wild=True)
    if not profile:
        actor.msg(f"[POKEROL] Falta plantilla registrada para {species_id}; el evento queda pendiente.")
        return {"accepted": False, "status": "SPECIES_NOT_REGISTERED", "species_id": species_id, "build": BRIDGE_BUILD}

    medium = _resolve_spawn_medium(actor, wild)
    if medium:
        profile["contact_medium_id"] = medium["id"]
        profile["contact_medium_kind"] = medium.get("kind")
        profile["battle_position"] = {"medium_id": medium["id"], "medium_kind": medium.get("kind"), "source": medium.get("source")}

    result = start_pokemon_battle_from_party(
        actor,
        profile,
        battle_kind="WILD",
        source_event_id=_text(event.get("travel_event_id")),
    )
    if not result.get("accepted"):
        actor.msg(f"[POKEROL] Encuentro salvaje pendiente: {result.get('status')}")
        return {**result, "species_id": species_id, "build": BRIDGE_BUILD}

    pending = _dict(getattr(actor.db, "pending_travel_event", {}))
    if _text(pending.get("travel_event_id")) == _text(event.get("travel_event_id")):
        pending["encounter_status"] = "BATTLE_STARTED"
        pending["battle_id"] = _text(_dict(result.get("battle")).get("battle_id"))
        pending["wild_instance"] = {
            "entity_id": profile.get("entity_id"),
            "species_id": profile.get("species_id"),
            "level": profile.get("level"),
            "contact_medium_id": profile.get("contact_medium_id"),
            "contact_medium_kind": profile.get("contact_medium_kind"),
        }
        actor.db.pending_travel_event = deepcopy(pending)

    return {
        "accepted": True,
        "status": "WILD_BATTLE_STARTED",
        "species_id": species_id,
        "battle_id": _text(_dict(result.get("battle")).get("battle_id")),
        "contact_medium_id": profile.get("contact_medium_id"),
        "build": BRIDGE_BUILD,
    }
