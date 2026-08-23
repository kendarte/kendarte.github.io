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

        # Obvious authored sensory facts. Entering/looking does not roll for these.
        self.db.sensory_facts = {
            "sight": [],
            "hearing": [],
            "smell": [],
            "touch": [],
            "taste": [],
        }

        # Physical orientation data for prose. Missing fields mean unknown, not absent.
        self.db.space_profile = {
            "room_type": None,
            "scale": None,
            "geometry": None,
            "orientation": None,
            "focal_points": [],
            "status": "prototype",
        }

        # Authored uncertain facts. PER may reveal these, but can never create new ones.
        # Each entry can contain: id, sense, difficulty, target, keywords, fact.
        self.db.perception_facts = []

        self.db.conditions = {}
        self.db.world_state = {}
