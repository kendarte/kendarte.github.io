from evennia import Command

from services.pokemon_battle_runtime import start_pokemon_battle_from_party
from services.pokemon_party_engine import add_pokemon
from services.pokemon_species_registry import (
    registry_state,
    spawn_species_profile,
    species_template,
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


def _room_water_bodies(actor):
    room = getattr(actor, "location", None) if actor else None
    rows = []
    for raw in _list(getattr(getattr(room, "db", None), "water_bodies", [])):
        row = _dict(raw)
        body_id = str(row.get("id") or "").strip()
        if body_id:
            rows.append(row)
    return rows


class CmdPokerolPokemonRegistry(Command):
    key = "pokemon-registry"
    aliases = ["pokedex-registry", "species-registry"]
    locks = "cmd:all()"

    def func(self):
        state = registry_state()
        self.caller.msg("=== POKEROL SPECIES REGISTRY ===")
        self.caller.msg(
            f"exists={state.get('exists')} | species={state.get('species_count')} | moves={state.get('move_count')}"
        )
        meta = state.get("meta") or {}
        if meta:
            self.caller.msg(f"set={meta.get('name') or meta}")


class CmdPokerolGivePokemon(Command):
    key = "pokerol-dar-pokemon"
    aliases = ["dar-pokemon"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = str(self.args or "").strip().split()
        if not parts:
            self.caller.msg("Uso: pokerol-dar-pokemon <SPECIES_ID> [nivel]")
            return
        species_id = parts[0]
        try:
            level = int(parts[1]) if len(parts) > 1 else None
        except ValueError:
            self.caller.msg("Nivel inválido.")
            return
        if not species_template(species_id):
            self.caller.msg(f"Species no registrada: {species_id}")
            return
        profile = spawn_species_profile(species_id, level=level, wild=False)
        if not profile:
            self.caller.msg(f"No se pudo construir {species_id}.")
            return
        result = add_pokemon(self.caller, profile, prefer_party=True)
        pokemon = result.get("pokemon") or {}
        self.caller.msg(
            f"{result.get('status')} | {pokemon.get('species_name')} Lv{pokemon.get('level')} | "
            f"instance={pokemon.get('instance_id')}"
        )


class CmdPokerolWildEncounter(Command):
    key = "encuentro-salvaje"
    aliases = ["wild-encounter"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = str(self.args or "").strip().split()
        if not parts:
            self.caller.msg("Uso: encuentro-salvaje <SPECIES_ID> [nivel] [WATER_BODY_ID]")
            return
        species_id = parts[0]
        try:
            level = int(parts[1]) if len(parts) > 1 else None
        except ValueError:
            self.caller.msg("Nivel inválido.")
            return
        medium_id = str(parts[2] if len(parts) > 2 else "").strip()
        profile = spawn_species_profile(species_id, level=level, wild=True)
        if not profile:
            self.caller.msg(f"Species no registrada: {species_id}")
            return

        if medium_id:
            bodies = _room_water_bodies(self.caller)
            body = next((row for row in bodies if str(row.get("id") or "").strip() == medium_id), None)
            if not body:
                available = ", ".join(str(row.get("id")) for row in bodies) or "ninguno"
                self.caller.msg(f"Water body inexistente en este Room: {medium_id}. Disponibles: {available}")
                return
            profile["contact_medium_id"] = medium_id
            profile["contact_medium_kind"] = str(body.get("kind") or "water")
            profile["battle_position"] = {
                "medium_id": medium_id,
                "medium_kind": profile["contact_medium_kind"],
                "source": "DEBUG_EXPLICIT",
            }

        result = start_pokemon_battle_from_party(
            self.caller,
            profile,
            battle_kind="WILD",
            source_event_id="DEBUG-WILD-ENCOUNTER",
        )
        medium_text = f" | medium={medium_id}" if medium_id else ""
        self.caller.msg(
            f"{result.get('status')} | {profile.get('species_name')} Lv{profile.get('level')} | "
            f"spawn={profile.get('entity_id')}{medium_text}"
        )
