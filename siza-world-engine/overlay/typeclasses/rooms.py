from evennia import DefaultRoom


class Room(DefaultRoom):
    """Atomic persistent location for Siza."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.room_id = None
        self.db.zone_id = None
        self.db.region_id = None
        self.db.settlement_id = None
        self.db.district_id = None
        self.db.canon_status = "prototype"
        self.db.sensory_facts = {
            "sight": [],
            "hearing": [],
            "smell": [],
            "touch": [],
            "taste": [],
        }
        self.db.conditions = {}
        self.db.world_state = {}
