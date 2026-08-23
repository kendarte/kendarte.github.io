from evennia import DefaultCharacter

from .objects import ObjectParent


class Character(DefaultCharacter, ObjectParent):
    """Player/NPC-compatible Siza character base."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.siza_narration = True
        self.db.adventure_stats = {
            "FUE": 2,
            "AGI": 2,
            "COO": 2,
            "INT": 2,
            "PER": 2,
            "PSI": 2,
        }
        self.db.knowledge = {}
        self.db.virtues = {}
        self.db.flaws = {}
        self.db.needs = {}
        self.db.relationships = {}
        self.db.memories = []
        self.db.current_action = None
        self.db.destination_id = None
