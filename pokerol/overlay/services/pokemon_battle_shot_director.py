"""Presentation-only Tsubasa shot director for Fakemon combat.

Authoritative battle/world state decides outcomes. This module only selects the
correct Fakemon pose + Skill FX/media for the facts already resolved.
"""

from copy import deepcopy

from services.pokemon_move_capability_engine import move_combat_profile

SHOT_DIRECTOR_BUILD = "0.4.0-tsubasa-attacker-target-order"
POSE_MAP = {
    "NEUTRAL": "neutral", "ATTACK_PHYSICAL": "attack_physical",
    "ATTACK_SPECIAL": "attack_special", "CHARGE": "charge",
    "DEFEND": "defend", "DODGE": "dodge", "MOVEMENT": "dodge",
    "STATUS": "neutral",
}


def _dict(value):
    try: return dict(value or {})
    except Exception: return {}


def _list(value):
    try: return list(value or [])
    except Exception: return []


def _text(value): return str(value or "").strip()


def _num(value, default=0.0):
    try: return float(value)
    except (TypeError, ValueError): return float(default)


def _source_profile(battle, side):
    state = _dict(battle)
    source = _dict(state.get("_source_player_profile" if side == "PLAYER" else "_source_enemy_profile"))
    return source or _dict(state.get("player" if side == "PLAYER" else "enemy"))


def _combatant(battle, side): return _dict(_dict(battle).get("player" if side == "PLAYER" else "enemy"))


def _source_move(battle, move_id, side="PLAYER"):
    wanted = _text(move_id).upper()
    source = _source_profile(battle, side)
    for raw in _list(source.get("moves")) + _list(source.get("resolved_moves")):
        row = _dict(raw)
        if _text(row.get("move_id")).upper() == wanted: return row
    for raw in _list(_combatant(battle, side).get("moves")):
        row = _dict(raw)
        if _text(row.get("move_id")).upper() == wanted: return row
    return {}


def _battle_sprite(profile, side):
    row = _dict(_dict(profile).get("combat_visuals")).get("battle")
    row = _dict(row) or _dict(_dict(profile).get("sprite"))
    src = _text(row.get("back") or row.get("front")) if side == "PLAYER" else _text(row.get("front") or row.get("back"))
    return {"media_type": "image" if src else None, "media_src": src or None, "media_scale": _num(row.get("scale"), 1.0), "anchor_x": 50, "anchor_y": 100}


def _pose(profile, pose_name, side):
    visuals = _dict(_dict(profile).get("combat_visuals"))
    row = _dict(_dict(visuals.get("shots")).get(pose_name))
    src = _text(row.get("video") or row.get("image"))
    if not src: return _battle_sprite(profile, side)
    return {
        "media_type": "video" if _text(row.get("video")) else "image",
        "media_src": src,
        "media_scale": max(.25, min(4.0, _num(row.get("scale"), 1.0))),
        "anchor_x": max(0, min(100, _num(row.get("anchor_x"), 50))),
        "anchor_y": max(0, min(100, _num(row.get("anchor_y"), 100))),
    }


def _move_visual(move):
    visual = _dict(_dict(move).get("visual"))
    cinematic = {**_dict(_dict(move).get("cinematic_media")), **_dict(visual.get("cinematic_media"))}
    src = _text(cinematic.get("src") or move.get("cinematic_video") or move.get("cinematic_image"))
    kind = _text(cinematic.get("type")).lower()
    if src and not kind: kind = "video" if src.lower().split("?", 1)[0].endswith((".mp4", ".webm", ".ogg")) else "image"
    return {
        "pose_family": _text(visual.get("pose_family") or "").upper(),
        "cinematic_type": kind,
        "cinematic_src": src,
        "effect_asset": _text(visual.get("effect_asset")),
        "impact_asset": _text(visual.get("impact_asset")),
        "sound_asset": _text(visual.get("sound_asset")),
    }


def _attack_media(battle, move, side):
    source = _source_profile(battle, side)
    visual = _move_visual(move)
    pose_name = POSE_MAP.get(visual["pose_family"], "attack_special" if _text(move.get("damage_class")).upper() == "SPECIAL" else "attack_physical")
    media = _pose(source, pose_name, side)
    if visual["cinematic_src"]:
        media["media_type"], media["media_src"] = visual["cinematic_type"] or "image", visual["cinematic_src"]
    return {**media, "pose": pose_name, "effect_asset": visual["effect_asset"] or None, "impact_asset": visual["impact_asset"] or None, "sound_asset": visual["sound_asset"] or None}


def _enemy_declared_action(before, logs):
    enemy_id = _text(_combatant(before, "ENEMY").get("entity_id"))
    for row in logs:
        row = _dict(row); kind = _text(row.get("kind")).upper()
        if kind not in {"MOVE", "WORLD_MOVE_ORDER", "POSITION_MOVE", "POSITION_CHANGED"}: continue
        if enemy_id and _text(row.get("actor")) != enemy_id: continue
        move_id = _text(row.get("move_id"))
        if move_id: return {"type": "MOVE", "move_id": move_id}
        if kind == "POSITION_CHANGED": return {"type": "FREE_ORDER", "position_action": _text(row.get("position_action"))}
    return {}


def _action_text(battle, action, side):
    action = _dict(action); pokemon = _combatant(battle, side); name = _text(pokemon.get("name")) or "PKM"
    move_id = _text(action.get("move_id"))
    if move_id:
        move = _source_move(battle, move_id, side); move_name = _text(move.get("name")) or move_id
        target = _text(_dict(action.get("world_target")).get("name"))
        return (f"{name} USA {move_name} SOBRE {target}" if target else f"{name} USA {move_name}").upper()
    kind = _text(action.get("type")).upper()
    return f"{name} → {kind or 'ACCIÓN'}".upper()


def _reaction_info(logs):
    kinds = [] ; lines = []
    for row in logs:
        row = _dict(row); kind = _text(row.get("kind")).upper(); line = _text(row.get("text"))
        if kind in {"DODGE", "BLOCK", "REDIRECT", "INTERCEPT", "REACTION", "REACTION_RESULT", "POSITION_BLOCKED_MOVE", "MISS", "REACTION_WINDOW"}:
            kinds.append(kind)
            if line and line not in lines: lines.append(line)
    pose = "dodge" if any(k in {"DODGE", "MISS"} for k in kinds) else "defend" if any(k in {"BLOCK", "REDIRECT", "INTERCEPT", "POSITION_BLOCKED_MOVE"} for k in kinds) else "neutral"
    return pose, lines


def build_battle_shots(before_battle, after_battle, action, *, log_start=0, event="ROUND"):
    before, after, action = _dict(before_battle), _dict(after_battle), _dict(action)
    player, enemy = _combatant(before, "PLAYER"), _combatant(before, "ENEMY")
    logs = [_dict(row) for row in _list(after.get("log"))[max(0, int(log_start or 0)):]]
    move_id = _text(action.get("move_id")); move = _source_move(before, move_id, "PLAYER") if move_id else {}; profile = move_combat_profile(move) if move else {}
    enemy_action = _enemy_declared_action(before, logs); shots = []

    shots.append({
        "shot":"DECLARATION_PLAYER",
        "title":"ORDEN",
        "text":_action_text(before, action, "PLAYER"),
        **_pose(_source_profile(before,"PLAYER"),"neutral","PLAYER"),
        "duration_ms":560,
    })

    reaction_pose, reaction_lines = _reaction_info(logs)
    if move_id:
        media = _attack_media(before, move, "PLAYER")
        shots.append({
            "shot":"EXECUTION",
            "title":_action_text(before, action, "PLAYER"),
            "text":"",
            **media,
            "duration_ms":900,
        })
        world_target = _dict(action.get("world_target"))
        if world_target:
            target_name = _text(world_target.get("name")) or "OBJETIVO"
            shots.append({
                "shot":"TARGET",
                "title":target_name.upper(),
                "text":"",
                "duration_ms":480,
            })

    if reaction_lines:
        shots.append({
            "shot":"REACTION",
            "title":"REACCIÓN",
            "text":" ".join(reaction_lines[-2:]),
            **_pose(_source_profile(before,"ENEMY"),reaction_pose,"ENEMY"),
            "duration_ms":780,
        })

    resolution_lines=[]
    for row in logs:
        if _text(row.get("kind")).upper() in {"ORDER","WEGO_DECLARATION","REACTION_WINDOW"}: continue
        line=_text(row.get("text"))
        if line and line not in resolution_lines: resolution_lines.append(line)
    if resolution_lines:
        damage_hit=any(_text(row.get("kind")).upper() in {"DAMAGE","CRITICAL","WORLD_BATTLE_IMPACT"} for row in logs)
        impact_pose = "hit" if damage_hit else reaction_pose
        shots.append({
            "shot":"IMPACT",
            "title":(_text(enemy.get("name")) or "OBJETIVO").upper(),
            "text":" ".join(resolution_lines[-3:]),
            **_pose(_source_profile(after,"ENEMY"),impact_pose,"ENEMY"),
            "impact_asset":_text(_move_visual(move).get("impact_asset")) or None,
            "duration_ms":1050,
        })

    world=_dict(after.get("last_world_resolution")); scene_reaction=_dict(world.get("scene_reaction"))
    if world.get("executed") or scene_reaction.get("reacted"):
        target=_text(world.get("target_name")) or _text(_dict(action.get("world_target")).get("name")) or "ENTORNO"
        consequence_text = _text(world.get("text")) or _text(scene_reaction.get("text")) or "EL ENTORNO CAMBIA COMO CONSECUENCIA DE LA ACCIÓN."
        shots.append({
            "shot":"CONSEQUENCE",
            "title":target.upper(),
            "text":consequence_text,
            "duration_ms":1000,
        })

    if enemy_action:
        enemy_move = _source_move(before, enemy_action.get("move_id"), "ENEMY") if enemy_action.get("move_id") else {}
        media = _attack_media(before, enemy_move, "ENEMY") if enemy_move else _pose(_source_profile(before,"ENEMY"),"neutral","ENEMY")
        shots.append({
            "shot":"DECLARATION_ENEMY",
            "title":"RIVAL",
            "text":_action_text(before,enemy_action,"ENEMY"),
            **media,
            "duration_ms":620,
        })

    if _text(after.get("status")).upper()=="COMPLETE":
        loser="ENEMY" if _text(after.get("outcome")).upper()=="PLAYER_WIN" else "PLAYER" if _text(after.get("outcome")).upper()=="PLAYER_LOSS" else None
        media=_pose(_source_profile(after,loser),"ko",loser) if loser else {}
        shots.append({"shot":"END","title":"FIN DEL COMBATE","text":_text(after.get("outcome")),**media,"duration_ms":1100})

    return {
        "battle_id":after.get("battle_id") or before.get("battle_id"),
        "event":_text(event).upper() or "ROUND",
        "turn":before.get("turn") or after.get("turn") or 1,
        "action":deepcopy(action),
        "enemy_action":deepcopy(enemy_action),
        "move_profile":profile,
        "shots":shots,
        "build":SHOT_DIRECTOR_BUILD,
    }


def emit_battle_shots(actor,before_battle,after_battle,action,*,log_start=0,event="ROUND"):
    packet=build_battle_shots(before_battle,after_battle,action,log_start=log_start,event=event)
    if actor and packet.get("shots"):
        actor.msg(pokerol_battle_shots=((packet,), {"build": SHOT_DIRECTOR_BUILD}))
        return True
    return False
