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

        # Optional authored visibility gate evaluated against the persistent
        # world_state of the object's current containing room/site.
        self.db.state_visibility_requirements = []

        # Authored interactions available on this persistent object. Hard actor
        # requirements reuse Skill/Knowledge/world_state gates; object_state_requirements
        # are evaluated against this object's own persistent db.state.
        self.db.object_actions = []
