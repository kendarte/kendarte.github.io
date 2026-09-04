import sys
import types
import unittest
from pathlib import Path

OVERLAY_ROOT = Path(__file__).resolve().parents[1]
if str(OVERLAY_ROOT) not in sys.path:
    sys.path.insert(0, str(OVERLAY_ROOT))

evennia = types.ModuleType("evennia")
evennia.search_object = lambda *_a, **_k: []
evennia.search_script = lambda *_a, **_k: []
evennia.create_script = lambda *_a, **_k: None
evennia.search_tag = lambda *_a, **_k: []
sys.modules.setdefault("evennia", evennia)

from services import actor_registry, social_graph_engine as graph
from services.combat_profile_engine import combat_participant, combat_profile
from services.consequence_engine import apply_consequence_effects_to_actor
from services.dm_context_broker import _resolve_engine_query


class DB: pass

class Actor:
    def __init__(self, ident, *, npc_id=None, player=False, location=None):
        self.id, self.key, self.db, self.location = ident, "actor-%s" % ident, DB(), location
        self.db.is_npc = npc_id is not None
        self.db.npc_id = npc_id
        self.db.siza_narration = player
        self.db.relationships = {}
        self.db.social_relationships = {}
        self.db.memories = []
        self.db.state = {}
        self.db.combat_profile = {}
        self.db.tcg_profile = {}
        self.db.tcg_loadout = {}
        self.db.tcg_deck_id = ""


class Room:
    def __init__(self):
        self.id, self.key, self.db, self.contents = 99, "Real Room", DB(), []
        self.db.room_id, self.db.state, self.db.world_context_tags = "ROOM-REAL", {"flooded": True}, ["RAIN"]


class BlockOneTests(unittest.TestCase):
    def setUp(self):
        self.room = Room()
        self.a, self.b = Actor(1, npc_id="A", location=self.room), Actor(2, npc_id="B", location=self.room)
        self.player = Actor(3, player=True, location=self.room)
        self.room.contents = [self.a, self.b, self.player]
        actor_registry._objects = lambda: [self.a, self.b, self.player]

    def test_a_directed_relationships(self):
        graph.adjust_relationship_dimension(self.a, self.b, "trust", 25)
        self.assertEqual(graph.read_relationship(self.a, self.b)["trust"], 25)
        self.assertIsNone(graph.read_relationship(self.b, self.a))

    def test_b_legacy_writer_syncs_immediately(self):
        self.a.db.relationships = {"B": {"trust": 42, "obligations": []}}
        graph.sync_legacy_relationships(self.a)
        self.assertEqual(graph.read_relationship(self.a, self.b)["trust"], 42)

    def test_c_npc_to_player_is_real_edge(self):
        graph.add_relationship_obligation(self.a, self.player, {"id": "meet", "active": True})
        row = graph.read_relationship(self.a, self.player)
        self.assertEqual(row["target_social_entity_id"], "PLAYER:3")
        self.assertEqual(row["obligations"][0]["id"], "meet")

    def test_d_read_only_social_query_persists_nothing(self):
        before = (dict(self.a.db.relationships), dict(self.a.db.social_relationships), getattr(self.player.db, "social_entity_id", None))
        data = _resolve_engine_query("player_social_context", self.a, "", {"target_social_entity": "PLAYER:3"}, "")
        self.assertEqual(data["status"], "RESOLVED")
        self.assertEqual(before, (dict(self.a.db.relationships), dict(self.a.db.social_relationships), getattr(self.player.db, "social_entity_id", None)))

    def test_e_f_memory_does_not_become_relationship(self):
        self.a.db.memories.append({"id": "memory"})
        graph.adjust_relationship_dimension(self.a, self.b, "respect", 9)
        self.assertEqual(self.a.db.memories, [{"id": "memory"}])
        self.assertEqual(graph.read_relationship(self.a, self.b)["respect"], 9)

    def test_e_consequence_updates_npc_relationship(self):
        rule = {"relationship_effects": [{"operation": "ADJUST", "dimension": "trust", "value": 8, "target_npc_id": "B"}]}
        apply_consequence_effects_to_actor(rule, {"action_id": "npc-effect"}, self.a, npc_lookup={"A": self.a, "B": self.b})
        self.assertEqual(graph.read_relationship(self.a, self.b)["trust"], 8)

    def test_f_consequence_updates_player_relationship(self):
        rule = {"relationship_effects": [{"operation": "ADD_ROLE", "role": "ALLY", "target_social_entity_id": "PLAYER:3"}]}
        apply_consequence_effects_to_actor(rule, {"action_id": "player-effect"}, self.a, npc_lookup={"A": self.a, "B": self.b})
        self.assertEqual(graph.read_relationship(self.a, self.player)["roles"], ["ALLY"])

    def test_g_actor_discovery_is_campaign_neutral(self):
        self.assertEqual([x.db.npc_id for x in actor_registry.siza_npcs()], ["A", "B"])
        self.assertEqual(actor_registry.siza_actors(include_npcs=False), [self.player])

    def test_h_visible_room_state_is_room_state(self):
        data = _resolve_engine_query("visible_room_state", self.a, "", {}, "")["data"]
        self.assertEqual(data["room_id"], "ROOM-REAL")
        self.assertEqual(data["state"], {"flooded": True})

    def test_i_active_campaign_state_is_director_state(self):
        self.a.db.dm_campaign_state = {"campaign_id": "DH", "active_beat_id": "BEAT-1"}
        data = _resolve_engine_query("active_campaign_state", self.a, "", {}, "")["data"]
        self.assertEqual(data["state"]["active_beat_id"], "BEAT-1")

    def test_j_k_l_combat_canonical_and_legacy_fallback(self):
        self.a.db.combat_profile = {"deck_id": "CANON", "world_status": {"alive": True}}
        self.a.db.tcg_deck_id, self.a.db.tcg_profile, self.a.db.tcg_loadout = "LEGACY", {"life": 20}, {"x": 1}
        self.assertEqual(combat_profile(self.a)["deck_id"], "CANON")
        self.a.db.combat_profile = {}
        self.a.db.state = {"alive": True}
        result = combat_profile(self.a)
        self.assertEqual((result["deck_id"], result["tcg_profile"], result["loadout"], result["world_status"]), ("LEGACY", {"life": 20}, {"x": 1}, {"alive": True}))

    def test_m_combat_participant_uses_given_actor(self):
        self.player.db.tcg_deck_id = "PLAYER-DECK"
        self.assertEqual(combat_participant(self.player, "PLAYER:3")["entity_id"], "PLAYER:3")
        self.assertEqual(combat_participant(self.player, "PLAYER:3")["deck_id"], "PLAYER-DECK")


if __name__ == "__main__":
    unittest.main()
