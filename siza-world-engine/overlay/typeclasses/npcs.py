from .characters import Character


class NPC(Character):
    """Persistent non-player character with authored knowledge, memory, routine and decision state."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_npc = True
        self.db.siza_narration = False
        self.db.npc_id = None
        self.db.job = {}
        self.db.knowledge = {}
        self.db.knowledge_facts = []
        self.db.dialogue_greeting = ""

        # Persistent simulation state. Routine mechanics remain prototype data
        # until the world clock and final need math are frozen.
        self.db.home_room_id = None
        self.db.work_room_id = None
        self.db.rest_room_id = None
        self.db.routine = []
        self.db.routine_index = 0
        self.db.routine_hold_remaining = 0
        self.db.current_activity = None
        self.db.destination_id = None
        self.db.simulation_enabled = False

        # Persistent need state. Values/rules/dynamics are data-driven and remain
        # prototype until their final progression math is defined.
        self.db.needs = {}
        self.db.need_rules = []
        self.db.need_dynamics = []
        self.db.need_dynamics_clock = 0

        # Decision Layer. Goals are explicit persistent records supplied by
        # authored systems; NPCs do not invent world facts, targets or priorities.
        self.db.decision_enabled = False
        self.db.decision_priorities = {
            "DANGER": 100,
            "EVENT": 80,
            "NEED": 70,
            "JOB": 60,
            "RELATIONSHIP": 50,
            "ROUTINE": 10,
        }
        self.db.decision_goals = []
        self.db.current_goal = None

        self.db.canon_status = "prototype"
