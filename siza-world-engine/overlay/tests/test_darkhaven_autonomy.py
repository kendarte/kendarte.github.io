import sys
import types
import unittest
from pathlib import Path


OVERLAY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = OVERLAY_ROOT.parent
if str(OVERLAY_ROOT) not in sys.path:
    sys.path.insert(0, str(OVERLAY_ROOT))


evennia = sys.modules.setdefault("evennia", types.ModuleType("evennia"))
evennia.search_object = getattr(evennia, "search_object", lambda *_a, **_k: [])
evennia.search_script = getattr(evennia, "search_script", lambda *_a, **_k: [])
evennia.create_script = getattr(evennia, "create_script", lambda *_a, **_k: None)
evennia.create_object = getattr(evennia, "create_object", lambda *_a, **_k: None)
evennia.search_tag = getattr(evennia, "search_tag", lambda *_a, **_k: [])
if not hasattr(evennia, "DefaultScript"):
    class DefaultScript:
        pass
    evennia.DefaultScript = DefaultScript

from services import actor_registry, job_engine, need_engine, npc_simulation, relationship_engine, world_event_engine
from typeclasses import world_tick
from world import darkhaven_autonomy_patch as autonomy


class DB:
    pass


class Tags:
    def __init__(self):
        self.rows = []
    def add(self, key, category=None):
        self.rows.append((key, category))


class Room:
    def __init__(self, room_id):
        self.id = abs(hash(room_id)) % 100000
        self.key = room_id
        self.db = DB()
        self.db.room_id = room_id
        self.tags = Tags()
        self.exits = []


class Exit:
    def __init__(self, destination):
        self.destination = destination
        self.db = DB()
        self.db.hidden = False
        self.db.is_locked = False
        self.db.door_state = "open"


class Actor:
    def __init__(self, npc_id, location):
        self.id = abs(hash(npc_id)) % 100000
        self.key = npc_id
        self.location = location
        self.db = DB()
        self.db.npc_id = npc_id
        self.db.decision_enabled = True
        self.db.simulation_enabled = True
        self.db.job = {}
        self.db.needs = {}
        self.db.need_rules = []
        self.db.is_npc = True
        self.db.relationships = {}
        self.db.social_relationships = {}
        self.db.knowledge = {}
        self.db.knowledge_facts = []


class Script:
    def __init__(self, ident=10):
        self.id = ident
        self.db = DB()
        self.db.last_world_clock_result = None
        self.db.last_producer_results = None
        self.db.last_event_results = None
        self.db.last_handoff_results = None
        self.db.last_arbitration_results = None
        self.db.last_need_results = None
        self.db.last_activity_need_results = None
        self.db.trace_history = None
    def start(self, **_kwargs):
        self.started = True


class DarkhavenAutonomyTests(unittest.TestCase):
    def test_a_world_tick_bootstrap_is_idempotent(self):
        scripts = []
        original_search, original_create = world_tick.search_script, world_tick.create_script
        try:
            world_tick.search_script = lambda *_a, **_k: list(scripts)
            def create(*_args, **_kwargs):
                script = Script(41)
                scripts.append(script)
                return script
            world_tick.create_script = create
            world_tick.ensure_world_clock = lambda *_a, **_k: None
            first = world_tick.ensure_world_tick()
            second = world_tick.ensure_world_tick()
        finally:
            world_tick.search_script, world_tick.create_script = original_search, original_create
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(len(scripts), 1)
        self.assertEqual(second["duplicate_count"], 0)

    def test_b_selected_autonomy_cohort_is_bounded(self):
        self.assertEqual(autonomy.AUTONOMY_NPC_IDS, set(autonomy.AUTONOMY))
        self.assertNotIn("NPC-DH7-RELENA", autonomy.AUTONOMY_NPC_IDS)
        self.assertNotIn("NPC-DH7-TRIMAGO", autonomy.AUTONOMY_NPC_IDS)

    def test_c_each_selected_npc_has_locations_and_routine(self):
        room_ids = {row[0] for row in autonomy.seed.ROOMS}
        for config in autonomy.AUTONOMY.values():
            self.assertTrue({config["home_room_id"], config["work_room_id"], config["rest_room_id"]} <= room_ids)
            self.assertTrue(config["routine"])
            self.assertTrue(all(room_id in room_ids for room_id, _activity in config["routine"]))

    def test_d_routine_path_uses_real_passable_exits(self):
        start, middle, target = Room("START"), Room("MIDDLE"), Room("TARGET")
        start.exits = [Exit(middle)]
        middle.exits = [Exit(target)]
        path = npc_simulation.find_path(start, target)
        self.assertEqual(len(path), 2)
        self.assertIs(path[-1].destination, target)

    def test_e_jobs_are_engine_contract_tasks(self):
        task = autonomy._autonomy_task("TASK", "JOB", "working")
        self.assertEqual(task["status"], "available")
        self.assertTrue(task["active"])
        self.assertGreater(task["work_required"], 0)
        self.assertIn("job_id", task)

    def test_f_job_and_need_candidates_use_real_engine_contracts(self):
        worksite, restsite = Room("WORK"), Room("REST")
        worksite.db.job_tasks = [autonomy._autonomy_task("TASK", "JOB", "working")]
        restsite.db.need_affordances = [{"id": "REST", "kind": "rest", "need_key": "rest", "enabled": True}]
        actor = Actor("NPC", worksite)
        actor.db.job = {"id": "JOB"}
        actor.db.needs = {"rest": 80}
        actor.db.need_rules = [{"id": "REST-RULE", "need_key": "rest", "affordance": "rest", "op": "GTE", "value": 70, "priority": 75}]
        original_job, original_need = job_engine.search_tag, need_engine.search_tag
        try:
            job_engine.search_tag = lambda *_a, **_k: [worksite]
            need_engine.search_tag = lambda *_a, **_k: [restsite]
            jobs = job_engine.collect_job_candidates(actor)
            needs = need_engine.collect_need_candidates(actor)
        finally:
            job_engine.search_tag, need_engine.search_tag = original_job, original_need
        self.assertEqual(jobs[0]["type"], "JOB")
        self.assertEqual(needs[0]["type"], "NEED")

    def test_g_event_candidate_is_materialized_by_world_event_engine(self):
        observation = Room("DH7-ROOM-023")
        observation.key = "Observation"
        observation.db.world_event_state = {"minor_anomaly": True}
        observation.db.world_event_rules = [{"id": "RULE", "event_id": "EVENT", "field": "minor_anomaly", "op": "EQ", "value": True, "goal_type": "EVENT", "npc_ids": ["SQUEEK"], "awareness_mode": "AUDIENCE"}]
        observation.db.world_event_instances = []
        actor = Actor("SQUEEK", observation)
        original_tag, original_npcs = world_event_engine.search_tag, world_event_engine.siza_npcs
        try:
            world_event_engine.search_tag = lambda *_a, **_k: [observation]
            world_event_engine.siza_npcs = lambda: [actor]
            world_event_engine.refresh_world_event_rules()
            candidates = world_event_engine.collect_event_candidates(actor)
        finally:
            world_event_engine.search_tag, world_event_engine.siza_npcs = original_tag, original_npcs
        self.assertEqual(candidates[0]["type"], "EVENT")

    def test_h_fact_share_creates_a_real_relationship_candidate(self):
        room = Room("ROOM")
        source, target = Actor("SOURCE", room), Actor("TARGET", room)
        source.id, target.id = 101, 102
        source.db.knowledge = {"TOPIC": 1}
        source.db.knowledge_facts = [{"id": "FACT", "topic": "fact", "knowledge_key": "TOPIC", "required_level": 1, "fact_status": "ACTIVE"}]
        original_objects = actor_registry._objects
        try:
            actor_registry._objects = lambda: [source, target]
            created = relationship_engine.create_fact_share_obligation(source, target, "FACT", priority=65)
            candidates = relationship_engine.collect_relationship_candidates(source)
            resolved = relationship_engine.resolve_relationship_goal(source, created["obligation_id"], target_social_entity_id="NPC:TARGET")
        finally:
            actor_registry._objects = original_objects
        self.assertTrue(created["success"])
        self.assertEqual(candidates[0]["relationship_kind"], "SHARE_FACT")
        self.assertEqual(candidates[0]["target_social_entity_id"], "NPC:TARGET")
        self.assertTrue(resolved["completed"])
        self.assertTrue(resolved["fact_shared"])

    def test_i_installed_event_is_consumed_by_world_event_engine(self):
        text = Path(autonomy.__file__).read_text(encoding="utf-8")
        self.assertIn("siza_event_site", text)
        self.assertIn("DH7-EVENT-MINOR-ANOMALY", text)
        self.assertIn('"goal_type": "EVENT"', text)

    def test_j_fact_share_is_an_explicit_social_obligation(self):
        text = Path(autonomy.__file__).read_text(encoding="utf-8")
        self.assertIn("create_fact_share_obligation(squeek, dino", text)
        self.assertIn("DH7-FACT-TUT-ORIENTATION-001", text)

    def test_k_no_kalnaj_discovery_dependency(self):
        for relative in ("services/actor_registry.py", "services/npc_simulation.py", "world/darkhaven_autonomy_patch.py"):
            self.assertNotIn("kalnaj_pilot_v03_entities", (OVERLAY_ROOT / relative).read_text(encoding="utf-8"))

    def test_l_update_bootstraps_tick_and_validator_is_available(self):
        update = (REPO_ROOT / "update_world_engine.bat").read_text(encoding="utf-8")
        validator = REPO_ROOT / "VALIDAR_DARKHAVEN_AUTONOMY.bat"
        self.assertIn("ensure_world_tick", update)
        self.assertIn("darkhaven_autonomy_patch", update)
        self.assertTrue(validator.is_file())


if __name__ == "__main__":
    unittest.main()
