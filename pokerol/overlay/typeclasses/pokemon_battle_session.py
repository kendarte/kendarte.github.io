"""Persistent shared multiplayer battle session for POKEROL.

A session is the single authority for one multiplayer battle. Characters only
store a session id; they never own independent copies of multiplayer state.
"""

from copy import deepcopy
from time import time
from uuid import uuid4

from evennia import DefaultScript


SESSION_BUILD = "0.1.0-shared-session-lobby"
SESSION_KINDS = {"PVE_COOP", "PVP", "RAID"}
SESSION_STATUSES = {"LOBBY", "ACTIVE", "COMPLETE", "ABANDONED"}
MAX_HUMAN_PARTICIPANTS = 8


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _text(value):
    return str(value or "").strip()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clone(value):
    return deepcopy(value)


def participant_id(actor):
    if not actor or getattr(actor, "id", None) is None:
        return ""
    return f"PLAYER:DBREF:{int(actor.id)}"


def participant_packet(actor, *, team="A", role="TRAINER", ready=False, joined_at=None):
    return {
        "participant_id": participant_id(actor),
        "actor_dbref": int(actor.id),
        "name": _text(getattr(actor, "key", "")) or f"Jugador {int(actor.id)}",
        "team": _text(team).upper() or "A",
        "role": _text(role).upper() or "TRAINER",
        "ready": bool(ready),
        "connected": True,
        "joined_at": int(joined_at or time()),
        "submitted_turn": 0,
        "active_entity_id": "",
    }


class PokemonBattleSession(DefaultScript):
    """Central persistent authority for one multiplayer Pokémon battle."""

    def at_script_creation(self):
        self.key = f"POKEROL-BATTLE-SESSION-{uuid4().hex[:10].upper()}"
        self.desc = "POKEROL shared multiplayer battle session"
        self.persistent = True
        self.interval = 0
        self.start_delay = False
        now = int(time())
        self.db.session_id = f"PKMS-{uuid4().hex[:14].upper()}"
        self.db.kind = "PVE_COOP"
        self.db.status = "LOBBY"
        self.db.room_dbref = None
        self.db.room_id = ""
        self.db.host_dbref = None
        self.db.participants = []
        self.db.invitations = []
        self.db.combatants = []
        self.db.pending_orders = {}
        self.db.turn = 1
        self.db.phase = "LOBBY"
        self.db.log = []
        self.db.created_at = now
        self.db.updated_at = now
        self.db.started_at = None
        self.db.completed_at = None
        self.db.winning_team = ""
        self.db.multi_target_pipeline = False
        self.db.build = SESSION_BUILD

    def snapshot(self):
        return {
            "build": SESSION_BUILD,
            "session_id": _text(self.db.session_id),
            "kind": _text(self.db.kind).upper(),
            "status": _text(self.db.status).upper(),
            "room_dbref": self.db.room_dbref,
            "room_id": _text(self.db.room_id),
            "host_dbref": self.db.host_dbref,
            "participants": _clone(_list(self.db.participants)),
            "invitations": _clone(_list(self.db.invitations)),
            "combatants": _clone(_list(self.db.combatants)),
            "pending_orders": _clone(_dict(self.db.pending_orders)),
            "turn": max(1, _int(self.db.turn, 1)),
            "phase": _text(self.db.phase).upper() or "LOBBY",
            "log": _clone(_list(self.db.log)),
            "created_at": self.db.created_at,
            "updated_at": self.db.updated_at,
            "started_at": self.db.started_at,
            "completed_at": self.db.completed_at,
            "winning_team": _text(self.db.winning_team).upper(),
            "multi_target_pipeline": bool(self.db.multi_target_pipeline),
        }

    def write_participants(self, rows):
        self.db.participants = _clone(_list(rows))
        self.db.updated_at = int(time())

    def write_combatants(self, rows):
        self.db.combatants = _clone(_list(rows))
        self.db.updated_at = int(time())

    def write_orders(self, rows):
        self.db.pending_orders = _clone(_dict(rows))
        self.db.updated_at = int(time())

    def append_log(self, kind, text, **extra):
        rows = _list(self.db.log)
        row = {
            "turn": max(1, _int(self.db.turn, 1)),
            "phase": _text(self.db.phase).upper(),
            "kind": _text(kind).upper() or "SESSION",
            "text": _text(text) or "Evento de sesión.",
        }
        row.update({key: value for key, value in extra.items() if value is not None})
        rows.append(row)
        self.db.log = rows[-160:]
        self.db.updated_at = int(time())
        return _clone(row)
