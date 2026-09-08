"""Contextual reaction windows for POKEROL Tsubasa combat.

A reaction is never prepared during COMMAND. The server opens this window only
when an enemy move is about to resolve against the player's active Pokemon.
The client may answer with one of the authorized options or PASS. If it does
not answer, the UI sends PASS and the Pokemon receives no automatic dodge.
"""

from copy import deepcopy
from uuid import uuid4

from services.pokemon_battle_engine import move_by_id
from services.pokemon_battle_reaction_engine import arm_reaction, clear_reaction, reaction_options


REACTION_WINDOW_BUILD = "1.0.0-contextual-tsubasa-window"
REACTION_TIMEOUT_MS = 4500
MAX_WINDOW_OPTIONS = 4


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


def _upper_set(value):
    return {str(v).strip().upper() for v in _list(value) if str(v).strip()}


def _source_move(battle, move_id, side="ENEMY"):
    wanted = _text(move_id).upper()
    key = "_source_enemy_profile" if _text(side).upper() == "ENEMY" else "_source_player_profile"
    source = _dict(_dict(battle).get(key))
    for raw in _list(source.get("moves")) + _list(source.get("resolved_moves")):
        row = _dict(raw)
        if _text(row.get("move_id")).upper() == wanted:
            return row
    pokemon = _dict(_dict(battle).get("enemy" if _text(side).upper() == "ENEMY" else "player"))
    return _dict(move_by_id(pokemon, move_id))


def _pose_name(move):
    move = _dict(move)
    visual = _dict(move.get("visual"))
    family = _text(visual.get("pose_family")).upper()
    mapping = {
        "ATTACK_PHYSICAL": "attack_physical",
        "ATTACK_SPECIAL": "attack_special",
        "CHARGE": "charge",
        "MOVEMENT": "movement",
        "STATUS": "status",
    }
    if family in mapping:
        return mapping[family]
    damage = _text(move.get("damage_class")).upper()
    return "attack_special" if damage == "SPECIAL" else "status" if damage == "STATUS" else "attack_physical"


def _attacker_media(battle, move):
    source = _dict(_dict(battle).get("_source_enemy_profile"))
    visuals = _dict(source.get("combat_visuals"))
    shots = _dict(visuals.get("shots"))
    pose = _pose_name(move)
    row = _dict(shots.get(pose))
    src = _text(row.get("video") or row.get("image"))
    media_type = "video" if _text(row.get("video")) else "image" if src else ""
    if not src:
        sprite = _dict(source.get("sprite"))
        src = _text(sprite.get("front"))
        media_type = "image" if src else ""
        scale = sprite.get("scale", 1.0)
        anchor_x, anchor_y = 50, 100
    else:
        scale = row.get("scale", 1.0)
        anchor_x, anchor_y = row.get("anchor_x", 50), row.get("anchor_y", 100)
    return {
        "pose": pose,
        "src": src,
        "type": media_type,
        "scale": scale,
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
    }


def contextual_options(battle, incoming_move, defender_side="PLAYER"):
    move = _dict(incoming_move)
    delivery = _text(move.get("delivery")).upper()
    damage_class = _text(move.get("damage_class")).upper()
    if delivery == "SELF":
        return []

    rows = []
    for raw in reaction_options(battle, defender_side):
        row = _dict(raw)
        policy = _text(row.get("policy")).upper()
        if policy == "INTERCEPT" and not bool(_dict(battle).get("protected_target_pipeline_active")):
            continue
        if policy in {"REDIRECT", "BLOCK"}:
            allowed = _upper_set(row.get("allowed_deliveries"))
            if allowed and delivery not in allowed:
                continue
            if bool(row.get("physical_only")) and damage_class != "PHYSICAL":
                continue
        rows.append(deepcopy(row))
        if len(rows) >= MAX_WINDOW_OPTIONS:
            break
    return rows


def build_window(battle, incoming_action):
    state = _dict(battle)
    action = _dict(incoming_action)
    if _text(action.get("type")).upper() != "MOVE":
        return None
    enemy = _dict(state.get("enemy"))
    player = _dict(state.get("player"))
    move = _dict(move_by_id(enemy, action.get("move_id")))
    if not move:
        return None
    options = contextual_options(state, move, "PLAYER")
    if not options:
        return None
    source_move = _source_move(state, move.get("move_id"), "ENEMY") or move
    return {
        "window_id": "RW-" + uuid4().hex[:12].upper(),
        "battle_id": _text(state.get("battle_id")),
        "turn": _int(state.get("turn"), 1),
        "attacker_side": "ENEMY",
        "defender_side": "PLAYER",
        "attacker_name": _text(enemy.get("name") or enemy.get("species_name")) or "RIVAL",
        "defender_name": _text(player.get("name") or player.get("species_name")) or "PKM",
        "move_id": _text(move.get("move_id")),
        "move_name": _text(move.get("name") or move.get("move_id")),
        "delivery": _text(move.get("delivery")).upper(),
        "damage_class": _text(move.get("damage_class")).upper(),
        "options": options,
        "attacker_media": _attacker_media(state, source_move),
        "timeout_ms": REACTION_TIMEOUT_MS,
        "status": "OPEN",
        "build": REACTION_WINDOW_BUILD,
    }


def public_window(battle):
    raw = _dict(_dict(battle).get("pending_reaction_window"))
    if not raw or _text(raw.get("status")).upper() != "OPEN":
        return {}
    return deepcopy(raw)


def apply_choice(battle, window_id, policy="PASS", method_move_id=""):
    state = battle if isinstance(battle, dict) else {}
    window = _dict(state.get("pending_reaction_window"))
    if not window or _text(window.get("status")).upper() != "OPEN":
        return {"accepted": False, "status": "NO_REACTION_WINDOW", "build": REACTION_WINDOW_BUILD}
    if _text(window.get("window_id")) != _text(window_id):
        return {"accepted": False, "status": "REACTION_WINDOW_MISMATCH", "build": REACTION_WINDOW_BUILD}

    wanted = _text(policy).upper() or "PASS"
    method = _text(method_move_id)
    player = state.get("player")
    if wanted in {"PASS", "NONE", "SKIP", "TIMEOUT"}:
        clear_reaction(player)
        window["status"] = "PASSED"
        window["choice"] = "PASS"
        state["pending_reaction_window"] = window
        return {"accepted": True, "status": "REACTION_PASSED", "choice": "PASS", "build": REACTION_WINDOW_BUILD}

    authorized = None
    for raw in _list(window.get("options")):
        row = _dict(raw)
        if _text(row.get("policy")).upper() == wanted and _text(row.get("method_move_id")) == method:
            authorized = row
            break
    if not authorized:
        return {"accepted": False, "status": "REACTION_NOT_IN_WINDOW", "build": REACTION_WINDOW_BUILD}

    result = arm_reaction(state, "PLAYER", wanted, method_move_id=method)
    if not result.get("accepted"):
        return {**result, "build": REACTION_WINDOW_BUILD}
    window["status"] = "ANSWERED"
    window["choice"] = wanted
    window["method_move_id"] = method
    state["pending_reaction_window"] = window
    return {"accepted": True, "status": "REACTION_CHOSEN", "choice": wanted, "reaction": result.get("reaction"), "build": REACTION_WINDOW_BUILD}
