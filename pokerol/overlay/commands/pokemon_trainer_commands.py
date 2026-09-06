from evennia import Command

from services.pokemon_bag_engine import add_item, bag_state
from services.pokemon_battle_runtime import current_battle, submit_player_battle_action
from services.pokemon_party_engine import add_pokemon, party_state, set_active_slot


def _demo_move(move_id, name, pokemon_type, power, accuracy, damage_class="PHYSICAL", priority=0):
    return {
        "move_id": move_id,
        "name": name,
        "pokemon_type": pokemon_type,
        "damage_class": damage_class,
        "power": power,
        "accuracy": accuracy,
        "priority": priority,
        "pp": 20,
        "world_enabled": False,
        "world_effects": [],
        "materials": ["CREATURE"],
        "delivery": "CONTACT",
        "requirements": {},
    }


def _demo_owned_pikachu():
    return {
        "species_id": "PKMN-025",
        "species_name": "Pikachu",
        "level": 8,
        "types": ["Electric"],
        "base_stats": {"HP": 35, "ATK": 55, "DEF": 40, "SPA": 50, "SPD": 50, "SPE": 90},
        "moves": [
            _demo_move("THUNDER-SHOCK", "Thunder Shock", "Electric", 40, 100, "SPECIAL"),
            _demo_move("QUICK-ATTACK", "Quick Attack", "Normal", 40, 100, "PHYSICAL", 1),
        ],
        "sprite": {
            "front": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
            "back": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/25.png",
            "icon": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
            "scale": 1.25,
        },
    }


def _demo_owned_bulbasaur():
    return {
        "species_id": "PKMN-001",
        "species_name": "Bulbasaur",
        "level": 7,
        "types": ["Grass", "Poison"],
        "base_stats": {"HP": 45, "ATK": 49, "DEF": 49, "SPA": 65, "SPD": 65, "SPE": 45},
        "moves": [
            _demo_move("TACKLE", "Tackle", "Normal", 40, 100),
            _demo_move("VINE-WHIP", "Vine Whip", "Grass", 45, 100),
        ],
        "sprite": {
            "front": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
            "back": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/1.png",
            "icon": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
            "scale": 1.25,
        },
    }


class CmdPokerolParty(Command):
    key = "equipo"
    aliases = ["party", "pokemon-equipo"]
    locks = "cmd:all()"

    def func(self):
        state = party_state(self.caller)
        rows = state.get("party") or []
        if not rows:
            self.caller.msg("No tienes Pokémon en el equipo.")
            return
        self.caller.msg("=== EQUIPO POKÉMON ===")
        for row in rows:
            marker = ">" if row.get("active") else " "
            self.caller.msg(
                f"{marker} {int(row.get('party_slot', 0)) + 1}. {row.get('nickname') or row.get('species_name')} "
                f"Lv{row.get('level')} HP {row.get('hp_current')}/{row.get('hp_max')} {row.get('status') or 'OK'}"
            )
        self.caller.msg(f"Storage: {state.get('storage_count', 0)}")


class CmdPokerolActivePokemon(Command):
    key = "pokemon-activo"
    aliases = ["activo", "active-pokemon"]
    locks = "cmd:all()"

    def func(self):
        raw = str(self.args or "").strip()
        try:
            slot = int(raw) - 1
        except ValueError:
            self.caller.msg("Uso: pokemon-activo <1-6>")
            return
        battle = current_battle(self.caller)
        if battle and str(battle.get("status") or "").upper() == "ACTIVE":
            result = submit_player_battle_action(self.caller, {"type": "SWITCH", "slot": slot})
        else:
            result = set_active_slot(self.caller, slot, require_able=True)
        self.caller.msg(str(result.get("status")))


class CmdPokerolBag(Command):
    key = "bolsa"
    aliases = ["bag", "mochila"]
    locks = "cmd:all()"

    def func(self):
        state = bag_state(self.caller)
        items = state.get("items") or {}
        self.caller.msg("=== BOLSA ===")
        if not items:
            self.caller.msg("Vacía.")
            return
        for item_id, count in sorted(items.items()):
            self.caller.msg(f"{item_id}: {count}")


class CmdPokerolGiveItem(Command):
    key = "pokerol-dar-item"
    aliases = ["dar-item"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = str(self.args or "").strip().split()
        if not parts:
            self.caller.msg("Uso: pokerol-dar-item <ITEM_ID> [cantidad]")
            return
        item_id = parts[0]
        try:
            amount = int(parts[1]) if len(parts) > 1 else 1
        except ValueError:
            self.caller.msg("Cantidad inválida.")
            return
        result = add_item(self.caller, item_id, amount)
        self.caller.msg(f"{result.get('status')} | {result.get('item_id')}={result.get('count')}")


class CmdPokerolTrainerTest(Command):
    key = "entrenador-prueba"
    aliases = ["trainer-test"]
    locks = "cmd:perm(Admin)"

    def func(self):
        state = party_state(self.caller)
        if not state.get("party"):
            add_pokemon(self.caller, _demo_owned_pikachu())
            add_pokemon(self.caller, _demo_owned_bulbasaur())
        add_item(self.caller, "POKE_BALL", 5)
        self.caller.msg("Entrenador de prueba preparado: Party + 5 POKE_BALL.")
