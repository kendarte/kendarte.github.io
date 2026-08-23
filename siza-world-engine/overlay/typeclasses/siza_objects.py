from evennia import DefaultObject


class WorldObject(DefaultObject):
    """Persistent interactable world object for Siza."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.object_id = None
        self.db.hidden = False
        self.db.portable = False
        self.db.state = {}
        self.db.interaction_facts = []
        self.db.canon_status = "prototype"
