from evennia import Command

from services.world_clock import (
    advance_world_clock,
    format_world_time,
    parse_hhmm,
    set_world_rate,
    set_world_time,
    world_clock_state,
)


class CmdSizaTime(Command):
    """Inspect the persistent prototype world clock."""

    key = "siza-time"
    aliases = ["world-time"]
    locks = "cmd:all()"

    def func(self):
        state = world_clock_state()
        self.caller.msg("=== SIZA WORLD CLOCK ===")
        self.caller.msg(
            f"{format_world_time(state.get('day'), state.get('minute'))} | "
            f"rate={state.get('minutes_per_tick')} world-min/tick | build={state.get('build')}"
        )
        self.caller.msg("Calendario: prototype técnico; day es un índice entero, sin nombres de lore.")
        self.caller.msg("========================")


class CmdSizaTimeSet(Command):
    """Admin/debug: set prototype world day and HH:MM without advancing simulation."""

    key = "siza-timeset"
    aliases = ["world-timeset"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 2:
            self.caller.msg("Uso: siza-timeset <day> <HH:MM>")
            return
        try:
            day = int(parts[0])
        except ValueError:
            self.caller.msg("day debe ser un entero >= 0.")
            return
        if day < 0:
            self.caller.msg("day debe ser un entero >= 0.")
            return
        minute = parse_hhmm(parts[1])
        if minute is None:
            self.caller.msg("Hora inválida. Use HH:MM en formato 24h.")
            return
        state = set_world_time(day, minute)
        if not state:
            self.caller.msg("No existe SIZA_WORLD_TICK; inicie el simulador al menos una vez.")
            return
        self.caller.msg(
            f"World clock fijado: {format_world_time(state.get('day'), state.get('minute'))} | "
            f"rate={state.get('minutes_per_tick')} world-min/tick."
        )


class CmdSizaTimeRate(Command):
    """Admin/debug: set how many world minutes pass per World Tick."""

    key = "siza-time-rate"
    aliases = ["world-time-rate"]
    locks = "cmd:perm(Admin)"

    def func(self):
        raw = (self.args or "").strip()
        try:
            minutes = int(raw)
        except ValueError:
            self.caller.msg("Uso: siza-time-rate <1-1440>")
            return
        if minutes < 1 or minutes > 1440:
            self.caller.msg("La tasa debe estar entre 1 y 1440 minutos de mundo por tick.")
            return
        state = set_world_rate(minutes)
        if not state:
            self.caller.msg("No existe SIZA_WORLD_TICK; inicie el simulador al menos una vez.")
            return
        self.caller.msg(f"World clock rate={state.get('minutes_per_tick')} world-min/tick.")


class CmdSizaTimeAdvance(Command):
    """Admin/debug: advance the world clock without executing producers or NPCs."""

    key = "siza-time-advance"
    aliases = ["world-time-advance"]
    locks = "cmd:perm(Admin)"

    def func(self):
        raw = (self.args or "").strip()
        try:
            minutes = int(raw)
        except ValueError:
            self.caller.msg("Uso: siza-time-advance <minutes>=0+")
            return
        if minutes < 0:
            self.caller.msg("minutes debe ser >= 0.")
            return
        packet = advance_world_clock(minutes=minutes)
        if packet.get("status") != "ADVANCED":
            self.caller.msg("No existe SIZA_WORLD_TICK; inicie el simulador al menos una vez.")
            return
        self.caller.msg(
            f"World clock: {format_world_time(packet.get('before_day'), packet.get('before_minute'))} "
            f"-> {format_world_time(packet.get('after_day'), packet.get('after_minute'))} "
            f"(+{packet.get('minutes_added')}m)."
        )
