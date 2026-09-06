import random
import unittest

from services.pokemon_battle_engine import create_battle
from services.pokemon_battle_physics_impact_engine import apply_world_physics_to_battle


class PokemonBattleSharedMediumTests(unittest.TestCase):
    def _thunder_shock(self):
        return {
            "move_id": "THUNDER-SHOCK",
            "name": "Thunder Shock",
            "pokemon_type": "ELECTRIC",
            "damage_class": "SPECIAL",
            "power": 40,
            "accuracy": 100,
            "pp": 30,
            "pp_max": 30,
            "pp_current": 30,
            "world_enabled": True,
            "world_effects": ["ELECTRIFY", "SHORT_CIRCUIT"],
            "materials": ["CREATURE", "WATER", "METAL", "ELECTRICAL_DEVICE"],
        }

    def _pokemon(self, entity_id, name, types, speed=50):
        return {
            "entity_id": entity_id,
            "species_id": entity_id,
            "species_name": name,
            "level": 10,
            "types": types,
            "base_stats": {"HP": 50, "ATK": 50, "DEF": 50, "SPA": 55, "SPD": 50, "SPE": speed},
            "moves": [self._thunder_shock()],
            "known_moves": ["THUNDER-SHOCK"],
        }

    def test_electricity_in_water_hits_enemy_in_same_medium(self):
        battle = create_battle(
            self._pokemon("P1", "Pikachu", ["Electric"], speed=90),
            self._pokemon("E1", "Magikarp", ["Water"], speed=20),
        )
        battle["enemy"]["contact_medium_id"] = "WB-POND"
        before = battle["enemy"]["hp_current"]
        result = apply_world_physics_to_battle(
            battle,
            battle["player"]["moves"][0],
            {"executed": True, "target_water_body_id": "WB-POND"},
            rng=random.Random(1),
        )
        self.assertTrue(result["applied"])
        self.assertLess(battle["enemy"]["hp_current"], before)
        self.assertEqual(battle["player"]["hp_current"], battle["player"]["hp_max"])

    def test_all_battle_participants_in_same_water_are_hit(self):
        battle = create_battle(
            self._pokemon("P1", "Pikachu", ["Electric"], speed=90),
            self._pokemon("E1", "Poliwag", ["Water"], speed=20),
        )
        battle["player"]["contact_medium_id"] = "WB-CREEK"
        battle["enemy"]["contact_medium_id"] = "WB-CREEK"
        p_before = battle["player"]["hp_current"]
        e_before = battle["enemy"]["hp_current"]
        result = apply_world_physics_to_battle(
            battle,
            battle["player"]["moves"][0],
            {"executed": True, "target_water_body_id": "WB-CREEK"},
            rng=random.Random(2),
        )
        self.assertTrue(result["applied"])
        self.assertLess(battle["player"]["hp_current"], p_before)
        self.assertLess(battle["enemy"]["hp_current"], e_before)
        self.assertEqual({row["side"] for row in result["impacts"]}, {"PLAYER", "ENEMY"})

    def test_ground_type_in_water_keeps_electric_immunity(self):
        battle = create_battle(
            self._pokemon("P1", "Pikachu", ["Electric"], speed=90),
            self._pokemon("E1", "Groundmon", ["Ground"], speed=20),
        )
        battle["enemy"]["contact_medium_id"] = "WB-POND"
        before = battle["enemy"]["hp_current"]
        result = apply_world_physics_to_battle(
            battle,
            battle["player"]["moves"][0],
            {"executed": True, "target_water_body_id": "WB-POND"},
            rng=random.Random(3),
        )
        self.assertTrue(result["applied"])
        self.assertEqual(battle["enemy"]["hp_current"], before)
        self.assertEqual(result["impacts"][0]["effectiveness"], 0.0)


if __name__ == "__main__":
    unittest.main()
