import unittest

from services.anime_world_physics_engine import resolve_anime_physics


class AnimeWorldPhysicsTests(unittest.TestCase):
    def test_fire_ignites_dry_wood(self):
        move = {"move_id": "EMBER", "world_effects": ["HEAT", "BURN", "IGNITE"]}
        target = {
            "materials": ["WOOD"],
            "physical_properties": {"flammability": 0.9, "ignition_point_c": 160},
            "environmental_state": {"temperature_c": 25, "wetness": 0.0},
        }
        result = resolve_anime_physics(move, target, intensity=1.2)
        self.assertTrue(result["target"]["environmental_state"]["burning"])
        self.assertIn("IGNITED", {event["type"] for event in result["events"]})

    def test_water_extinguishes_burning_target(self):
        move = {"move_id": "WATER-GUN", "world_effects": ["WATER", "SOAK", "COOL"]}
        target = {
            "materials": ["WOOD"],
            "environmental_state": {"temperature_c": 180, "wetness": 0.0, "burning": True},
        }
        result = resolve_anime_physics(move, target)
        state = result["target"]["environmental_state"]
        self.assertFalse(state["burning"])
        self.assertGreater(state["wetness"], 0)

    def test_electricity_hits_every_member_of_shared_water(self):
        move = {"move_id": "THUNDER-SHOCK", "world_effects": ["ELECTRIFY"]}
        target = {
            "materials": ["WATER"],
            "water_body_id": "WB-POND",
            "physical_properties": {"conductivity": 1.0},
            "environmental_state": {"wetness": 1.0},
        }
        environment = {
            "water_body_id": "WB-POND",
            "medium_members": [
                {"id": "pokemon-a", "distance_m": 1},
                {"id": "pokemon-b", "distance_m": 4},
                {"id": "trainer-a", "distance_m": 6},
            ],
        }
        result = resolve_anime_physics(move, target, environment=environment)
        self.assertEqual(len(result["area_impacts"]), 3)
        self.assertEqual({row["effect"] for row in result["area_impacts"]}, {"ELECTRIC_SHOCK"})

    def test_hot_glass_then_water_can_thermal_shock_break(self):
        heat = {"move_id": "EMBER", "world_effects": ["HEAT"]}
        water = {"move_id": "WATER-GUN", "world_effects": ["WATER", "SOAK", "COOL"]}
        target = {
            "materials": ["GLASS", "FRAGILE_STRUCTURE"],
            "physical_properties": {"thermal_shock_sensitivity": 1.0},
            "environmental_state": {"temperature_c": 20, "integrity": 1.0},
        }
        heated = resolve_anime_physics(heat, target, intensity=2.0)["target"]
        cooled = resolve_anime_physics(water, heated, environment={"water_temperature_c": 8}, intensity=1.5)
        events = {event["type"] for event in cooled["events"]}
        self.assertTrue(events & {"THERMAL_SHOCK_CRACK", "THERMAL_SHOCK_BREAK"})

    def test_freezing_water_creates_surface(self):
        move = {"move_id": "ICE-MOVE", "world_effects": ["FREEZE"]}
        target = {
            "materials": ["WATER"],
            "environmental_state": {"temperature_c": 12, "wetness": 1.0},
        }
        result = resolve_anime_physics(move, target, intensity=1.5)
        self.assertTrue(result["target"]["environmental_state"]["frozen"])
        self.assertIn("FROZEN_SURFACE_CREATED", {event["type"] for event in result["events"]})


if __name__ == "__main__":
    unittest.main()
