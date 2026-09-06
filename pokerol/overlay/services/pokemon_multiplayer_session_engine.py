"""Shared multiplayer battle-session authority for POKEROL."""

from copy import deepcopy
from time import time

import evennia

from services.pokemon_battle_engine import normalize_pokemon
from services.pokemon_party_engine import active_pokemon
from typeclasses.pokemon_battle_session import (
    MAX_HUMAN_PARTICIPANTS,
    SESSION_KINDS,
    participant_id,
    participant_packet,
)


MULTI_SESSION_BUILD = "0.2.0-lobby-combatant-start"
SESSION_TYPECLASS = "typeclasses.pokemon_battle_session.PokemonBattleSession"


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


def actor_from_dbref(dbref):
    try:
        matches = evennia.search_object(f"#{int(dbref)}")
    except Exception:
        return None
    return matches[0] if matches else None


def session_by_id(session_id):
    wanted = _text(session_id)
    if not wanted:
        return None
    try:
        rows = evennia.search_script(wanted)
    except Exception:
        rows = []
    for script in rows or []:
        if _text(getattr(script.db, "session_id", "")) == wanted:
            return script
    try:
        rows = evennia.search_script("POKEROL-BATTLE-SESSION", exact=False)
    except Exception:
        rows = []
    for script in rows or []:
        if _text(getattr(script.db, "session_id", "")) == wanted:
            return script
    return None


def session_for_actor(actor):
    if not actor:
        return None
    session_id = _text(getattr(actor.db, "pokerol_battle_session_id", ""))
    if not session_id:
        return None
    session = session_by_id(session_id)
    if not session:
        actor.db.pokerol_battle_session_id = None
        return None
    pid = participant_id(actor)
    if not any(_text(_dict(row).get("participant_id")) == pid for row in _list(session.db.participants)):
        actor.db.pokerol_battle_session_id = None
        return None
    return session


def _same_room(actor, session):
    room = getattr(actor, "location", None) if actor else None
    if not room or not session:
        return False
    return _int(getattr(room, "id", None), -1) == _int(getattr(session.db, "room_dbref", None), -2)


def _participant_index(session, actor):
    pid = participant_id(actor)
    for index, row in enumerate(_list(session.db.participants)):
        if _text(_dict(row).get("participant_id")) == pid:
            return index
    return -1


def _invitation_rows(actor):
    return [_dict(row) for row in _list(getattr(actor.db, "pokerol_battle_invites", [])) if _dict(row)] if actor else []


def _write_actor_invites(actor, rows):
    actor.db.pokerol_battle_invites = _clone(_list(rows))


def _clean_actor_invites(actor):
    if not actor:
        return []
    rows = []
    now = int(time())
    for row in _invitation_rows(actor):
        if now - _int(row.get("created_at"), now) > 3600:
            continue
        session = session_by_id(row.get("session_id"))
        if not session or _text(session.db.status).upper() != "LOBBY":
            continue
        rows.append(row)
    _write_actor_invites(actor, rows)
    return rows


def public_session(session, viewer=None):
    if not session:
        return {}
    packet = session.snapshot()
    packet["viewer_participant_id"] = participant_id(viewer) if viewer else ""
    packet["viewer_dbref"] = int(viewer.id) if viewer and getattr(viewer, "id", None) is not None else None
    packet["viewer_is_host"] = bool(viewer and _int(session.db.host_dbref, -1) == _int(viewer.id, -2))
    packet["build"] = MULTI_SESSION_BUILD
    return packet


def emit_session(session, *, event="STATE"):
    if not session:
        return 0
    sent = 0
    for row in _list(session.db.participants):
        actor = actor_from_dbref(_dict(row).get("actor_dbref"))
        if not actor:
            continue
        packet = public_session(session, actor)
        packet["event"] = _text(event).upper() or "STATE"
        actor.msg(pokerol_multiplayer_battle_state=((packet,), {"build": MULTI_SESSION_BUILD}))
        sent += 1
    return sent


def create_session(actor, kind="PVE_COOP"):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": MULTI_SESSION_BUILD}
    existing = session_for_actor(actor)
    if existing:
        return {"accepted": False, "status": "ALREADY_IN_BATTLE_SESSION", "session": public_session(existing, actor), "build": MULTI_SESSION_BUILD}
    old_battle = _dict(getattr(actor.db, "pokerol_pokemon_battle", {}))
    if _text(old_battle.get("status")).upper() == "ACTIVE":
        return {"accepted": False, "status": "SINGLE_BATTLE_ALREADY_ACTIVE", "build": MULTI_SESSION_BUILD}
    room = getattr(actor, "location", None)
    if not room:
        return {"accepted": False, "status": "NO_ROOM", "build": MULTI_SESSION_BUILD}
    if not active_pokemon(actor):
        return {"accepted": False, "status": "NO_ACTIVE_POKEMON", "build": MULTI_SESSION_BUILD}
    wanted = _text(kind).upper() or "PVE_COOP"
    if wanted not in SESSION_KINDS:
        return {"accepted": False, "status": "INVALID_SESSION_KIND", "kind": wanted, "build": MULTI_SESSION_BUILD}
    session = evennia.create_script(SESSION_TYPECLASS)
    session.db.kind = wanted
    session.db.room_dbref = int(room.id)
    session.db.room_id = _text(getattr(room.db, "room_id", ""))
    session.db.host_dbref = int(actor.id)
    session.db.participants = [participant_packet(actor, team="A", ready=False)]
    session.db.phase = "LOBBY"
    session.db.status = "LOBBY"
    session.append_log("SESSION_CREATED", f"{actor.key} crea una sesión {wanted}.", actor_dbref=int(actor.id))
    actor.db.pokerol_battle_session_id = _text(session.db.session_id)
    emit_session(session, event="CREATED")
    return {"accepted": True, "status": "SESSION_CREATED", "session": public_session(session, actor), "build": MULTI_SESSION_BUILD}


def invite_actor(host, target, *, team=""):
    session = session_for_actor(host)
    if not session:
        return {"accepted": False, "status": "NO_BATTLE_SESSION", "build": MULTI_SESSION_BUILD}
    if _int(session.db.host_dbref, -1) != _int(host.id, -2):
        return {"accepted": False, "status": "HOST_ONLY", "build": MULTI_SESSION_BUILD}
    if _text(session.db.status).upper() != "LOBBY":
        return {"accepted": False, "status": "SESSION_NOT_IN_LOBBY", "build": MULTI_SESSION_BUILD}
    if not target or target is host:
        return {"accepted": False, "status": "INVALID_INVITEE", "build": MULTI_SESSION_BUILD}
    if getattr(target, "location", None) is not getattr(host, "location", None):
        return {"accepted": False, "status": "INVITEE_NOT_IN_ROOM", "build": MULTI_SESSION_BUILD}
    if session_for_actor(target):
        return {"accepted": False, "status": "INVITEE_ALREADY_IN_SESSION", "build": MULTI_SESSION_BUILD}
    if len(_list(session.db.participants)) >= MAX_HUMAN_PARTICIPANTS:
        return {"accepted": False, "status": "SESSION_FULL", "build": MULTI_SESSION_BUILD}
    if not active_pokemon(target):
        return {"accepted": False, "status": "INVITEE_HAS_NO_ACTIVE_POKEMON", "build": MULTI_SESSION_BUILD}
    target_team = _text(team).upper()
    if target_team not in {"A", "B"}:
        target_team = "B" if _text(session.db.kind).upper() == "PVP" else "A"
    invitation = {
        "session_id": _text(session.db.session_id),
        "host_dbref": int(host.id),
        "host_name": _text(host.key),
        "room_dbref": int(host.location.id),
        "kind": _text(session.db.kind).upper(),
        "team": target_team,
        "created_at": int(time()),
    }
    session_invites = [_dict(row) for row in _list(session.db.invitations)]
    session_invites = [row for row in session_invites if _int(row.get("actor_dbref"), -1) != int(target.id)]
    session_invites.append({**_clone(invitation), "actor_dbref": int(target.id), "actor_name": _text(target.key)})
    session.db.invitations = session_invites
    actor_invites = _clean_actor_invites(target)
    actor_invites = [row for row in actor_invites if _text(row.get("session_id")) != _text(session.db.session_id)]
    actor_invites.append(_clone(invitation))
    _write_actor_invites(target, actor_invites)
    session.append_log("INVITED", f"{host.key} invita a {target.key}.", actor_dbref=int(target.id), team=target_team)
    target.msg(pokerol_multiplayer_battle_invite=((invitation,), {"build": MULTI_SESSION_BUILD}))
    emit_session(session, event="INVITE")
    return {"accepted": True, "status": "INVITED", "invitation": invitation, "session": public_session(session, host), "build": MULTI_SESSION_BUILD}


def accept_invitation(actor, session_id=""):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": MULTI_SESSION_BUILD}
    if session_for_actor(actor):
        return {"accepted": False, "status": "ALREADY_IN_BATTLE_SESSION", "build": MULTI_SESSION_BUILD}
    invitations = _clean_actor_invites(actor)
    wanted = _text(session_id)
    invitation = None
    for row in reversed(invitations):
        if not wanted or _text(row.get("session_id")) == wanted:
            invitation = row
            break
    if not invitation:
        return {"accepted": False, "status": "INVITATION_NOT_FOUND", "build": MULTI_SESSION_BUILD}
    session = session_by_id(invitation.get("session_id"))
    if not session or _text(session.db.status).upper() != "LOBBY":
        return {"accepted": False, "status": "SESSION_NOT_AVAILABLE", "build": MULTI_SESSION_BUILD}
    if not _same_room(actor, session):
        return {"accepted": False, "status": "NOT_IN_SESSION_ROOM", "build": MULTI_SESSION_BUILD}
    if len(_list(session.db.participants)) >= MAX_HUMAN_PARTICIPANTS:
        return {"accepted": False, "status": "SESSION_FULL", "build": MULTI_SESSION_BUILD}
    if not active_pokemon(actor):
        return {"accepted": False, "status": "NO_ACTIVE_POKEMON", "build": MULTI_SESSION_BUILD}
    team = _text(invitation.get("team")).upper() or "A"
    participants = _list(session.db.participants)
    participants.append(participant_packet(actor, team=team, ready=False))
    session.write_participants(participants)
    session.db.invitations = [row for row in _list(session.db.invitations) if _int(_dict(row).get("actor_dbref"), -1) != int(actor.id)]
    actor.db.pokerol_battle_session_id = _text(session.db.session_id)
    _write_actor_invites(actor, [row for row in invitations if _text(row.get("session_id")) != _text(session.db.session_id)])
    session.append_log("JOINED", f"{actor.key} entra a la sesión.", actor_dbref=int(actor.id), team=team)
    emit_session(session, event="JOINED")
    return {"accepted": True, "status": "JOINED", "session": public_session(session, actor), "build": MULTI_SESSION_BUILD}


def set_ready(actor, ready=True):
    session = session_for_actor(actor)
    if not session:
        return {"accepted": False, "status": "NO_BATTLE_SESSION", "build": MULTI_SESSION_BUILD}
    if _text(session.db.status).upper() != "LOBBY":
        return {"accepted": False, "status": "SESSION_NOT_IN_LOBBY", "build": MULTI_SESSION_BUILD}
    if not _same_room(actor, session):
        return {"accepted": False, "status": "NOT_IN_SESSION_ROOM", "build": MULTI_SESSION_BUILD}
    if not active_pokemon(actor):
        return {"accepted": False, "status": "NO_ACTIVE_POKEMON", "build": MULTI_SESSION_BUILD}
    rows = _list(session.db.participants)
    index = _participant_index(session, actor)
    if index < 0:
        return {"accepted": False, "status": "NOT_SESSION_PARTICIPANT", "build": MULTI_SESSION_BUILD}
    row = _dict(rows[index])
    row["ready"] = bool(ready)
    rows[index] = row
    session.write_participants(rows)
    session.append_log("READY" if ready else "NOT_READY", f"{actor.key} {'está listo' if ready else 'deja de estar listo'}.", actor_dbref=int(actor.id))
    emit_session(session, event="READY")
    return {"accepted": True, "status": "READY_SET", "ready": bool(ready), "session": public_session(session, actor), "build": MULTI_SESSION_BUILD}


def leave_session(actor):
    session = session_for_actor(actor)
    if not session:
        return {"accepted": False, "status": "NO_BATTLE_SESSION", "build": MULTI_SESSION_BUILD}
    if _text(session.db.status).upper() == "ACTIVE":
        return {"accepted": False, "status": "ACTIVE_SESSION_CANNOT_LEAVE", "build": MULTI_SESSION_BUILD}
    rows = [row for row in _list(session.db.participants) if _int(_dict(row).get("actor_dbref"), -1) != int(actor.id)]
    was_host = _int(session.db.host_dbref, -1) == int(actor.id)
    actor.db.pokerol_battle_session_id = None
    session.write_participants(rows)
    session.append_log("LEFT", f"{actor.key} sale de la sesión.", actor_dbref=int(actor.id))
    if not rows:
        session.db.status = "ABANDONED"
        session.db.phase = "COMPLETE"
        session.db.completed_at = int(time())
        return {"accepted": True, "status": "SESSION_ABANDONED", "build": MULTI_SESSION_BUILD}
    if was_host:
        session.db.host_dbref = _int(_dict(rows[0]).get("actor_dbref"), None)
        session.append_log("HOST_CHANGED", f"{_dict(rows[0]).get('name')} queda como host.", actor_dbref=session.db.host_dbref)
    emit_session(session, event="LEFT")
    return {"accepted": True, "status": "LEFT_SESSION", "session": public_session(session), "build": MULTI_SESSION_BUILD}


def _participant_team(session, actor_dbref):
    for row in _list(session.db.participants):
        row = _dict(row)
        if _int(row.get("actor_dbref"), -1) == _int(actor_dbref, -2):
            return _text(row.get("team")).upper() or "A"
    return "A"


def _human_combatant(session, participant):
    row = _dict(participant)
    actor = actor_from_dbref(row.get("actor_dbref"))
    if not actor:
        return None
    profile = active_pokemon(actor)
    if not profile:
        return None
    pokemon = normalize_pokemon(profile, side=row.get("team") or "A")
    return {
        "combatant_id": _text(pokemon.get("entity_id")),
        "controller_kind": "HUMAN",
        "controller_participant_id": _text(row.get("participant_id")),
        "actor_dbref": int(actor.id),
        "trainer_name": _text(actor.key),
        "team": _text(row.get("team")).upper() or "A",
        "pokemon": pokemon,
        "active": True,
        "needs_switch": False,
        "joined_turn": 1,
    }


def add_ai_combatant(session, pokemon_profile, *, team="B", controller_id="AI"):
    if not session or _text(session.db.status).upper() != "LOBBY":
        return {"accepted": False, "status": "SESSION_NOT_IN_LOBBY", "build": MULTI_SESSION_BUILD}
    profile = _dict(pokemon_profile)
    if not profile:
        return {"accepted": False, "status": "POKEMON_PROFILE_REQUIRED", "build": MULTI_SESSION_BUILD}
    wanted_team = _text(team).upper() or "B"
    pokemon = normalize_pokemon(profile, side=wanted_team)
    rows = [row for row in _list(session.db.combatants) if _text(_dict(row).get("combatant_id")) != _text(pokemon.get("entity_id"))]
    rows.append({
        "combatant_id": _text(pokemon.get("entity_id")),
        "controller_kind": "AI",
        "controller_participant_id": _text(controller_id) or "AI",
        "actor_dbref": None,
        "trainer_name": "WILD" if bool(pokemon.get("wild")) else "AI TRAINER",
        "team": wanted_team,
        "pokemon": pokemon,
        "active": True,
        "needs_switch": False,
        "joined_turn": 1,
    })
    session.write_combatants(rows)
    session.append_log("AI_COMBATANT_ADDED", f"{pokemon.get('name')} entra al equipo {wanted_team}.", combatant_id=pokemon.get("entity_id"), team=wanted_team)
    emit_session(session, event="ENCOUNTER_ATTACHED")
    return {"accepted": True, "status": "AI_COMBATANT_ADDED", "combatant": _clone(rows[-1]), "build": MULTI_SESSION_BUILD}


def lobby_can_start(session):
    if not session or _text(session.db.status).upper() != "LOBBY":
        return {"allowed": False, "status": "NOT_LOBBY"}
    rows = [_dict(row) for row in _list(session.db.participants)]
    if len(rows) < 2:
        return {"allowed": False, "status": "NEED_MORE_PLAYERS"}
    if not all(bool(row.get("ready")) for row in rows):
        return {"allowed": False, "status": "PLAYERS_NOT_READY"}
    kind = _text(session.db.kind).upper()
    teams = {_text(row.get("team")).upper() for row in rows}
    if kind == "PVP" and not {"A", "B"}.issubset(teams):
        return {"allowed": False, "status": "PVP_NEEDS_BOTH_TEAMS"}
    if kind in {"PVE_COOP", "RAID"}:
        ai_rows = [row for row in _list(session.db.combatants) if _text(_dict(row).get("controller_kind")).upper() == "AI"]
        if not ai_rows:
            return {"allowed": False, "status": "PVE_ENCOUNTER_NOT_ATTACHED"}
    return {"allowed": True, "status": "LOBBY_READY"}


def start_session(host):
    session = session_for_actor(host)
    if not session:
        return {"accepted": False, "status": "NO_BATTLE_SESSION", "build": MULTI_SESSION_BUILD}
    if _int(session.db.host_dbref, -1) != _int(host.id, -2):
        return {"accepted": False, "status": "HOST_ONLY", "build": MULTI_SESSION_BUILD}
    gate = lobby_can_start(session)
    if not gate.get("allowed"):
        return {"accepted": False, "status": gate.get("status"), "session": public_session(session, host), "build": MULTI_SESSION_BUILD}

    existing_ai = [
        _dict(row) for row in _list(session.db.combatants)
        if _text(_dict(row).get("controller_kind")).upper() == "AI"
    ]
    humans = []
    participants = _list(session.db.participants)
    for index, participant in enumerate(participants):
        combatant = _human_combatant(session, participant)
        if not combatant:
            return {"accepted": False, "status": "PARTICIPANT_HAS_NO_ACTIVE_POKEMON", "participant": _dict(participant).get("name"), "build": MULTI_SESSION_BUILD}
        humans.append(combatant)
        updated = _dict(participant)
        updated["active_entity_id"] = combatant["combatant_id"]
        updated["submitted_turn"] = 0
        participants[index] = updated

    combatants = humans + existing_ai
    teams = {_text(row.get("team")).upper() for row in combatants if _int(_dict(row).get("pokemon", {}).get("hp_current"), 0) > 0}
    if len(teams) < 2:
        return {"accepted": False, "status": "BATTLE_NEEDS_OPPOSING_TEAM", "build": MULTI_SESSION_BUILD}

    session.write_participants(participants)
    session.write_combatants(combatants)
    session.write_orders({})
    session.db.status = "ACTIVE"
    session.db.phase = "COMMAND"
    session.db.turn = 1
    session.db.started_at = int(time())
    session.db.updated_at = int(time())
    session.db.multi_target_pipeline = True
    session.append_log("BATTLE_STARTED", "La batalla multiplayer comienza.", teams=sorted(teams), combatants=len(combatants))
    emit_session(session, event="START")
    return {"accepted": True, "status": "MULTIPLAYER_BATTLE_STARTED", "session": public_session(session, host), "build": MULTI_SESSION_BUILD}
