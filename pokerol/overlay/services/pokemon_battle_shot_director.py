"""Build presentation-only WEGO shot sequences from authoritative battle facts.

The battle engine chooses both sides' intents before resolution. This module turns
that authoritative round into the Captain-Tsubasa-style presentation contract:
first reveal the intentions, then show reactions/execution, then consequences.
Shots never decide outcomes and never mutate battle state.
"""

from copy import deepcopy

from services.pokemon_move_capability_engine import move_combat_profile


SHOT_DIRECTOR_BUILD = "0.2.0-wego-anime-sequence"


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


def _sprite(profile, side="PLAYER"):
    row = _dict(_dict(profile).get("sprite"))
    if side == "PLAYER":
        return _text(row.get("back") or row.get("front"))
    return _text(row.get("front") or row.get("back"))


def _source_move(battle, move_id, side="PLAYER"):
    state = _dict(battle)
    source = _dict(state.get("_source_player_profile" if side == "PLAYER" else "_source_enemy_profile"))
    wanted = _text(move_id).upper()
    for raw in _list(source.get("moves")) + _list(source.get("resolved_moves")):
        row = _dict(raw)
        if _text(row.get("move_id")).upper() == wanted:
            return row
    combatant = _dict(state.get("player" if side == "PLAYER" else "enemy"))
    for raw in _list(combatant.get("moves")):
        row = _dict(raw)
        if _text(row.get("move_id")).upper() == wanted:
            return row
    return {}


def _media(move, fallback=""):
    row = _dict(move)
    media = _dict(row.get("cinematic_media"))
    src = _text(media.get("src") or row.get("cinematic_video") or row.get("cinematic_image") or fallback)
    kind = _text(media.get("type")).lower()
    if not kind and src:
        kind = "video" if src.lower().split("?", 1)[0].endswith((".mp4", ".webm", ".ogg")) else "image"
    return {"media_type": kind or None, "media_src": src or None}


def _move_name(battle, move_id, side):
    move = _source_move(battle, move_id, side)
    return _text(move.get("name")) or _text(move_id)


def _action_text(battle, action, side):
    row = _dict(action)
    kind = _text(row.get("type")).upper()
    pokemon = _dict(_dict(battle).get("player" if side == "PLAYER" else "enemy"))
    name = _text(pokemon.get("name")) or ("TU POKÉMON" if side == "PLAYER" else "RIVAL")
    move_id = _text(row.get("move_id"))
    if move_id:
        move_name = _move_name(battle, move_id, side)
        target = _text(_dict(row.get("world_target")).get("name"))
        if target:
            return "{} → {} SOBRE {}".format(name, move_name, target).upper()
        return "{} → {}".format(name, move_name).upper()
    if kind == "SWITCH":
        return "{} → CAMBIO DE POKÉMON".format(name).upper()
    if kind == "CAPTURE":
        return "ENTRENADOR → LANZAR POKÉ BALL"
    if kind == "RUN":
        return "ENTRENADOR → HUIR"
    if kind == "ITEM":
        return "ENTRENADOR → USAR OBJETO"
    return "{} → {}".format(name, kind or "ACCIÓN").upper()


def _enemy_declared_action(before, logs):
    enemy = _dict(_dict(before).get("enemy"))
    enemy_id = _text(enemy.get("entity_id"))
    for row in logs:
        kind = _text(row.get("kind")).upper()
        if kind not in {"MOVE", "WORLD_MOVE_ORDER", "POSITION_MOVE", "POSITION_CHANGED"}:
            continue
        if enemy_id and _text(row.get("actor")) != enemy_id:
            continue
        move_id = _text(row.get("move_id"))
        if move_id:
            return {"type": "MOVE", "move_id": move_id}
        if kind == "POSITION_CHANGED":
            return {"type": "FREE_ORDER", "position_action": _text(row.get("position_action"))}
    return {}


def _reaction_lines(logs):
    output = []
    for row in logs:
        kind = _text(row.get("kind")).upper()
        if kind in {
            "DODGE", "BLOCK", "REDIRECT", "INTERCEPT", "REACTION", "REACTION_RESULT",
            "POSITION_BLOCKED_MOVE", "MISS", "REACTION_WINDOW",
        }:
            line = _text(row.get("text"))
            if line and line not in output:
                output.append(line)
    return output


def build_battle_shots(before_battle, after_battle, action, *, log_start=0, event="ROUND"):
    before = _dict(before_battle)
    after = _dict(after_battle)
    action = _dict(action)
    kind = _text(action.get("type")).upper()
    move_id = _text(action.get("move_id"))
    player = _dict(before.get("player"))
    enemy = _dict(before.get("enemy"))
    site = _dict(before.get("site"))
    logs = [_dict(row) for row in _list(after.get("log"))[max(0, int(log_start or 0)):]]
    move = _source_move(before, move_id, "PLAYER") if move_id else {}
    profile = move_combat_profile(move) if move else {}
    enemy_action = _enemy_declared_action(before, logs)
    shots = []

    scene_image = _dict(site.get("scene_image"))
    scene_src = _text(scene_image.get("src")) if scene_image else ""
    shots.append({
        "shot": "ESTABLISHING",
        "title": _text(site.get("name")) or "CAMPO DE BATALLA",
        "text": "TURNO {} · AMBOS BANDOS ELIGEN SU INTENCIÓN ANTES DE RESOLVER.".format(before.get("turn") or 1),
        "media_type": "image" if scene_src else None,
        "media_src": scene_src or None,
        "duration_ms": 650,
    })

    player_media = _media(move, _sprite(player, "PLAYER")) if move_id else {"media_type": "image" if _sprite(player, "PLAYER") else None, "media_src": _sprite(player, "PLAYER") or None}
    shots.append({
        "shot": "DECLARATION_PLAYER",
        "title": "TU ORDEN",
        "text": _action_text(before, action, "PLAYER"),
        **player_media,
        "duration_ms": 850,
    })

    if enemy_action:
        enemy_move = _source_move(before, enemy_action.get("move_id"), "ENEMY") if enemy_action.get("move_id") else {}
        enemy_media = _media(enemy_move, _sprite(enemy, "ENEMY"))
        shots.append({
            "shot": "DECLARATION_ENEMY",
            "title": "INTENCIÓN RIVAL",
            "text": _action_text(before, enemy_action, "ENEMY"),
            **enemy_media,
            "duration_ms": 850,
        })

    reaction_lines = _reaction_lines(logs)
    if reaction_lines:
        shots.append({
            "shot": "REACTION",
            "title": "REACCIÓN / BLOQUEO",
            "text": " ".join(reaction_lines[-2:]),
            "duration_ms": 850,
        })

    if move_id:
        move_name = _text(move.get("name")) or move_id
        media = _media(move, _sprite(player, "PLAYER"))
        shots.append({
            "shot": "EXECUTION",
            "title": "{} USA {}".format(_text(player.get("name")) or "POKÉMON", move_name).upper(),
            "text": "POT {} · CONTROL {} · VELOCIDAD {} · {} · {}".format(
                profile.get("power", 0), profile.get("control", 0), profile.get("speed", 0),
                profile.get("range") or "", profile.get("trajectory") or "",
            ).strip(" ·"),
            **media,
            "duration_ms": 900,
        })

        target_src = _sprite(enemy, "ENEMY")
        world_target = _dict(action.get("world_target"))
        target_name = _text(world_target.get("name")) or _text(enemy.get("name")) or "OBJETIVO"
        shots.append({
            "shot": "TARGET",
            "title": target_name.upper(),
            "text": "La trayectoria se cruza con la posición, cobertura y estado reales del objetivo.",
            "media_type": "image" if target_src and not world_target else None,
            "media_src": target_src if target_src and not world_target else None,
            "duration_ms": 700,
        })

    resolution_lines = []
    for row in logs:
        if _text(row.get("kind")).upper() in {"ORDER", "REACTION_WINDOW"}:
            continue
        line = _text(row.get("text"))
        if line and line not in resolution_lines:
            resolution_lines.append(line)
    if resolution_lines:
        shots.append({
            "shot": "IMPACT",
            "title": "RESOLUCIÓN DEL TURNO",
            "text": " ".join(resolution_lines[-4:]),
            "duration_ms": 1200,
        })

    world = _dict(after.get("last_world_resolution"))
    scene_reaction = _dict(world.get("scene_reaction"))
    if scene_reaction.get("reacted"):
        shots.append({
            "shot": "CONSEQUENCE",
            "title": "EL MUNDO REACCIONA",
            "text": "{} reacciona a la consecuencia sobre {}.".format(
                "Profesor Oak" if scene_reaction.get("npc_id") == "NPC-KANTO-PAL-OAK" else "La escena",
                _text(scene_reaction.get("target_name")) or "el entorno",
            ),
            "duration_ms": 1300,
        })

    if _text(after.get("status")).upper() == "COMPLETE":
        shots.append({
            "shot": "END",
            "title": "BATALLA INTERRUMPIDA" if _text(after.get("outcome")).upper() == "ABANDONED" else "FIN DEL COMBATE",
            "text": _text(_dict(after.get("scene_interruption")).get("reason")) or _text(after.get("outcome")),
            "duration_ms": 1100,
        })

    return {
        "battle_id": after.get("battle_id") or before.get("battle_id"),
        "event": _text(event).upper() or "ROUND",
        "round_mode": "WEGO",
        "turn": before.get("turn") or after.get("turn") or 1,
        "action": deepcopy(action),
        "enemy_action": deepcopy(enemy_action),
        "move_profile": profile,
        "shots": shots,
        "build": SHOT_DIRECTOR_BUILD,
    }


def emit_battle_shots(actor, before_battle, after_battle, action, *, log_start=0, event="ROUND"):
    packet = build_battle_shots(before_battle, after_battle, action, log_start=log_start, event=event)
    if actor and packet.get("shots"):
        actor.msg(pokerol_battle_shots=((packet,), {"build": SHOT_DIRECTOR_BUILD}))
        return True
    return False