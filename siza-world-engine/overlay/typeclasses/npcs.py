from .characters import Character


class NPC(Character):
    """Persistent non-player character with authored knowledge and memory."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_npc = True
        self.db.siza_narration = False
        self.db.npc_id = None
        self.db.job = {}
        self.db.knowledge = {}
        self.db.knowledge_facts = []
        self.db.dialogue_greeting = ""
        self.db.canon_status = "prototype"
