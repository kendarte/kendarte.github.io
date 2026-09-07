"""Authoritative persistent PLAYER transform shared by every account.

The transform is stored in Evennia ServerConfig, therefore it lives in the
persistent Evennia database on Railway and survives browser reloads, account
changes and service restarts. Character sprites remain character-owned; only
PLAYER scene transform/anchor state is global.
"""

import json

from evennia.server.models import ServerConfig


GLOBAL_PLAYER_VISUAL_CONFIG = "pokerol_global_player_visual_state_v1"
DEFAULT_PLAYER_VISUAL = {
    "x": 11.0,
    "y": 94.0,
    "scale": 1.0,
    "anchored": False,
    "revision": 0,
}


def _number(value, default, minimum, maximum):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)
    return max(float(minimum), min(float(maximum), value))


def _revision(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _normalize(raw):
    row = dict(raw or {}) if isinstance(raw, dict) else {}
    return {
        "x": _number(row.get("x"), 11, 1, 99),
        "y": _number(row.get("y"), 94, 0, 500),
        "scale": _number(row.get("scale"), 1, 0.35, 3),
        "anchored": bool(row.get("anchored", False)),
        "revision": _revision(row.get("revision")),
        "updated_by": str(row.get("updated_by") or ""),
        "updated_by_dbref": _revision(row.get("updated_by_dbref")),
        "scope": "GLOBAL_PLAYER_VISUAL_STATE",
    }


def _read_saved():
    try:
        raw = ServerConfig.objects.conf(GLOBAL_PLAYER_VISUAL_CONFIG, default="")
    except Exception:
        return None
    if isinstance(raw, dict):
        return _normalize(raw)
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return _normalize(parsed) if isinstance(parsed, dict) else None


def _write(state):
    normalized = _normalize(state)
    ServerConfig.objects.conf(
        GLOBAL_PLAYER_VISUAL_CONFIG,
        value=json.dumps(normalized, separators=(",", ":"), sort_keys=True),
    )
    return normalized


def _legacy_character_state(actor):
    """Return an existing real character edit for one-time migration, if any."""
    if actor is None:
        return None
    try:
        visual = getattr(actor.db, "pokerol_player_visual_state", None)
    except Exception:
        visual = None
    if not isinstance(visual, dict) or not visual:
        return None
    revision = _revision(visual.get("revision"))
    # Only migrate an actual saved edit. A missing/default character must not
    # become the global authority merely because it logged in first.
    if revision <= 0:
        return None
    try:
        anchored = bool(getattr(actor.db, "pokerol_player_anchor_enabled", False))
    except Exception:
        anchored = bool(visual.get("anchored", False))
    return _normalize({
        "x": visual.get("x", 11),
        "y": visual.get("y", 94),
        "scale": visual.get("scale", 1),
        "anchored": anchored,
        "revision": revision,
        "updated_by": getattr(actor, "key", ""),
        "updated_by_dbref": getattr(actor, "id", 0),
    })


def get_global_player_visual(actor=None, *, migrate_legacy=True):
    saved = _read_saved()
    if saved is not None:
        return saved
    if migrate_legacy:
        legacy = _legacy_character_state(actor)
        if legacy is not None:
            return _write(legacy)
    return _normalize(DEFAULT_PLAYER_VISUAL)


def save_global_player_visual(data, actor=None):
    previous = get_global_player_visual(None, migrate_legacy=False)
    row = dict(data or {})
    row["revision"] = max(_revision(previous.get("revision")), _revision(row.get("revision"))) + 1
    if actor is not None:
        row["updated_by"] = str(getattr(actor, "key", "") or "")
        row["updated_by_dbref"] = int(getattr(actor, "id", 0) or 0)
    return _write(row)
