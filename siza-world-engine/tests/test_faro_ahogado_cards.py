import unittest

from world.faro_ahogado_cards import (
    FARO_AHOGADO_CARD_VALIDATION,
    FARO_AHOGADO_CARDS,
    build_card_resolution_plan,
)


class FaroAhogadoCardContractTests(unittest.TestCase):
    def test_all_fourteen_cards_validate(self):
        self.assertTrue(FARO_AHOGADO_CARD_VALIDATION["valid"])
        self.assertEqual(14, FARO_AHOGADO_CARD_VALIDATION["card_count"])
        self.assertEqual([], FARO_AHOGADO_CARD_VALIDATION["errors"])

    def test_every_effect_is_world_persistent(self):
        effects = []
        for card in FARO_AHOGADO_CARDS:
            for rule in card["rules"]:
                effects.extend(rule["on_success"])
                effects.extend(rule["on_failure"])
        self.assertTrue(effects)
        self.assertTrue(all(effect["persistence"] == "WORLD" for effect in effects))

    def test_nina_failure_can_lead_to_real_replacement(self):
        question = build_card_resolution_plan("FA-CARD-LA-NINA-DE-LAS-FLORES", "PREGUNTAR", "FAILURE")
        self.assertEqual("ADJUST_ENTITY_STAT", question["effects"][0]["op"])
        replacement = build_card_resolution_plan(
            "FA-CARD-NINA-DE-LAS-FLORES-CREATURE",
            "NEGATIVE_PSI_REPLACEMENT",
            "SUCCESS",
        )
        operations = [effect["op"] for effect in replacement["effects"]]
        self.assertIn("REPLACE_ENTITY", operations)
        self.assertIn("MARK_MILESTONE", operations)

    def test_routes_share_one_campaign_milestone(self):
        fisherman = build_card_resolution_plan("FA-CARD-PESCADOR-OLVIDO-MAR", "PEDIR_RUTA", "SUCCESS")
        procession = build_card_resolution_plan("FA-CARD-PROCESION-SIN-ROSTROS", "SEGUIR", "SUCCESS")
        for plan in (fisherman, procession):
            milestones = [effect.get("value") for effect in plan["effects"] if effect["op"] == "MARK_MILESTONE"]
            self.assertIn("ROUTE_IDENTIFIED", milestones)

    def test_faro_open_and_activation_are_separate(self):
        opening = build_card_resolution_plan("FA-CARD-FARO-AHOGADO", "OPEN_WITH_LANTERN", "SUCCESS")
        activation = build_card_resolution_plan("FA-CARD-FARO-AHOGADO", "ACTIVATE", "SUCCESS")
        self.assertIn("REMOVE_LAND_TAG", [effect["op"] for effect in opening["effects"]])
        self.assertNotIn("WIN_CAMPAIGN", [effect["op"] for effect in opening["effects"]])
        self.assertIn("WIN_CAMPAIGN", [effect["op"] for effect in activation["effects"]])
        milestones = [effect.get("value") for effect in activation["effects"] if effect["op"] == "MARK_MILESTONE"]
        self.assertIn("FARO_RESOLVED", milestones)

    def test_unknown_card_fails_closed(self):
        plan = build_card_resolution_plan("NOT-A-CARD", "NOPE", "SUCCESS")
        self.assertFalse(plan["accepted"])
        self.assertEqual("UNKNOWN_CARD", plan["status"])


if __name__ == "__main__":
    unittest.main()
