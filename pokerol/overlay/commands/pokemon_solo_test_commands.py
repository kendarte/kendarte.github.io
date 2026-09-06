import os

from evennia import Command

from commands.pokemon_battle_commands import _demo_caterpie
from commands.pokemon_trainer_commands import _demo_owned_bulbasaur, _demo_owned_pikachu
from services.pokemon_bag_engine import add_item
from services.pokemon_battle_runtime import current_battle, start_pokemon_battle
from services.pokemon_multiplayer_session_engine import session_for_actor
from services.pokemon_party_engine import active_pokemon, add_pokemon, party_state


SOLO_TEST_BUILD = "0.1.0-local-solo-smoke-test"


def _solo_mode_enabled():
    return str(os.environ.get("POKEROL_SOLO_TEST_MODE") or "").strip().lower() in {"1", "true", "yes", "on"}


class CmdPokerolSoloTest(Command):
    key = "solo-prueba"
    aliases = ["pokerol-solo", "solo-test"]
    locks = "cmd:all()"

    def func(self):
        if not _solo_mode_enabled():
            self.caller.msg("SOLO_TEST_MODE_DISABLED. Inicie con PROBAR_POKEROL_SOLO.bat.")
            return

        multiplayer = session_for_actor(self.caller)
        if multiplayer and str(multiplayer.db.status or "").upper() in {"LOBBY", "ACTIVE"}:
            self.caller.msg("SOLO_TEST_BLOCKED_BY_MULTIPLAYER_SESSION")
            return

        battle = current_battle(self.caller)
        if battle and str(battle.get("status") or "").upper() == "ACTIVE":
            self.caller.msg("SOLO_TEST_BATTLE_ALREADY_ACTIVE")
            return

        state = party_state(self.caller)
        if not state.get("party"):
            add_pokemon(self.caller, _demo_owned_pikachu())
            add_pokemon(self.caller, _demo_owned_bulbasaur())

        for item_id, amount in (
            ("POKE_BALL", 5),
            ("GREAT_BALL", 2),
            ("POTION", 3),
            ("ANTIDOTE", 1),
            ("PARALYZE_HEAL", 1),
            ("FULL_HEAL", 1),
            ("REVIVE", 1),
            ("ETHER", 1),
        ):
            add_item(self.caller, item_id, amount)

        player = active_pokemon(self.caller)
        if not player:
            self.caller.msg("SOLO_TEST_NO_ACTIVE_POKEMON")
            return

        result = start_pokemon_battle(
            self.caller,
            player,
            _demo_caterpie(),
            battle_kind="WILD",
            source_event_id="SOLO_TEST",
        )
        self.caller.msg(
            f"SOLO TEST {result.get('status')} | Pikachu/Bulbasaur + Bag preparados | build={SOLO_TEST_BUILD}"
        )
