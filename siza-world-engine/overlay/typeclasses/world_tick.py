from datetime import datetime, timezone

from evennia import DefaultScript, create_script, search_script

from services.job_claims import arbitrate_job_claims, refresh_job_claims
from services.job_engine import refresh_world_job_rules
from services.need_dynamics import advance_need_dynamics, apply_activity_need_dynamics
from services.npc_decision import decision_step
from services.npc_simulation import simulated_npcs, simstep
from services.shift_handoff import release_offshift_claims
from services.world_clock import advance_world_clock, ensure_world_clock, world_clock_state
from services.world_event_engine import refresh_world_event_rules


WORLD_TICK_KEY = "SIZA_WORLD_TICK"
WORLD_TICK_BUILD = "0.27.0-action-consequence-memory"
DEFAULT_INTERVAL = 30
MIN_INTERVAL = 5
MAX_INTERVAL = 3600
TRACE_LIMIT = 20


def simulate_npc_tick(npc):
    """Dispatch one NPC action using the world state already prepared for this tick."""
    if bool(npc.db.decision_enabled):
        result = dict(decision_step(npc, prepare_world_state=False) or {})
        result.setdefault("engine", "DECISION")
        return result

    result = dict(simstep(npc) or {})
    result.setdefault("engine", "ROUTINE_V04")
    return result


def _append_trace(
    script,
    tick_number,
    timestamp,
    world_clock_result,
    producer_results,
    event_results,
    handoff_results,
    arbitration_results,
    need_results,
    activity_need_results,
    results,
):
    """Persist a short rolling trace so autonomous state changes stay inspectable."""
    try:
        history = list(script.db.trace_history or [])
    except Exception:
        history = []

    history.append(
        {
            "tick": int(tick_number),
            "timestamp": timestamp,
            "world_clock_result": dict(world_clock_result or {}),
            "producer_results": list(producer_results or []),
            "event_results": list(event_results or []),
            "handoff_results": list(handoff_results or []),
            "arbitration_results": list(arbitration_results or []),
            "need_results": list(need_results or []),
            "activity_need_results": list(activity_need_results or []),
            "npc_results": list(results or []),
        }
    )
    script.db.trace_history = history[-TRACE_LIMIT:]


class SizaWorldTick(DefaultScript):
    """Persistent world tick with one global arbitration phase before NPC actions."""

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
        self.db.last_world_clock_result = {}
        self.db.last_producer_results = []
        self.db.last_event_results = []
        self.db.last_handoff_results = []
        self.db.last_arbitration_results = []
        self.db.last_need_results = []
        self.db.last_activity_need_results = []
        self.db.trace_history = []
        self.db.build = WORLD_TICK_BUILD
        ensure_world_clock(self)

    def at_repeat(self):
        if not bool(self.db.manual_enabled):
            return

        try:
            world_clock_result = advance_world_clock(self)
        except Exception as exc:
            world_clock_result = {
                "status": "ERROR",
                "error": str(exc),
            }

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

        try:
            event_results = refresh_world_event_rules()
        except Exception as exc:
            event_results = [
                {
                    "status": "ERROR",
                    "producer": "WORLD_EVENT_RULES",
                    "error": str(exc),
                }
            ]

        npcs = list(simulated_npcs())

        need_results = []
        for npc in npcs:
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
            handoff_results = release_offshift_claims()
        except Exception as exc:
            handoff_results = [
                {
                    "status": "ERROR",
                    "reason": "SHIFT_HANDOFF_ERROR",
                    "error": str(exc),
                }
            ]

        try:
            refresh_job_claims()
            arbitration_results = arbitrate_job_claims(npcs)
        except Exception as exc:
            arbitration_results = [
                {
                    "status": "ERROR",
                    "task_id": None,
                    "policy": None,
                    "winner_name": None,
                    "error": str(exc),
                }
            ]

        activity_need_results = []
        results = []
        for npc in npcs:
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
        self.db.last_world_clock_result = world_clock_result
        self.db.last_producer_results = producer_results
        self.db.last_event_results = event_results
        self.db.last_handoff_results = handoff_results
        self.db.last_arbitration_results = arbitration_results
        self.db.last_need_results = need_results
        self.db.last_activity_need_results = activity_need_results
        self.db.build = WORLD_TICK_BUILD
        _append_trace(
            self,
            tick_number=tick_number,
            timestamp=timestamp,
            world_clock_result=world_clock_result,
            producer_results=producer_results,
            event_results=event_results,
            handoff_results=handoff_results,
            arbitration_results=arbitration_results,
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
        script.db.last_world_clock_result = {}
        script.db.last_producer_results = []
        script.db.last_event_results = []
        script.db.last_handoff_results = []
        script.db.last_arbitration_results = []
        script.db.last_need_results = []
        script.db.last_activity_need_results = []
        script.db.trace_history = []
        ensure_world_clock(script)
        return script, True

    script.db.manual_enabled = True
    script.db.build = WORLD_TICK_BUILD
    if script.db.last_world_clock_result is None:
        script.db.last_world_clock_result = {}
    if script.db.last_producer_results is None:
        script.db.last_producer_results = []
    if script.db.last_event_results is None:
        script.db.last_event_results = []
    if script.db.last_handoff_results is None:
        script.db.last_handoff_results = []
    if script.db.last_arbitration_results is None:
        script.db.last_arbitration_results = []
    if script.db.last_need_results is None:
        script.db.last_need_results = []
    if script.db.last_activity_need_results is None:
        script.db.last_activity_need_results = []
    if script.db.trace_history is None:
        script.db.trace_history = []
    ensure_world_clock(script)
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
            "last_world_clock_result": {},
            "last_producer_results": [],
            "last_event_results": [],
            "last_handoff_results": [],
            "last_arbitration_results": [],
            "last_need_results": [],
            "last_activity_need_results": [],
            "trace_history": [],
            "next_repeat": None,
            "world_clock": world_clock_state(),
            "build": WORLD_TICK_BUILD,
        }

    try:
        next_repeat = script.time_until_next_repeat()
    except Exception:
        next_repeat = None

    ensure_world_clock(script)
    return {
        "exists": True,
        "enabled": bool(script.db.manual_enabled),
        "active": bool(script.is_active),
        "interval": int(script.interval or 0),
        "tick_count": int(script.db.tick_count or 0),
        "last_tick_at": script.db.last_tick_at,
        "last_results": list(script.db.last_results or []),
        "last_world_clock_result": dict(script.db.last_world_clock_result or {}),
        "last_producer_results": list(script.db.last_producer_results or []),
        "last_event_results": list(script.db.last_event_results or []),
        "last_handoff_results": list(script.db.last_handoff_results or []),
        "last_arbitration_results": list(script.db.last_arbitration_results or []),
        "last_need_results": list(script.db.last_need_results or []),
        "last_activity_need_results": list(script.db.last_activity_need_results or []),
        "trace_history": list(script.db.trace_history or []),
        "next_repeat": next_repeat,
        "world_clock": world_clock_state(script),
        "build": str(script.db.build or WORLD_TICK_BUILD),
    }
