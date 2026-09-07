"""Natural-language orders for an already-active POKEROL Pokémon battle.

The browser never decides battle meaning. This module reads the current authoritative
battle, Room targets, party, positions and reaction options, converts high-confidence
trainer language into the same action packets used by the normal battle UI, and then
submits those packets through the existing battle runtimes.

It deliberately does not start a new combat encounter. While a Pokémon battle is
active, free text belongs to that battle or is rejected as an unclear battle order.
"""

import re
import unicodedata

from services.pokemon_battle_environment_engine import compatible_environment_targets
from services.pokemon_battle_position_engine import position_targets
from services.pokemon_battle_reaction_engine import reaction_options
from services.pokemon_battle_runtime import current_battle
from services.pokemon_battle_tactical_runtime import set_player_reaction, submit_tactical_battle_action


BATTLE_FREE_ORDER_BUILD = "0.1.0-authoritative-natural-battle-orders"
ACTIVE_STATUS = "ACTIVE"


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


def _norm(value):
    text = unicodedata.normalize("NFD", _text(value).lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _phrase_in(raw_norm, phrase):
    wanted = _norm(phrase)
    if not wanted:
        return False
    return (" " + wanted + " ") in (" " + raw_norm + " ") or wanted in raw_norm


def _best_named_row(raw_norm, rows, names):
    best = None
    best_score = -1
    for raw in rows:
        row = _dict(raw)
        candidates = []
        for key in names:
            value = _text(row.get(key))
            if value:
                candidates.append(value)
        for candidate in candidates:
            normalized = _norm(candidate)
            if not normalized or not _phrase_in(raw_norm, normalized):
                continue
            score = len(normalized)
            if score > best_score:
                best = row
                best_score = score
    return best


def _battle_ready(actor):
    battle = current_battle(actor)
    return battle if _text(battle.get("status")).upper() == ACTIVE_STATUS else {}


def _move_match(raw_norm, battle):
    player = _dict(_dict(battle).get("player"))
    return _best_named_row(raw_norm, _list(player.get("moves")), ("name", "move_id"))


def _switch_match(raw_norm, battle):
    party = _list(_dict(battle).get("party_state", {}).get("party"))
    if not party:
        # The stored battle does not include public party_state; wrapper fills it below.
        return None
    if not any(_phrase_in(raw_norm, word) for word in ("cambia", "cambiar", "saca", "sacar", "reemplaza", "switch")):
        return None
    row = _best_named_row(raw_norm, party, ("nickname", "species_name", "name"))
    if not row:
        return None
    try:
        slot = int(row.get("party_slot"))
    except (TypeError, ValueError):
        return None
    return {"type": "SWITCH", "slot": slot}


def _reaction_intent(raw_norm, options):
    wanted = None
    if any(_phrase_in(raw_norm, phrase) for phrase in ("esquiva", "esquivar", "evade", "dodge")):
        wanted = "DODGE"
    elif any(_phrase_in(raw_norm, phrase) for phrase in ("desvia", "desviar", "redirige", "refleja", "redirect")):
        wanted = "REDIRECT"
    elif any(_phrase_in(raw_norm, phrase) for phrase in ("bloquea", "bloquear", "defiendete", "defiende", "block")):
        wanted = "BLOCK"
    elif any(_phrase_in(raw_norm, phrase) for phrase in ("intercepta", "interceptar", "intercept")):
        wanted = "INTERCEPT"
    if not wanted:
        return None

    candidates = [_dict(row) for row in options if _text(_dict(row).get("policy")).upper() == wanted]
    if not candidates:
        return {"policy": wanted, "unauthorized": True}
    # Prefer a named defensive move explicitly mentioned by the trainer.
    named = _best_named_row(raw_norm, candidates, ("method_move_name", "method_move_id"))
    chosen = named or candidates[0]
    return {
        "policy": wanted,
        "method_move_id": _text(chosen.get("method_move_id")),
        "option": chosen,
    }


def _position_action_word(raw_norm):
    if any(_phrase_in(raw_norm, phrase) for phrase in ("cubret", "cubrete", "cobertura", "detras", "escondete", "take cover")):
        return "TAKE_COVER"
    if any(_phrase_in(raw_norm, phrase) for phrase in ("sube", "trepa", "escala", "encima", "climb")):
        return "CLIMB"
    if any(_phrase_in(raw_norm, phrase) for phrase in ("entra al agua", "entra en el agua", "metete al agua", "nada", "sumergete", "enter water")):
        return "ENTER_WATER"
    if any(_phrase_in(raw_norm, phrase) for phrase in ("despega", "vuela", "toma el aire", "al aire", "takeoff")):
        return "TAKEOFF"
    if any(_phrase_in(raw_norm, phrase) for phrase in ("aterriza", "baja al suelo", "vuelve al suelo", "terreno abierto", "return ground")):
        return "RETURN_GROUND"
    return ""


def _position_match(raw_norm, targets):
    action = _position_action_word(raw_norm)
    if not action:
        return None
    candidates = [_dict(row) for row in targets if _text(_dict(row).get("action")).upper() == action]
    if not candidates:
        return {"position_action": action, "unauthorized": True}
    named = _best_named_row(raw_norm, candidates, ("name", "target_id"))
    chosen = named or (candidates[0] if len(candidates) == 1 else None)
    if not chosen:
        return {"position_action": action, "ambiguous": True, "candidates": candidates}
    return {
        "type": "FREE_ORDER",
        "position_action": action,
        "target_id": _text(chosen.get("target_id")),
        "method_move_id": _text(chosen.get("method_move_id")),
        "target": chosen,
    }


def _environment_move_action(actor, raw_norm, battle, move):
    if not move or not bool(move.get("world_enabled")) or not _list(move.get("world_effects")):
        return None
    targets = compatible_environment_targets(actor, move)
    chosen = _best_named_row(raw_norm, targets, ("name", "object_id"))
    if not chosen:
        return None
    return {
        "type": "FREE_ORDER",
        "move_id": _text(move.get("move_id")),
        "world_target": {
            "object_id": _text(chosen.get("object_id")),
            "dbref": chosen.get("dbref"),
            "name": _text(chosen.get("name")),
        },
    }


def interpret_battle_free_order(actor, raw_player_input):
    """Return a high-confidence battle intent without mutating battle state."""
    battle = _battle_ready(actor)
    raw = _text(raw_player_input)
    normalized = _norm(raw)
    if not battle:
        return {"handled": False, "status": "NO_ACTIVE_BATTLE", "build": BATTLE_FREE_ORDER_BUILD}
    if not normalized:
        return {"handled": True, "status": "EMPTY_BATTLE_ORDER", "build": BATTLE_FREE_ORDER_BUILD}

    # Public party state is generated outside the stored battle; attach it only to
    # this interpretation copy so switch-name matching uses authoritative storage.
    from services.pokemon_party_engine import party_state
    battle_context = dict(battle)
    battle_context["party_state"] = party_state(actor)

    options = reaction_options(battle, "PLAYER")
    reaction = _reaction_intent(normalized, options)
    if reaction:
        return {
            "handled": True,
            "status": "REACTION_INTENT" if not reaction.get("unauthorized") else "REACTION_NOT_AVAILABLE",
            "kind": "REACTION",
            "reaction": reaction,
            "raw": raw,
            "build": BATTLE_FREE_ORDER_BUILD,
        }

    switch_action = _switch_match(normalized, battle_context)
    if switch_action:
        return {"handled": True, "status": "SWITCH_INTENT", "kind": "ACTION", "action": switch_action, "raw": raw, "build": BATTLE_FREE_ORDER_BUILD}

    if any(_phrase_in(normalized, phrase) for phrase in ("huye", "huir", "escapa", "escapar", "corre", "run away")):
        return {"handled": True, "status": "RUN_INTENT", "kind": "ACTION", "action": {"type": "RUN"}, "raw": raw, "build": BATTLE_FREE_ORDER_BUILD}

    if any(_phrase_in(normalized, phrase) for phrase in ("captura", "capturarlo", "pokeball", "poke ball", "lanza la bola")):
        return {"handled": True, "status": "CAPTURE_INTENT", "kind": "ACTION", "action": {"type": "CAPTURE", "item_id": "POKE_BALL"}, "raw": raw, "build": BATTLE_FREE_ORDER_BUILD}

    move = _move_match(normalized, battle)
    position = _position_match(normalized, position_targets(actor, battle, side="PLAYER"))
    environment_action = _environment_move_action(actor, normalized, battle, move) if move else None

    if position and move and not environment_action:
        # Do not silently turn a compound anime maneuver into two rounds. The
        # player gets a precise prompt and can choose which component happens now.
        return {
            "handled": True,
            "status": "COMPOUND_ORDER_NEEDS_PRIORITY",
            "kind": "AMBIGUOUS",
            "move": move,
            "position": position,
            "raw": raw,
            "build": BATTLE_FREE_ORDER_BUILD,
        }

    if environment_action:
        return {"handled": True, "status": "WORLD_MOVE_INTENT", "kind": "ACTION", "action": environment_action, "move": move, "raw": raw, "build": BATTLE_FREE_ORDER_BUILD}

    if position:
        status = "POSITION_INTENT"
        if position.get("unauthorized"):
            status = "POSITION_NOT_AVAILABLE"
        elif position.get("ambiguous"):
            status = "POSITION_TARGET_AMBIGUOUS"
        return {"handled": True, "status": status, "kind": "POSITION", "position": position, "action": position if position.get("type") else None, "raw": raw, "build": BATTLE_FREE_ORDER_BUILD}

    if move:
        return {
            "handled": True,
            "status": "MOVE_INTENT",
            "kind": "ACTION",
            "action": {"type": "MOVE", "move_id": _text(move.get("move_id"))},
            "move": move,
            "raw": raw,
            "build": BATTLE_FREE_ORDER_BUILD,
        }

    return {
        "handled": True,
        "status": "BATTLE_ORDER_UNCLEAR",
        "kind": "UNRESOLVED",
        "raw": raw,
        "build": BATTLE_FREE_ORDER_BUILD,
    }


def _message(actor, text):
    if actor and _text(text):
        actor.msg("\n" + _text(text))


def submit_battle_free_order(actor, raw_player_input):
    """Interpret and execute one natural-language order against the active battle."""
    intent = interpret_battle_free_order(actor, raw_player_input)
    if not intent.get("handled"):
        return intent
    status = _text(intent.get("status")).upper()

    if status == "REACTION_INTENT":
        reaction = _dict(intent.get("reaction"))
        result = set_player_reaction(actor, reaction.get("policy"), method_move_id=reaction.get("method_move_id"))
        if result.get("accepted"):
            label = _text(_dict(reaction.get("option")).get("label")) or reaction.get("policy")
            _message(actor, "Orden preparada: {}.".format(label))
        else:
            _message(actor, "Esa reacción no está disponible ahora: {}.".format(result.get("status")))
        return {**intent, "result": result, "executed": bool(result.get("accepted"))}

    if status == "REACTION_NOT_AVAILABLE":
        _message(actor, "Tu Pokémon no tiene una reacción válida de ese tipo en este momento.")
        return {**intent, "executed": False}

    if status == "COMPOUND_ORDER_NEEDS_PRIORITY":
        move_name = _text(_dict(intent.get("move")).get("name")) or "el movimiento"
        position_name = _text(_dict(_dict(intent.get("position")).get("target")).get("name")) or "esa posición"
        _message(actor, "La orden combina cambiar de posición y atacar. Indica qué hace primero: ir a {} o usar {}.".format(position_name, move_name))
        return {**intent, "executed": False}

    if status == "POSITION_NOT_AVAILABLE":
        _message(actor, "Esa posición no existe o no es alcanzable desde esta escena de combate.")
        return {**intent, "executed": False}

    if status == "POSITION_TARGET_AMBIGUOUS":
        names = [_text(_dict(row).get("name")) for row in _list(_dict(intent.get("position")).get("candidates"))]
        names = [name for name in names if name]
        _message(actor, "Hay varias posiciones posibles. Especifica una: {}.".format(", ".join(names[:5]) or "objetivo de posición"))
        return {**intent, "executed": False}

    action = _dict(intent.get("action"))
    if action:
        result = submit_tactical_battle_action(actor, action)
        if not result.get("accepted"):
            _message(actor, "La orden no puede ejecutarse ahora: {}.".format(result.get("status")))
        return {**intent, "result": result, "executed": bool(result.get("accepted"))}

    if status == "BATTLE_ORDER_UNCLEAR":
        _message(actor, "La batalla ya está activa. Da una orden concreta a tu Pokémon: movimiento, posición, reacción, cambio, captura o huida.")
    elif status == "EMPTY_BATTLE_ORDER":
        _message(actor, "¿Qué orden le das a tu Pokémon?")
    return {**intent, "executed": False}
