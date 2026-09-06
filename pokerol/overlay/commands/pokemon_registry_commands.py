from evennia import Command

from services.pokemon_battle_runtime import start_pokemon_battle_from_party
from services.pokemon_party_engine import add_pokemon
from services.pokemon_species_registry import (
    registry_state,
    spawn_species_profile,
    species_template,
)


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
            self.caller.msg("Uso: encuentro-salvaje <SPECIES_ID> [nivel]")
            return
        species_id = parts[0]
        try:
            level = int(parts[1]) if len(parts) > 1 else None
        except ValueError:
            self.caller.msg("Nivel inválido.")
            return
        profile = spawn_species_profile(species_id, level=level, wild=True)
        if not profile:
            self.caller.msg(f"Species no registrada: {species_id}")
            return
        result = start_pokemon_battle_from_party(
            self.caller,
            profile,
            battle_kind="WILD",
            source_event_id="DEBUG-WILD-ENCOUNTER",
        )
        self.caller.msg(
            f"{result.get('status')} | {profile.get('species_name')} Lv{profile.get('level')} | "
            f"spawn={profile.get('entity_id')}"
        )
