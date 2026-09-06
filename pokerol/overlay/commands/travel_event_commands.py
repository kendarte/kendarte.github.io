from evennia import Command

from services.travel_event_engine import TRAVEL_EVENT_BUILD, resolve_pending_travel_event


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


class CmdPokerolTravelEvent(Command):
    key = "evento"
    aliases = ["evento-viaje", "travel-event"]
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        pending = _dict(getattr(self.caller.db, "pending_travel_event", {}))
        last_roll = _dict(getattr(self.caller.db, "last_travel_event_roll", {}))
        self.caller.msg(f"=== POKEROL TRAVEL EVENT | {TRAVEL_EVENT_BUILD} ===")
        if pending:
            self.caller.msg(
                f"ACTIVE {pending.get('travel_event_id')} | {pending.get('event_type')} | "
                f"{pending.get('title')} | room={pending.get('destination_room_id')}"
            )
            if pending.get("premise"):
                self.caller.msg(str(pending.get("premise")))
            wild = _dict(pending.get("wild_pokemon"))
            if wild.get("species_id"):
                self.caller.msg(
                    f"wild={wild.get('species_id')} | level={wild.get('level')} | "
                    f"behavior={wild.get('behavior')}"
                )
            self.caller.msg(f"stakes={pending.get('stakes') or []}")
        else:
            self.caller.msg("No hay evento de viaje activo.")
        if last_roll:
            self.caller.msg(
                f"last_roll={last_roll.get('roll')} / threshold={last_roll.get('threshold')} | "
                f"status={last_roll.get('status')} | room={last_roll.get('destination_room_id')}"
            )
        self.caller.msg("============================================")


class CmdPokerolResolveTravelEvent(Command):
    key = "resolver-evento"
    aliases = ["resolve-travel-event"]
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        raw = str(self.args or "").strip()
        if not raw:
            self.caller.msg("Uso: resolver-evento <resuelto|ayudado|capturado|derrotado|escapó|ignorado> [notas]")
            return
        parts = raw.split(None, 1)
        resolution = parts[0]
        notes = parts[1] if len(parts) > 1 else None
        packet = resolve_pending_travel_event(self.caller, resolution, notes=notes)
        if not packet.get("resolved"):
            self.caller.msg("No hay evento de viaje pendiente.")
            return
        event = _dict(packet.get("event"))
        self.caller.msg(
            f"Evento {event.get('travel_event_id')} resuelto como {event.get('resolution')}."
        )
