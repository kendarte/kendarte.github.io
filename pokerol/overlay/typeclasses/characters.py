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
        self.db.discovered_facts = []
        self.db.current_action = None
        self.db.destination_id = None

    def _emit_siza_room_snapshot(self):
        """Send the current room state to the Siza book UI without depending on text look parsing."""
        try:
            from commands.siza_ui_runtime_commands import emit_room_snapshot

            emit_room_snapshot(self)
        except Exception:
            # Never break puppet/movement because the presentation bridge failed.
            return None
        return None

    def at_post_puppet(self, **kwargs):
        """Refresh the book UI immediately after entering a character."""
        try:
            super().at_post_puppet(**kwargs)
        except TypeError:
            super().at_post_puppet()
        self._emit_siza_room_snapshot()

    def at_post_move(self, source_location, move_type="move", **kwargs):
        """Publish completed player traversal from Evennia's canonical movement hook."""
        super().at_post_move(source_location, move_type=move_type, **kwargs)
        destination = getattr(self, "location", None)
        if not source_location or not destination:
            self._emit_siza_room_snapshot()
            return
        if source_location is destination:
            self._emit_siza_room_snapshot()
            return

        from services.dm_campaign_registry import observe_active_campaign_evidence

        exit_obj = kwargs.get("exit_obj")
        if str(move_type or "").lower() == "traverse":
            observe_active_campaign_evidence(
                self,
                {
                    "authority": "WORLD_ENGINE",
                    "source": "CHARACTER_TRAVERSAL",
                    "action_types": ["MOVEMENT_EXECUTED"],
                    "result": {
                        "exit_dbref": int(exit_obj.id)
                        if exit_obj and getattr(exit_obj, "id", None) is not None
                        else None,
                        "exit_id": str(getattr(getattr(exit_obj, "db", None), "exit_id", "") or "")
                        if exit_obj
                        else None,
                        "exit_key": str(getattr(exit_obj, "key", "") or "") if exit_obj else None,
                        "origin_dbref": int(source_location.id)
                        if getattr(source_location, "id", None) is not None
                        else None,
                        "origin_room_id": str(getattr(source_location.db, "room_id", "") or "") or None,
                        "destination_dbref": int(destination.id)
                        if getattr(destination, "id", None) is not None
                        else None,
                        "destination_room_id": str(getattr(destination.db, "room_id", "") or "") or None,
                    },
                },
            )
        self._emit_siza_room_snapshot()
