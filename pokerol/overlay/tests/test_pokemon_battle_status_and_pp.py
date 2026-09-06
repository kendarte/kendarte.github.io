import random
import unittest

from services.pokemon_battle_engine import create_battle, resolve_player_action
from services.pokemon_battle_status_engine import end_turn_effects


class PokemonBattleStatusAndPPTests(unittest.TestCase):
    def _move(self, move_id, name, pokemon_type, power, pp=5, damage_class="SPECIAL"):
        return {
            "move_id": move_id,
            "name": name,
            "pokemon_type": pokemon_type,
            "damage_class": damage_class,
            "power": power,
            "accuracy": 100,
            "priority": 0,
            "pp": pp,
            "pp_max": pp,
            "pp_current": pp,
            "world_enabled": False,
            "world_effects": [],
            "materials": ["CREATURE"],
        }

    def _pokemon(self, entity_id, name, types, moves, speed=50):
        return {
            "entity_id": entity_id,
            "species_id": entity_id,
            "species_name": name,
            "level": 10,
            "types": types,
            "base_stats": {"HP": 50, "ATK": 50, "DEF": 50, "SPA": 50, "SPD": 50, "SPE": speed},
            "moves": moves,
            "known_moves": [row["move_id"] for row in moves],
        }

    def test_pp_is_spent_by_server(self):
        thunder = self._move("THUNDER-SHOCK", "Thunder Shock", "Electric", 40, pp=2)
        tackle = self._move("TACKLE", "Tackle", "Normal", 40, pp=10, damage_class="PHYSICAL")
        battle = create_battle(
            self._pokemon("P1", "Pikachu", ["Electric"], [thunder], speed=90),
            self._pokemon("E1", "Caterpie", ["Bug"], [tackle], speed=20),
        )
        result = resolve_player_action(battle, {"type": "MOVE", "move_id": "THUNDER-SHOCK"}, rng=random.Random(3))
        self.assertTrue(result["accepted"])
        move = result["battle"]["player"]["moves"][0]
        self.assertEqual(move["pp_current"], 1)

    def test_zero_pp_is_rejected(self):
        thunder = self._move("THUNDER-SHOCK", "Thunder Shock", "Electric", 40, pp=1)
        thunder["pp_current"] = 0
        tackle = self._move("TACKLE", "Tackle", "Normal", 40)
        battle = create_battle(
            self._pokemon("P1", "Pikachu", ["Electric"], [thunder]),
            self._pokemon("E1", "Caterpie", ["Bug"], [tackle]),
        )
        result = resolve_player_action(battle, {"type": "MOVE", "move_id": "THUNDER-SHOCK"}, rng=random.Random(1))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["status"], "NO_PP")

    def test_thunder_wave_paralyzes(self):
        wave = self._move("THUNDER-WAVE", "Thunder Wave", "Electric", 0, pp=20, damage_class="STATUS")
        tackle = self._move("TACKLE", "Tackle", "Normal", 40)
        battle = create_battle(
            self._pokemon("P1", "Pikachu", ["Electric"], [wave], speed=90),
            self._pokemon("E1", "Pidgey", ["Normal", "Flying"], [tackle], speed=20),
        )
        result = resolve_player_action(battle, {"type": "MOVE", "move_id": "THUNDER-WAVE"}, rng=random.Random(4))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["battle"]["enemy"]["status"], "PARALYSIS")

    def test_poison_causes_residual_damage(self):
        pokemon = {"name": "Weedle", "hp_max": 80, "hp_current": 80, "status": "POISON"}
        events = end_turn_effects(pokemon)
        self.assertEqual(pokemon["hp_current"], 70)
        self.assertTrue(any(row.get("kind") == "STATUS_DAMAGE" for row in events))


if __name__ == "__main__":
    unittest.main()
