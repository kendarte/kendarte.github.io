from evennia import DefaultExit

from services.ollama_narrator import narrate_move_async


class Exit(DefaultExit):
    """Persistent Siza Exit. Geometry and door state are authoritative here."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.exit_id = None
        self.db.door_state = "open"
        self.db.is_locked = False
        self.db.hidden = False
        self.db.canon_status = "prototype"

    def at_traverse(self, traversing_object, target_location, **kwargs):
        if self.db.is_locked or self.db.door_state == "locked":
            traversing_object.msg("El paso esta bloqueado.")
            return False
        if self.db.door_state == "closed":
            traversing_object.msg("La puerta esta cerrada.")
            return False
        return super().at_traverse(traversing_object, target_location, **kwargs)

    def at_post_traverse(self, traversing_object, source_location, **kwargs):
        super().at_post_traverse(traversing_object, source_location, **kwargs)
        if traversing_object.db.siza_narration:
            narrate_move_async(
                traversing_object,
                source_location,
                self.destination,
                self,
            )
