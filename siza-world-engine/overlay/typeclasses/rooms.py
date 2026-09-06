from evennia import DefaultRoom

from services.object_visibility_engine import object_visible_in_world_state


SECTION_MARKERS = (
    "Personas presentes:",
    "Personas:",
    "A la vista:",
    "Ves:",
    "Salidas:",
    "Exits:",
    "Characters:",
    "You see:",
    "SIZA Scene Image:",
)


PLACEHOLDER_PREFIXES = (
    "the current location will be described here.",
    "the current location will be described here",
)


def _description_only(value):
    text = str(value or "").replace("\r", "\n").strip()
    if not text:
        return ""

    lowered = text.lower()
    for prefix in PLACEHOLDER_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix):].strip()
            while text.startswith("-"):
                text = text[1:].strip()
            lowered = text.lower()
            break

    cut_at = len(text)
    lowered = text.lower()
    for marker in SECTION_MARKERS:
        index = lowered.find(marker.lower())
        if index >= 0:
            cut_at = min(cut_at, index)
    return text[:cut_at].strip()


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
        self.db.scene_image = {"src": "", "alt": "", "position": "center center", "fit": "cover"}
        self.db.scene_manifest = {
            "version": 1,
            "orientation": {
                "arrival_summary": "",
                "spatial_answer": "",
                "time_context": "",
                "current_activity": "",
            },
            "narrator_answers": [],
            "entities": [],
            "hidden_discoveries": [],
            "free_action_hooks": [],
        }

        self.db.sensory_facts = {
            "sight": [],
            "hearing": [],
            "smell": [],
            "touch": [],
            "taste": [],
        }

        self.db.space_profile = {
            "room_type": None,
            "scale": None,
            "geometry": None,
            "orientation": None,
            "focal_points": [],
            "status": "prototype",
        }

        self.db.perception_facts = []
        self.db.job_tasks = []
        self.db.conditions = {}
        self.db.world_state = {}
        self.db.state_presentations = []

    def filter_visible(self, obj_list, looker, **kwargs):
        """Preserve Evennia visibility locks, then apply optional Siza world_state visibility gates."""
        visible = super().filter_visible(obj_list, looker, **kwargs)
        return [obj for obj in visible if object_visible_in_world_state(obj, site=self)]

    def return_appearance(self, looker, **kwargs):
        """Return only narrative prose.

        NPCs, objects and exits stay available through Room State packets and
        action buttons. They are not printed inside the observation text.
        """
        text = _description_only(getattr(self.db, "desc", ""))
        return text or "Este lugar todavía no tiene descripción narrativa importada desde el Map Editor."
