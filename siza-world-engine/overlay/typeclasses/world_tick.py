from datetime import datetime, timezone

from evennia import DefaultScript, create_script, search_script

from services.job_engine import refresh_world_job_rules
from services.need_dynamics import advance_need_dynamics, apply_activity_need_dynamics
from services.npc_decision import decision_step
from services.npc_simulation import simulated_npcs, simstep


WORLD_TICK_KEY = "SIZA_WORLD_TICK"
WORLD_TICK_BUILD = "0.11.0-activity-needs"
DEFAULT_INTERVAL = 30
MIN_INTERVAL = 5
MAX_INTERVAL = 3600
TRACE_LIMIT = 20


def simulate_npc_tick(npc):
    """Dispatch one NPC tick without changing unapproved NPC behavior."""
    if bool(npc.db.decision_enabled):
        result = dict(decision_step(npc) or {})
        result.setdefault("engine", "DECISION")
        return result

    result = dict(simstep(npc) or {})
    result.setdefault("engine", "ROUTINE_V04")
    return result


def _append_trace(
    script,
    tick_number,
    timestamp,
    producer_results,
    need_results,
    activity_need_results,
    results,
):
    """Persist a short rolling trace so transient autonomous decisions stay inspectable."""
    try:
        history = list(script.db.trace_history or [])
    except Exception:
        history = []

    history.append(
        {
            "tick": int(tick_number),
            "timestamp": timestamp,
            "producer_results": list(producer_results or []),
            "need_results": list(need_results or []),
            "activity_need_results": list(activity_need_results or []),
            "npc_results": list(results or []),
        }
    )
    script.db.trace_history = history[-TRACE_LIMIT:]


class SizaWorldTick(DefaultScript):
    """Persistent global world tick for world producers, needs and NPC simulation."""

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
        self.db.last_producer_results = []
        self.db.last_need_results = []
        self.db.last_activity_need_results = []
        self.db.trace_history = []
        self.db.build = WORLD_TICK_BUILD

    def at_repeat(self):
        if not bool(self.db.manual_enabled):
            return

        try:
            producer_results = refresh_world_job_rules()
        except Exception as exc:
            producer_results = [
                {
                    "status": "ERROR",
                    "producer": "WORLD_JOB_RULES",
                    "error": str(exc),
                }
            ]

        need_results = []
        activity_need_results = []
        results = []
        for npc in simulated_npcs():
            try:
                need_result = advance_need_dynamics(npc)
            except Exception as exc:
                need_result = {
                    "npc": getattr(npc, "key", "UNKNOWN"),
                    "clock": None,
                    "changes": [],
                    "error": str(exc),
                }
            need_results.append(need_result)

            try:
                result = simulate_npc_tick(npc)
            except Exception as exc:
                result = {
                    "status": "ERROR",
                    "npc": getattr(npc, "key", "UNKNOWN"),
                    "engine": "ERROR",
                    "action_kind": "IDLE",
                    "error": str(exc),
                }
            results.append(result)

            try:
                activity_result = apply_activity_need_dynamics(
                    npc, result.get("action_kind") or "IDLE"
                )
            except Exception as exc:
                activity_result = {
                    "npc": getattr(npc, "key", "UNKNOWN"),
                    "activity_kind": result.get("action_kind") or "IDLE",
                    "changes": [],
                    "counters": {},
                    "error": str(exc),
                }
            activity_need_results.append(activity_result)

        tick_number = int(self.db.tick_count or 0) + 1
        timestamp = datetime.now(timezone.utc).isoformat()
        self.db.tick_count = tick_number
        self.db.last_tick_at = timestamp
        self.db.last_results = results
        self.db.last_producer_results = producer_results
        self.db.last_need_results = need_results
        self.db.last_activity_need_results = activity_need_results
        self.db.build = WORLD_TICK_BUILD
        _append_trace(
            self,
            tick_number=tick_number,
            timestamp=timestamp,
            producer_results=producer_results,
            need_results=need_results,
            activity_need_results=activity_need_results,
            results=results,
        )


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
        script.db.last_producer_results = []
        script.db.last_need_results = []
        script.db.last_activity_need_results = []
        script.db.trace_history = []
        return script, True

    script.db.manual_enabled = True
    script.db.build = WORLD_TICK_BUILD
    if script.db.last_producer_results is None:
        script.db.last_producer_results = []
    if script.db.last_need_results is None:
        script.db.last_need_results = []
    if script.db.last_activity_need_results is None:
        script.db.last_activity_need_results = []
    if script.db.trace_history is None:
        script.db.trace_history = []
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
            "last_producer_results": [],
            "last_need_results": [],
            "last_activity_need_results": [],
            "trace_history": [],
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
        "last_producer_results": list(script.db.last_producer_results or []),
        "last_need_results": list(script.db.last_need_results or []),
        "last_activity_need_results": list(script.db.last_activity_need_results or []),
        "trace_history": list(script.db.trace_history or []),
        "next_repeat": next_repeat,
        "build": str(script.db.build or WORLD_TICK_BUILD),
    }
