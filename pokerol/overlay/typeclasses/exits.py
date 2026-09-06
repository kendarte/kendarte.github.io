from evennia import DefaultExit, logger

from services.dm_campaign_registry import observe_active_campaign_evidence
from services.exit_state_gate_engine import inspect_exit_state
from services.ollama_narrator import narrate_move_async
from services.travel_encounter_bridge import activate_travel_event_encounter
from services.travel_event_engine import roll_travel_event


def _plain_string_list(value):
    try:
        rows = list(value or [])
    except Exception:
        rows = []
    output = []
    for raw in rows:
        item = str(raw or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def _emit_room_after_traverse(actor):
    try:
        from commands.siza_ui_runtime_commands import emit_room_snapshot

        emit_room_snapshot(actor, visible_text=False)
    except Exception:
        return None
    return None


class Exit(DefaultExit):
    """Persistent POKEROL Exit. Geometry and door state are authoritative here."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.exit_id = None
        self.db.door_state = "open"
        self.db.is_locked = False
        self.db.hidden = False
        self.db.canon_status = "prototype"
        self.db.state_requirements = []
        self.db.state_block_message = "El estado actual del lugar no permite usar ese paso."
        self.db.campaign_tags = []

    def at_traverse(self, traversing_object, target_location, **kwargs):
        state_check = inspect_exit_state(self)
        if not bool(state_check.get("eligible")):
            message = str(
                getattr(self.db, "state_block_message", "")
                or "El estado actual del lugar no permite usar ese paso."
            ).strip()
            traversing_object.msg(message)
            return False
        if self.db.is_locked or self.db.door_state == "locked":
            traversing_object.msg("El paso esta bloqueado.")
            return False
        if self.db.door_state == "closed":
            traversing_object.msg("La puerta esta cerrada.")
            return False
        return super().at_traverse(traversing_object, target_location, **kwargs)

    def at_post_traverse(self, traversing_object, source_location, **kwargs):
        super().at_post_traverse(traversing_object, source_location, **kwargs)
        destination = getattr(traversing_object, "location", None)
        campaign_tags = _plain_string_list(getattr(self.db, "campaign_tags", []))
        observe_active_campaign_evidence(
            traversing_object,
            {
                "authority": "WORLD_ENGINE",
                "source": "EXIT_TRAVERSAL",
                "action_types": ["MOVEMENT_EXECUTED"],
                "campaign_tags": campaign_tags,
                "result": {
                    "exit_dbref": int(self.id) if getattr(self, "id", None) is not None else None,
                    "exit_id": str(getattr(self.db, "exit_id", "") or "") or None,
                    "exit_key": str(self.key),
                    "origin_dbref": int(source_location.id)
                    if source_location and getattr(source_location, "id", None) is not None
                    else None,
                    "origin_room_id": str(getattr(getattr(source_location, "db", None), "room_id", "") or "")
                    if source_location
                    else None,
                    "destination_dbref": int(destination.id)
                    if destination and getattr(destination, "id", None) is not None
                    else None,
                    "destination_room_id": str(getattr(getattr(destination, "db", None), "room_id", "") or "")
                    if destination
                    else None,
                },
            },
        )
        _emit_room_after_traverse(traversing_object)
        if traversing_object.db.siza_narration:
            narrate_move_async(
                traversing_object,
                source_location,
                destination,
                self,
            )
        try:
            packet = roll_travel_event(
                traversing_object,
                source_location,
                destination,
                self,
            )
            traversing_object.db.last_travel_event_roll = packet
            activation = activate_travel_event_encounter(traversing_object, packet)
            traversing_object.db.last_travel_encounter_activation = activation
        except Exception as exc:
            logger.log_err(f"POKEROL travel event roll failed: {exc}")
