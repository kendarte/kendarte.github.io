from evennia import Command

from services.pokerol_event_editor_service import get_room_event
from services.pokerol_room_event_runtime import (
    complete_room_event,
    process_room_event_trigger,
    runtime_event_packet,
    snooze_room_event,
    start_room_event,
)


def _text(value):
    return str(value or "").strip()


def _refresh(actor):
    try:
        from commands.pokerol_ui_runtime_commands import emit_room_snapshot
        emit_room_snapshot(actor, visible_text=False)
    except Exception:
        pass


class CmdPokerolRoomEvent(Command):
    key = "pokerol-room-event"
    aliases = ["evento-room"]
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        raw = _text(self.args)
        if not raw:
            packet = runtime_event_packet(self.caller)
            self.caller.msg("ROOM EVENTS: {}".format(packet.get("events") or []))
            return
        parts = raw.split(None, 1)
        mode = parts[0].lower()
        event_id = _text(parts[1]) if len(parts) > 1 else ""

        if mode == "sync":
            packet = runtime_event_packet(self.caller)
            self.caller.msg(pokerol_room_event_state=((packet,), {}))
            return

        if not event_id:
            self.caller.msg("Falta el id del evento.")
            return

        if mode == "snooze":
            result = snooze_room_event(self.caller, event_id)
        elif mode == "complete":
            result = complete_room_event(self.caller, event_id, reason="PLAYER_ACK")
        elif mode in {"start", "trigger"}:
            room = getattr(self.caller, "location", None)
            event = get_room_event(room, event_id) if room else None
            if not event:
                result = {"accepted": False, "status": "ROOM_EVENT_NOT_FOUND", "event_id": event_id}
            else:
                # Editor/manual testing uses the event's authored trigger itself;
                # this never bypasses its start conditions or chance gate.
                result = start_room_event(
                    self.caller,
                    event,
                    trigger=_text(event.get("trigger")).upper() or "MANUAL",
                    trigger_target=_text(event.get("trigger_target")),
                    trigger_token="COMMAND",
                )
        else:
            self.caller.msg("Uso: pokerol-room-event <start|snooze|complete|sync> [EVENT_ID]")
            return

        if not result.get("accepted"):
            self.caller.msg("Evento: {}.".format(result.get("status")))
        _refresh(self.caller)


class CmdPokerolRoomEventTrigger(Command):
    key = "pokerol-room-event-trigger"
    aliases = ()
    locks = "cmd:perm(Admin)"
    help_category = "POKEROL"

    def func(self):
        trigger = _text(self.args).upper() or "MANUAL"
        results = process_room_event_trigger(self.caller, trigger, trigger_token="ADMIN")
        self.caller.msg("EVENT TRIGGER {}: {}".format(trigger, [row.get("status") for row in results]))
        _refresh(self.caller)
