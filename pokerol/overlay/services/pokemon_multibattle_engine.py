"""Pure-ish multi-combat round engine for POKEROL shared battle sessions.

All human orders are locked before resolution. AI orders are generated only once
all required human orders exist. One initiative list then resolves the shared
round across all teams.
"""

import random
from copy import deepcopy

from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    _action_priority,
    _execute_move,
    _speed,
    move_by_id,
)
from services.pokemon_battle_status_engine import end_turn_effects


MULTIBATTLE_BUILD = "0.1.1-shared-mutation-lockin"
SUPPORTED_ORDER_TYPES = {"MOVE"}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _row_ref(value):
    return value if isinstance(value, dict) else _dict(value)


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


def combatant_by_id(combatants, combatant_id):
    wanted = _text(combatant_id)
    for raw in combatants if isinstance(combatants, list) else _list(combatants):
        row = _row_ref(raw)
        if _text(row.get("combatant_id")) == wanted:
            return row
    return None


def able_combatants(combatants, *, team="", exclude_id=""):
    wanted_team = _text(team).upper()
    excluded = _text(exclude_id)
    output = []
    for raw in combatants if isinstance(combatants, list) else _list(combatants):
        row = _row_ref(raw)
        pokemon = _dict(row.get("pokemon"))
        if excluded and _text(row.get("combatant_id")) == excluded:
            continue
        if wanted_team and _text(row.get("team")).upper() != wanted_team:
            continue
        if not bool(row.get("active", True)) or bool(row.get("needs_switch")):
            continue
        if _int(pokemon.get("hp_current"), 0) <= 0:
            continue
        output.append(row)
    return output


def opposing_targets(combatants, attacker_id):
    attacker = combatant_by_id(combatants, attacker_id)
    if not attacker:
        return []
    team = _text(attacker.get("team")).upper()
    return [row for row in able_combatants(combatants) if _text(row.get("team")).upper() != team]


def human_order_requirements(session_state):
    combatants = _list(_dict(session_state).get("combatants"))
    required = []
    for raw in combatants:
        row = _dict(raw)
        if _text(row.get("controller_kind")).upper() != "HUMAN":
            continue
        if bool(row.get("needs_switch")):
            continue
        pokemon = _dict(row.get("pokemon"))
        if _int(pokemon.get("hp_current"), 0) <= 0:
            continue
        pid = _text(row.get("controller_participant_id"))
        if pid and pid not in required:
            required.append(pid)
    return required


def validate_order(session_state, participant_id, order):
    state = _dict(session_state)
    if _text(state.get("status")).upper() != "ACTIVE":
        return {"accepted": False, "status": "SESSION_NOT_ACTIVE", "build": MULTIBATTLE_BUILD}
    if _text(state.get("phase")).upper() != "COMMAND":
        return {"accepted": False, "status": "NOT_COMMAND_PHASE", "build": MULTIBATTLE_BUILD}
    pid = _text(participant_id)
    combatants = _list(state.get("combatants"))
    actor_row = next((
        _dict(row) for row in combatants
        if _text(_dict(row).get("controller_participant_id")) == pid
        and _text(_dict(row).get("controller_kind")).upper() == "HUMAN"
        and not bool(_dict(row).get("needs_switch"))
        and _int(_dict(_dict(row).get("pokemon")).get("hp_current"), 0) > 0
    ), None)
    if not actor_row:
        return {"accepted": False, "status": "NO_CONTROLLABLE_COMBATANT", "build": MULTIBATTLE_BUILD}
    command = _dict(order)
    kind = _text(command.get("type")).upper()
    if kind not in SUPPORTED_ORDER_TYPES:
        return {"accepted": False, "status": "ORDER_TYPE_NOT_YET_SUPPORTED", "type": kind, "build": MULTIBATTLE_BUILD}
    pokemon = _dict(actor_row.get("pokemon"))
    move = move_by_id(pokemon, command.get("move_id"))
    if not move:
        return {"accepted": False, "status": "MOVE_NOT_KNOWN", "build": MULTIBATTLE_BUILD}
    if _int(move.get("pp_current"), move.get("pp", 0)) <= 0:
        return {"accepted": False, "status": "NO_PP", "move_id": move.get("move_id"), "build": MULTIBATTLE_BUILD}
    targets = opposing_targets(combatants, actor_row.get("combatant_id"))
    if not targets:
        return {"accepted": False, "status": "NO_OPPOSING_TARGET", "build": MULTIBATTLE_BUILD}
    target_id = _text(command.get("target_entity_id"))
    if not target_id and len(targets) == 1:
        target_id = _text(targets[0].get("combatant_id"))
    valid_ids = {_text(row.get("combatant_id")) for row in targets}
    if target_id not in valid_ids:
        return {
            "accepted": False,
            "status": "INVALID_TARGET",
            "target_entity_id": target_id,
            "valid_target_ids": sorted(valid_ids),
            "build": MULTIBATTLE_BUILD,
        }
    normalized = _clone(command)
    normalized["type"] = "MOVE"
    normalized["target_entity_id"] = target_id
    normalized["actor_entity_id"] = _text(actor_row.get("combatant_id"))
    normalized["participant_id"] = pid
    return {
        "accepted": True,
        "status": "ORDER_VALID",
        "order": normalized,
        "actor_combatant_id": actor_row.get("combatant_id"),
        "build": MULTIBATTLE_BUILD,
    }


def _choose_ai_order(combatants, actor_row, rng):
    pokemon = _dict(actor_row.get("pokemon"))
    moves = [_dict(move) for move in _list(pokemon.get("moves")) if _int(_dict(move).get("pp_current"), _dict(move).get("pp", 0)) > 0]
    if not moves:
        return None
    targets = opposing_targets(combatants, actor_row.get("combatant_id"))
    if not targets:
        return None
    damaging = [move for move in moves if _int(move.get("power"), 0) > 0]
    move = rng.choice(damaging or moves)
    target = rng.choice(targets)
    return {
        "type": "MOVE",
        "move_id": _text(move.get("move_id")),
        "target_entity_id": _text(target.get("combatant_id")),
        "actor_entity_id": _text(actor_row.get("combatant_id")),
        "participant_id": _text(actor_row.get("controller_participant_id")),
        "ai": True,
    }


def _order_rows(combatants, human_orders, rng):
    rows = []
    for raw in combatants:
        actor_row = _dict(raw)
        pokemon = _dict(actor_row.get("pokemon"))
        if _int(pokemon.get("hp_current"), 0) <= 0 or bool(actor_row.get("needs_switch")):
            continue
        controller = _text(actor_row.get("controller_kind")).upper()
        action = _dict(_dict(human_orders).get(_text(actor_row.get("controller_participant_id")))) if controller == "HUMAN" else (_choose_ai_order(combatants, actor_row, rng) or {})
        if not action:
            continue
        rows.append({
            "actor_combatant_id": _text(actor_row.get("combatant_id")),
            "participant_id": _text(actor_row.get("controller_participant_id")),
            "team": _text(actor_row.get("team")).upper(),
            "action": action,
            "priority": _action_priority(action, pokemon),
            "speed": _speed(pokemon),
            "tie": rng.random(),
        })
    rows.sort(key=lambda row: (row["priority"], row["speed"], row["tie"]), reverse=True)
    return rows


def _session_log(log_rows, turn, phase, kind, text, **extra):
    row = {"turn": turn, "phase": phase, "kind": kind, "text": text}
    row.update({key: value for key, value in extra.items() if value is not None})
    log_rows.append(row)
    return row


def _merge_duel_logs(log_rows, duel_log, actor_row, target_row):
    for raw in _list(duel_log):
        row = _dict(raw)
        row["actor_combatant_id"] = _text(actor_row.get("combatant_id"))
        row["target_combatant_id"] = _text(target_row.get("combatant_id"))
        row["actor_team"] = _text(actor_row.get("team")).upper()
        row["target_team"] = _text(target_row.get("team")).upper()
        log_rows.append(row)


def _resolve_move_row(combatants, action_row, log_rows, turn, rng):
    actor_row = combatant_by_id(combatants, action_row.get("actor_combatant_id"))
    if not actor_row:
        return
    attacker = _dict(actor_row.get("pokemon"))
    if _int(attacker.get("hp_current"), 0) <= 0:
        _session_log(log_rows, turn, "ACTION", "SKIPPED_FAINTED", f"{attacker.get('name') or 'Pokémon'} ya está fuera de combate.", actor_combatant_id=actor_row.get("combatant_id"))
        return
    action = _dict(action_row.get("action"))
    targets = opposing_targets(combatants, actor_row.get("combatant_id"))
    target_row = combatant_by_id(combatants, action.get("target_entity_id"))
    if not target_row or _int(_dict(target_row.get("pokemon")).get("hp_current"), 0) <= 0:
        if len(targets) == 1:
            target_row = targets[0]
            action["target_entity_id"] = _text(target_row.get("combatant_id"))
            _session_log(log_rows, turn, "ACTION", "AUTO_RETARGET", f"{attacker.get('name')} cambia al único objetivo disponible.", actor_combatant_id=actor_row.get("combatant_id"), target_combatant_id=target_row.get("combatant_id"))
        else:
            _session_log(log_rows, turn, "ACTION", "TARGET_UNAVAILABLE", f"El objetivo de {attacker.get('name')} ya no está disponible.", actor_combatant_id=actor_row.get("combatant_id"))
            return
    defender = _dict(target_row.get("pokemon"))
    duel = {
        "battle_id": "MULTI-DUEL",
        "status": ACTIVE_STATUS,
        "phase": "ACTION",
        "turn": turn,
        "player": attacker,
        "enemy": defender,
        "log": [],
        "world_requests": [],
    }
    _execute_move(duel, "PLAYER", action, rng)
    actor_row["pokemon"] = duel["player"]
    target_row["pokemon"] = duel["enemy"]
    _merge_duel_logs(log_rows, duel.get("log"), actor_row, target_row)


def _apply_multi_round_end(combatants, log_rows, turn):
    for raw in combatants:
        row = _row_ref(raw)
        pokemon = _dict(row.get("pokemon"))
        if _int(pokemon.get("hp_current"), 0) <= 0:
            continue
        events = end_turn_effects(pokemon, None)
        row["pokemon"] = pokemon
        for event in events:
            event = _dict(event)
            _session_log(
                log_rows,
                turn,
                "RESOLUTION",
                _text(event.get("kind")) or "BATTLE_EFFECT",
                _text(event.get("text")) or "Efecto de fin de turno.",
                combatant_id=row.get("combatant_id"),
                team=row.get("team"),
                damage=event.get("damage"),
            )


def winning_team(combatants):
    alive_teams = {
        _text(_dict(row).get("team")).upper()
        for row in _list(combatants)
        if bool(_dict(row).get("active", True)) and _int(_dict(_dict(row).get("pokemon")).get("hp_current"), 0) > 0
    }
    return next(iter(alive_teams)) if len(alive_teams) == 1 else ""


def resolve_locked_round(session_state, human_orders, *, rng=None):
    """Resolve exactly one shared round after every required human has locked in."""
    rng = rng or random.SystemRandom()
    state = _clone(_dict(session_state))
    if _text(state.get("status")).upper() != "ACTIVE":
        return {"accepted": False, "status": "SESSION_NOT_ACTIVE", "state": state, "build": MULTIBATTLE_BUILD}
    if _text(state.get("phase")).upper() != "COMMAND":
        return {"accepted": False, "status": "NOT_COMMAND_PHASE", "state": state, "build": MULTIBATTLE_BUILD}
    required = human_order_requirements(state)
    orders = _dict(human_orders)
    missing = [pid for pid in required if not _dict(orders.get(pid))]
    if missing:
        return {"accepted": False, "status": "WAITING_FOR_ORDERS", "missing_participant_ids": missing, "state": state, "build": MULTIBATTLE_BUILD}
    combatants = _list(state.get("combatants"))
    turn = max(1, _int(state.get("turn"), 1))
    log_rows = _list(state.get("log"))
    order_rows = _order_rows(combatants, orders, rng)
    state["phase"] = "ORDER"
    _session_log(log_rows, turn, "ORDER", "INITIATIVE", "Las órdenes multiplayer quedan ordenadas.", order=[{
        "actor_combatant_id": row["actor_combatant_id"],
        "priority": row["priority"],
        "speed": row["speed"],
    } for row in order_rows])
    state["phase"] = "ACTION"
    for row in order_rows:
        if winning_team(combatants):
            break
        if _text(_dict(row.get("action")).get("type")).upper() == "MOVE":
            _resolve_move_row(combatants, row, log_rows, turn, rng)
    state["phase"] = "RESOLUTION"
    _apply_multi_round_end(combatants, log_rows, turn)
    winner = winning_team(combatants)
    state["combatants"] = combatants
    state["log"] = log_rows[-220:]
    state["pending_orders"] = {}
    if winner:
        state["status"] = "COMPLETE"
        state["phase"] = "COMPLETE"
        state["winning_team"] = winner
        _session_log(state["log"], turn, "COMPLETE", "BATTLE_END", f"El equipo {winner} gana la batalla.", winning_team=winner)
    else:
        state["turn"] = turn + 1
        state["phase"] = "COMMAND"
    return {
        "accepted": True,
        "status": "MULTIPLAYER_ROUND_RESOLVED",
        "state": state,
        "initiative": _clone(order_rows),
        "winning_team": winner or None,
        "build": MULTIBATTLE_BUILD,
    }
