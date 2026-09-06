"""Bridge local Travel Beats into authoritative Pokémon encounters."""

from copy import deepcopy

from services.pokemon_battle_runtime import start_pokemon_battle_from_party
from services.pokemon_species_registry import spawn_species_profile


BRIDGE_BUILD = "0.1.0-travel-wild-battle"


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _text(value):
    return str(value or "").strip()


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
        }
        actor.db.pending_travel_event = deepcopy(pending)

    return {
        "accepted": True,
        "status": "WILD_BATTLE_STARTED",
        "species_id": species_id,
        "battle_id": _text(_dict(result.get("battle")).get("battle_id")),
        "build": BRIDGE_BUILD,
    }
