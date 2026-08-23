from datetime import datetime, timezone

from evennia import DefaultScript, create_script, search_script

from services.npc_decision import decision_step
from services.npc_simulation import simulated_npcs, simstep


WORLD_TICK_KEY = "SIZA_WORLD_TICK"
WORLD_TICK_BUILD = "0.7.0-world-job"
DEFAULT_INTERVAL = 30
MIN_INTERVAL = 5
MAX_INTERVAL = 3600


def simulate_npc_tick(npc):
    """Dispatch one NPC tick without changing unapproved NPC behavior."""
    if bool(npc.db.decision_enabled):
        result = dict(decision_step(npc) or {})
        result.setdefault("engine", "DECISION")
        return result

    result = dict(simstep(npc) or {})
    result.setdefault("engine", "ROUTINE_V04")
    return result


class SizaWorldTick(DefaultScript):
    """Persistent global world tick for Siza NPC simulation."""

    def at_script_creation(self):
        self.key = WORLD_TICK_KEY
        self.desc = "Persistent Siza world simulation tick."
        self.interval = DEFAULT_INTERVAL
        self.start_delay = True
        self.repeats = 0
        self.persistent = True
        self.db.manual_enabled = True
        self.db.tick_count = 0
        self.db.last_tick_at = None
        self.db.last_results = []
        self.db.build = WORLD_TICK_BUILD

    def at_repeat(self):
        if not bool(self.db.manual_enabled):
            return

        results = []
        for npc in simulated_npcs():
            try:
                result = simulate_npc_tick(npc)
            except Exception as exc:
                result = {
                    "status": "ERROR",
                    "npc": getattr(npc, "key", "UNKNOWN"),
                    "engine": "ERROR",
                    "error": str(exc),
                }
            results.append(result)

        self.db.tick_count = int(self.db.tick_count or 0) + 1
        self.db.last_tick_at = datetime.now(timezone.utc).isoformat()
        self.db.last_results = results
        self.db.build = WORLD_TICK_BUILD


def get_world_tick():
    matches = list(search_script(WORLD_TICK_KEY))
    return matches[0] if matches else None


def clamp_interval(value):
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = DEFAULT_INTERVAL
    return max(MIN_INTERVAL, min(MAX_INTERVAL, seconds))


def start_world_tick(interval=DEFAULT_INTERVAL):
    seconds = clamp_interval(interval)
    script = get_world_tick()

    if script is None:
        script = create_script(
            "typeclasses.world_tick.SizaWorldTick",
            key=WORLD_TICK_KEY,
            interval=seconds,
            start_delay=True,
            repeats=0,
            persistent=True,
            autostart=True,
        )
        script.db.manual_enabled = True
        script.db.build = WORLD_TICK_BUILD
        return script, True

    script.db.manual_enabled = True
    script.db.build = WORLD_TICK_BUILD
    script.start(interval=seconds, start_delay=seconds, repeats=0)
    return script, False


def pause_world_tick():
    script = get_world_tick()
    if script is None:
        return None
    script.db.manual_enabled = False
    script.pause()
    return script


def world_tick_state():
    script = get_world_tick()
    if script is None:
        return {
            "exists": False,
            "enabled": False,
            "active": False,
            "interval": None,
            "tick_count": 0,
            "last_tick_at": None,
            "last_results": [],
            "next_repeat": None,
            "build": WORLD_TICK_BUILD,
        }

    try:
        next_repeat = script.time_until_next_repeat()
    except Exception:
        next_repeat = None

    return {
        "exists": True,
        "enabled": bool(script.db.manual_enabled),
        "active": bool(script.is_active),
        "interval": int(script.interval or 0),
        "tick_count": int(script.db.tick_count or 0),
        "last_tick_at": script.db.last_tick_at,
        "last_results": list(script.db.last_results or []),
        "next_repeat": next_repeat,
        "build": str(script.db.build or WORLD_TICK_BUILD),
    }
