from .characters import Character


class NPC(Character):
    """Persistent non-player character with authored knowledge, memory and routine state."""

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
        self.db.current_activity = None
        self.db.destination_id = None
        self.db.simulation_enabled = False

        self.db.canon_status = "prototype"
