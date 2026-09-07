from evennia import Command

from commands.siza_ui_runtime_commands import (
    _room_text_block,
    context_action_packet as _legacy_context_action_packet,
    room_snapshot_packet as _legacy_room_snapshot_packet,
)
from services.pokerol_tutorial_engine import (
    OAK_NPC_ID,
    RIVAL_NPC_ID,
    ensure_tutorial_world,
    tutorial_context_actions,
)

POKEROL_UI_RUNTIME_BUILD = "0.7.0-persistent-project-assets"


def _stamp(packet):
    packet = dict(packet or {})
    packet["build"] = POKEROL_UI_RUNTIME_BUILD
    packet["game"] = "POKEROL"
    return packet


def _db_value(obj, name, default=None):
    try:
        value = getattr(obj.db, name, default)
    except Exception:
        return default
    return default if value is None else value


def _scene_metadata(obj):
    return {
        "scene_x": _db_value(obj, "scene_x", None),
        "scene_y": _db_value(obj, "scene_y", None),
        "scene_scale": _db_value(obj, "scene_scale", 1.0),
        "scene_sprite": str(_db_value(obj, "scene_sprite", "") or ""),
    }


def _player_metadata(actor, location):
    room_key = str(_db_value(location, "room_id", "") or f"DBREF:{int(location.id)}")
    layouts = _db_value(actor, "pokerol_player_layouts", {}) or {}
    if not isinstance(layouts, dict):
        layouts = {}
    layout = layouts.get(room_key) or {}
    return {
        "room_key": room_key,
        "scene_x": layout.get("x", 11),
        "scene_y": layout.get("y", 94),
        "scene_scale": layout.get("scale", 1),
        "scene_sprite": str(_db_value(actor, "scene_sprite", "") or ""),
    }


def _custom_hotspots(location):
    rows = []
    for raw in list(_db_value(location, "pokerol_custom_hotspots", []) or []):
        if not isinstance(raw, dict):
            continue
        rows.append({
            "id": str(raw.get("id") or ""),
            "name": str(raw.get("name") or "HOTSPOT"),
            "command": str(raw.get("command") or "mirar"),
            "x": raw.get("x", 50),
            "y": raw.get("y", 20),
            "description": str(raw.get("description") or ""),
            "scale": raw.get("scale", 1),
            "sprite": str(raw.get("sprite") or ""),
        })
    return rows


def _enrich_world_rows(actor, packet):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return packet

    packet["room_dbref"] = int(location.id)
    packet["room_editor"] = {
        "dbref": int(location.id),
        "name": str(location.key),
        "description": str(_db_value(location, "desc", "") or packet.get("room_description") or ""),
    }
    scene_image = _db_value(location, "scene_image", {})
    if isinstance(scene_image, dict):
        packet["scene_image"] = str(scene_image.get("src") or "")
    elif scene_image:
        packet["scene_image"] = str(scene_image)
    else:
        packet["scene_image"] = ""

    packet["custom_hotspots"] = _custom_hotspots(location)
    packet["player_editor"] = _player_metadata(actor, location)

    local = {}
    for obj in list(getattr(location, "contents", []) or []):
        if getattr(obj, "id", None) is not None:
            local[int(obj.id)] = obj

    for key in ("visible_npcs", "people", "visible_objects", "objects"):
        rows = list(packet.get(key) or [])
        enriched = []
        for raw in rows:
            row = dict(raw or {})
            try:
                dbref = int(row.get("dbref"))
            except (TypeError, ValueError):
                dbref = None
            obj = local.get(dbref)
            if obj:
                row.update(_scene_metadata(obj))
                row["description"] = str(_db_value(obj, "desc", "") or row.get("description") or "")
                row["editor_kind"] = "NPC" if bool(_db_value(obj, "is_npc", False)) else "OBJECT"
                if bool(_db_value(obj, "is_npc", False)):
                    row["dialogue_greeting"] = str(_db_value(obj, "dialogue_greeting", "") or "")
            enriched.append(row)
        packet[key] = enriched

    exit_objects = list(getattr(location, "exits", []) or [])
    enriched_exits = []
    for raw in list(packet.get("exits") or []):
        row = dict(raw or {})
        exit_obj = None
        exit_id = str(row.get("exit_id") or "").strip()
        for candidate in exit_objects:
            if exit_id and str(_db_value(candidate, "exit_id", "") or "").strip() == exit_id:
                exit_obj = candidate
                break
            if str(candidate.key) == str(row.get("name") or ""):
                exit_obj = candidate
        if exit_obj:
            row["dbref"] = int(exit_obj.id)
            row["description"] = str(_db_value(exit_obj, "desc", "") or "")
            row["editor_kind"] = "EXIT"
            row.update(_scene_metadata(exit_obj))
        enriched_exits.append(row)
    packet["exits"] = enriched_exits
    packet["editor_enabled"] = True
    return packet


def _tutorial_target_names(actor):
    room = getattr(actor, "location", None) if actor else None
    names = set()
    if not room:
        return names
    for obj in list(getattr(room, "contents", []) or []):
        if str(_db_value(obj, "npc_id", "") or "") in {OAK_NPC_ID, RIVAL_NPC_ID}:
            names.add(str(obj.key))
    return names


def room_snapshot_packet(actor):
    ensure_tutorial_world(actor)
    return _enrich_world_rows(actor, _stamp(_legacy_room_snapshot_packet(actor)))


def context_action_packet(actor):
    ensure_tutorial_world(actor)
    packet = _stamp(_legacy_context_action_packet(actor))
    actions = [dict(row or {}) for row in list(packet.get("actions") or [])]
    tutorial_rows = tutorial_context_actions(actor)
    tutorial_targets = _tutorial_target_names(actor)
    if tutorial_targets:
        actions = [
            row
            for row in actions
            if not (
                str(row.get("kind") or "").upper() == "INTERACTION"
                and str(row.get("target") or "") in tutorial_targets
            )
        ]
    packet["actions"] = tutorial_rows + actions
    return packet


def emit_room_snapshot(actor, *, visible_text=False):
    """Publish POKEROL-native room state to the web client."""
    packet = room_snapshot_packet(actor)
    actions = context_action_packet(actor)
    actor.msg(pokerol_room_snapshot=((packet,), {}))
    actor.msg(pokerol_context_actions=((actions,), {}))
    if visible_text:
        actor.msg(_room_text_block(packet))
    return packet


class CmdPokerolRoomState(Command):
    key = "pokerol-room-state"
    aliases = ("estado-escena",)
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        emit_room_snapshot(self.caller, visible_text=False)


class CmdPokerolUiContext(Command):
    key = "pokerol-ui-context"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        self.caller.msg(pokerol_context_actions=((context_action_packet(self.caller),), {}))
