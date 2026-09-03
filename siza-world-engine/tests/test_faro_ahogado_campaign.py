import unittest

from services.dm_campaign_director import get_campaign_state, project_campaign_evidence, start_campaign
from world.faro_ahogado_vertical_slice import FARO_AHOGADO_CAMPAIGN


class _DB:
    pass


class _Actor:
    def __init__(self):
        self.db = _DB()


class FaroAhogadoCampaignTests(unittest.TestCase):
    def setUp(self):
        self.actor = _Actor()
        start_campaign(self.actor, FARO_AHOGADO_CAMPAIGN, force=True)

    def observe(self, *milestones, action_types=None):
        return project_campaign_evidence(
            self.actor,
            FARO_AHOGADO_CAMPAIGN,
            {
                "authority": "WORLD_ENGINE",
                "source": "UNIT_TEST",
                "campaign_milestones": list(milestones),
                "action_types": list(action_types or []),
            },
        )

    def test_generic_engine_activity_does_not_advance_campaign(self):
        for action_type in (
            "KNOWLEDGE_FACT_SHARED",
            "MOVEMENT_EXECUTED",
            "OBJECT_ACTION_EXECUTED",
            "COMBAT_RESOLVED",
            "WORLD_ACTION_RESOLVED",
        ):
            result = self.observe(action_types=[action_type])
            self.assertFalse(result["advanced"])
            self.assertEqual("FA-BEAT-LEAD", get_campaign_state(self.actor)["active_beat_id"])

    def test_replacement_and_route_require_exact_milestones(self):
        lead = self.observe("REPLACEMENT_PROOF")
        self.assertTrue(lead["advanced"])
        self.assertEqual("FA-BEAT-ROUTE", get_campaign_state(self.actor)["active_beat_id"])
        self.assertEqual(1, get_campaign_state(self.actor)["signals"]["replacement"])

        movement = self.observe(action_types=["MOVEMENT_EXECUTED"])
        self.assertFalse(movement["advanced"])
        route = self.observe("ROUTE_IDENTIFIED")
        self.assertTrue(route["advanced"])
        self.assertEqual("FA-BEAT-MEANS", get_campaign_state(self.actor)["active_beat_id"])

    def test_full_authoritative_milestone_sequence_completes_campaign(self):
        milestones = (
            "REPLACEMENT_PROOF",
            "ROUTE_IDENTIFIED",
            "EXPEDITION_MEANS_SECURED",
            "CLIMAX_THREAT_RESOLVED",
            "FARO_RESOLVED",
        )
        for milestone in milestones:
            result = self.observe(milestone)
            self.assertTrue(result["advanced"])
        state = get_campaign_state(self.actor)
        self.assertEqual("COMPLETED", state["status"])
        self.assertIsNone(state["active_beat_id"])
        self.assertEqual(5, len(state["completed_beats"]))

    def test_non_world_evidence_is_rejected(self):
        result = project_campaign_evidence(
            self.actor,
            FARO_AHOGADO_CAMPAIGN,
            {"authority": "DM", "campaign_milestones": ["REPLACEMENT_PROOF"]},
        )
        self.assertFalse(result["advanced"])
        self.assertEqual("AUTHORITATIVE_EVIDENCE_REQUIRED", result["status"])


if __name__ == "__main__":
    unittest.main()
