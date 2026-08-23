from evennia import search_script


WORLD_CLOCK_BUILD = "0.16.0-world-clock-schedules"
WORLD_TICK_KEY = "SIZA_WORLD_TICK"
DEFAULT_DAY = 0
DEFAULT_MINUTE = 8 * 60
DEFAULT_MINUTES_PER_TICK = 10
MIN_RATE = 1
MAX_RATE = 1440


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _world_tick_script():
    matches = list(search_script(WORLD_TICK_KEY))
    return matches[0] if matches else None


def ensure_world_clock(script=None):
    script = script or _world_tick_script()
    if script is None:
        return None

    if script.db.world_day is None:
        script.db.world_day = DEFAULT_DAY
    if script.db.world_minute is None:
        script.db.world_minute = DEFAULT_MINUTE
    if script.db.world_minutes_per_tick is None:
        script.db.world_minutes_per_tick = DEFAULT_MINUTES_PER_TICK

    day = max(0, _to_int(script.db.world_day, DEFAULT_DAY))
    minute = _to_int(script.db.world_minute, DEFAULT_MINUTE) % 1440
    rate = max(MIN_RATE, min(MAX_RATE, _to_int(script.db.world_minutes_per_tick, DEFAULT_MINUTES_PER_TICK)))

    script.db.world_day = day
    script.db.world_minute = minute
    script.db.world_minutes_per_tick = rate
    return script


def format_minute(minute):
    minute = _to_int(minute, 0) % 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def format_world_time(day, minute):
    return f"day {max(0, _to_int(day, 0))} {format_minute(minute)}"


def parse_hhmm(text):
    raw = str(text or "").strip()
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except (TypeError, ValueError):
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def world_clock_state(script=None):
    script = ensure_world_clock(script)
    if script is None:
        return {
            "exists": False,
            "day": DEFAULT_DAY,
            "minute": DEFAULT_MINUTE,
            "time": format_minute(DEFAULT_MINUTE),
            "minutes_per_tick": DEFAULT_MINUTES_PER_TICK,
            "build": WORLD_CLOCK_BUILD,
        }

    day = _to_int(script.db.world_day, DEFAULT_DAY)
    minute = _to_int(script.db.world_minute, DEFAULT_MINUTE) % 1440
    rate = _to_int(script.db.world_minutes_per_tick, DEFAULT_MINUTES_PER_TICK)
    return {
        "exists": True,
        "day": day,
        "minute": minute,
        "time": format_minute(minute),
        "minutes_per_tick": rate,
        "build": WORLD_CLOCK_BUILD,
    }


def set_world_time(day, minute, script=None):
    script = ensure_world_clock(script)
    if script is None:
        return None
    script.db.world_day = max(0, _to_int(day, DEFAULT_DAY))
    script.db.world_minute = _to_int(minute, DEFAULT_MINUTE) % 1440
    return world_clock_state(script)


def set_world_rate(minutes_per_tick, script=None):
    script = ensure_world_clock(script)
    if script is None:
        return None
    rate = max(MIN_RATE, min(MAX_RATE, _to_int(minutes_per_tick, DEFAULT_MINUTES_PER_TICK)))
    script.db.world_minutes_per_tick = rate
    return world_clock_state(script)


def advance_world_clock(script=None, minutes=None):
    script = ensure_world_clock(script)
    if script is None:
        return {"status": "NO_CLOCK", "build": WORLD_CLOCK_BUILD}

    before_day = _to_int(script.db.world_day, DEFAULT_DAY)
    before_minute = _to_int(script.db.world_minute, DEFAULT_MINUTE) % 1440
    delta = _to_int(minutes, script.db.world_minutes_per_tick) if minutes is not None else _to_int(
        script.db.world_minutes_per_tick, DEFAULT_MINUTES_PER_TICK
    )
    delta = max(0, delta)

    total = before_day * 1440 + before_minute + delta
    after_day = total // 1440
    after_minute = total % 1440
    script.db.world_day = after_day
    script.db.world_minute = after_minute

    return {
        "status": "ADVANCED",
        "before_day": before_day,
        "before_minute": before_minute,
        "before_time": format_minute(before_minute),
        "after_day": after_day,
        "after_minute": after_minute,
        "after_time": format_minute(after_minute),
        "minutes_added": delta,
        "build": WORLD_CLOCK_BUILD,
    }


def schedule_is_active(schedule, state=None):
    if not schedule:
        return True
    try:
        schedule = dict(schedule)
    except Exception:
        return True

    if not bool(schedule.get("enabled", True)):
        return True

    state = state or world_clock_state()
    day = _to_int(state.get("day"), DEFAULT_DAY)
    minute = _to_int(state.get("minute"), DEFAULT_MINUTE) % 1440

    days = schedule.get("days")
    if days:
        try:
            allowed_days = {int(value) for value in list(days)}
        except Exception:
            allowed_days = set()
        if allowed_days and day not in allowed_days:
            return False

    start = _to_int(schedule.get("start_minute"), 0) % 1440
    end = _to_int(schedule.get("end_minute"), 0) % 1440

    if start == end:
        return True
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def schedule_label(schedule):
    if not schedule:
        return "ALWAYS"
    try:
        schedule = dict(schedule)
    except Exception:
        return "ALWAYS"
    if not bool(schedule.get("enabled", True)):
        return "ALWAYS"
    start = _to_int(schedule.get("start_minute"), 0) % 1440
    end = _to_int(schedule.get("end_minute"), 0) % 1440
    return f"{format_minute(start)}-{format_minute(end)}"
