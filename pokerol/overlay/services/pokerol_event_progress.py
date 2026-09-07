"""Persistent per-character lifecycle for story and room events.

This is deliberately independent from any specific event handler.  Events can be
pending, active, snoozed or completed.  "Snoozed" never consumes the event;
completion is the only terminal state for one-shot/per-character events.
"""

from copy import deepcopy
from datetime import datetime, timezone


EVENT_PROGRESS_BUILD = "0.1.0-event-lifecycle"
EVENT_PROGRESS_ATTR = "pokerol_event_progress"
VALID_STATUS = {"PENDING", "ACTIVE", "SNOOZED", "COMPLETED"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _text(value, limit=None):
    value = str(value or "").strip()
    return value[:limit] if limit else value


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _progress_map(actor):
    if not actor:
        return {}
    return {
        str(key): dict(value or {})
        for key, value in _dict(getattr(actor.db, EVENT_PROGRESS_ATTR, {})).items()
        if str(key).strip()
    }


def _write_map(actor, rows):
    if actor:
        setattr(actor.db, EVENT_PROGRESS_ATTR, deepcopy(rows or {}))


def event_progress(actor, event_id):
    event_id = _text(event_id, 120)
    row = _dict(_progress_map(actor).get(event_id))
    status = _text(row.get("status")).upper() or "PENDING"
    if status not in VALID_STATUS:
        status = "PENDING"
    return {
        "event_id": event_id,
        "status": status,
        "stage": _text(row.get("stage"), 96),
        "started_at": _text(row.get("started_at"), 64),
        "updated_at": _text(row.get("updated_at"), 64),
        "snoozed_at": _text(row.get("snoozed_at"), 64),
        "completed_at": _text(row.get("completed_at"), 64),
        "snooze_count": max(0, int(row.get("snooze_count", 0) or 0)),
        "completion_reason": _text(row.get("completion_reason"), 160),
        "facts": _dict(row.get("facts")),
        "build": EVENT_PROGRESS_BUILD,
    }


def _mutate(actor, event_id, *, status=None, stage=None, facts=None, reason=None):
    event_id = _text(event_id, 120)
    if not actor or not event_id:
        return event_progress(actor, event_id)
    rows = _progress_map(actor)
    current = event_progress(actor, event_id)
    now = _now()
    next_row = dict(current)
    if status:
        normalized = _text(status).upper()
        if normalized in VALID_STATUS:
            next_row["status"] = normalized
    if stage is not None:
        next_row["stage"] = _text(stage, 96)
    if facts:
        merged = _dict(next_row.get("facts"))
        merged.update(deepcopy(_dict(facts)))
        next_row["facts"] = merged
    if reason is not None:
        next_row["completion_reason"] = _text(reason, 160)
    if next_row["status"] == "ACTIVE" and not next_row.get("started_at"):
        next_row["started_at"] = now
    if next_row["status"] == "SNOOZED":
        next_row["snoozed_at"] = now
        next_row["snooze_count"] = max(0, int(current.get("snooze_count", 0) or 0)) + 1
    if next_row["status"] == "COMPLETED":
        next_row["completed_at"] = next_row.get("completed_at") or now
    next_row["updated_at"] = now
    next_row.pop("build", None)
    rows[event_id] = next_row
    _write_map(actor, rows)
    return event_progress(actor, event_id)


def mark_event_active(actor, event_id, *, stage="", facts=None):
    current = event_progress(actor, event_id)
    if current.get("status") == "COMPLETED":
        return current
    return _mutate(actor, event_id, status="ACTIVE", stage=stage, facts=facts)


def snooze_event(actor, event_id, *, stage="", facts=None):
    current = event_progress(actor, event_id)
    if current.get("status") == "COMPLETED":
        return current
    return _mutate(actor, event_id, status="SNOOZED", stage=stage or current.get("stage"), facts=facts)


def complete_event(actor, event_id, *, stage="COMPLETE", reason="", facts=None):
    return _mutate(actor, event_id, status="COMPLETED", stage=stage, facts=facts, reason=reason)


def event_is_completed(actor, event_id):
    return event_progress(actor, event_id).get("status") == "COMPLETED"
