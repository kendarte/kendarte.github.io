import base64
import json

from evennia import Command
from evennia.utils import logger


PLAYER_ANCHOR_BUILD = "0.5.0-character-room-player-layouts"


def _clean(value):
    return str(value or "").strip()


def _number(value, default, minimum, maximum):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)
    return max(float(minimum), min(float(maximum), value))


def _decode_payload(raw):
    value = _clean(raw)
    if not value:
        raise ValueError("payload vacío")
    value += "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        data = json.loads(decoded)
    except Exception as exc:
        raise ValueError("payload inválido") from exc
    if not isinstance(data, dict):
        raise ValueError("payload inválido")
    return data


def _refresh(caller):
    try:
        from commands.pokerol_ui_runtime_commands import emit_room_snapshot
        emit_room_snapshot(caller, visible_text=False)
    except Exception:
        pass


def _layout_from(data):
    if bool(data.get("reset")):
        return {"x": 11.0, "y": 94.0, "scale": 1.0}
    return {
        "x": _number(data.get("x"), 11, 1, 99),
        "y": _number(data.get("y"), 94, 0, 500),
        "scale": _number(data.get("scale"), 1, 0.35, 3),
    }


def _next_revision(caller):
    try:
        revision = int(getattr(caller.db, "pokerol_player_state_revision", 0) or 0) + 1
    except (TypeError, ValueError):
        revision = 1
    caller.db.pokerol_player_state_revision = revision
    return revision


def _room_layout_key(room):
    return str(int(room.id))


def _room_layouts(caller):
    raw = getattr(caller.db, "pokerol_player_room_layouts", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _save_character_room_layout(caller, room, layout):
    layouts = _room_layouts(caller)
    key = _room_layout_key(room)
    layouts[key] = dict(layout)
    caller.db.pokerol_player_room_layouts = layouts
    return key


class CmdPokerolEditorPlayerState(Command):
    """Save PLAYER position, scale and anchor state in one authoritative transaction."""

    key = "pokerol-editor-player-state"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        room = getattr(self.caller, "location", None)
        if not room:
            self.caller.msg(
                pokerol_asset_result=(({
                    "status": "ERROR",
                    "message": "No hay cuarto actual.",
                    "kind": "player_state",
                },), {})
            )
            return

        try:
            data = _decode_payload(self.args)
            anchored = bool(data.get("anchored"))
            layout = _layout_from(data)
            try:
                seq = int(data.get("seq") or 0)
            except (TypeError, ValueError):
                seq = 0
        except Exception as exc:
            self.caller.msg(
                pokerol_asset_result=(({
                    "status": "ERROR",
                    "message": "No se pudo guardar PLAYER: {}".format(exc),
                    "kind": "player_state",
                },), {})
            )
            return

        revision = _next_revision(self.caller)
        room_layout = dict(layout)
        room_layout["revision"] = revision
        room_key = _save_character_room_layout(self.caller, room, room_layout)

        visual_state = {
            "x": layout["x"],
            "y": layout["y"],
            "scale": layout["scale"],
            "anchored": anchored,
            "room_dbref": int(room.id),
            "room_key": room_key,
            "revision": revision,
        }

        # PLAYER layout belongs to the character, never to the shared Room.
        # This prevents Chumeco/Azulith (or any two trainers) from overwriting
        # each other's position and scale in the same location.
        self.caller.db.pokerol_player_visual_state = dict(visual_state)
        self.caller.db.pokerol_player_anchor_enabled = anchored
        if anchored:
            self.caller.db.pokerol_player_anchor_layout = dict(room_layout)

        logger.log_info(
            "[POKEROL PLAYER SAVE] caller={} room=#{} key={} x={:.3f} y={:.3f} scale={:.3f} anchored={} rev={} scope={}".format(
                self.caller.key,
                int(room.id),
                room_key,
                layout["x"],
                layout["y"],
                layout["scale"],
                anchored,
                revision,
                "PLAYER_ANCHOR" if anchored else "PLAYER_ROOM",
            )
        )

        packet = {
            "status": "PLAYER_STATE_SAVED",
            "build": PLAYER_ANCHOR_BUILD,
            "seq": seq,
            "revision": revision,
            "anchored": anchored,
            "layout": dict(room_layout),
            "visual_state": dict(visual_state),
            "room_dbref": int(room.id),
            "room_key": room_key,
            "scope": "PLAYER_ANCHOR" if anchored else "PLAYER_ROOM",
        }
        self.caller.msg(pokerol_asset_result=((packet,), {}))
        _refresh(self.caller)


class CmdPokerolEditorPlayerAnchor(Command):
    key = "pokerol-editor-player-anchor"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            data = _decode_payload(self.args)
        except Exception as exc:
            self.caller.msg("No se pudo guardar ANCLAR: {}".format(exc))
            return

        enabled = bool(data.get("enabled"))
        self.caller.db.pokerol_player_anchor_enabled = enabled
        room = getattr(self.caller, "location", None)

        if enabled:
            revision = _next_revision(self.caller)
            layout = {
                "x": _number(data.get("x"), 11, 1, 99),
                "y": _number(data.get("y"), 94, 0, 500),
                "scale": _number(data.get("scale"), 1, 0.35, 3),
                "revision": revision,
            }
            self.caller.db.pokerol_player_anchor_layout = dict(layout)
            room_key = _save_character_room_layout(self.caller, room, layout) if room else ""
            self.caller.db.pokerol_player_visual_state = {
                "x": layout["x"],
                "y": layout["y"],
                "scale": layout["scale"],
                "anchored": True,
                "room_dbref": int(room.id) if room else None,
                "room_key": room_key,
                "revision": revision,
            }
        elif bool(data.get("clear")):
            self.caller.db.pokerol_player_anchor_layout = None

        packet = {
            "status": "PLAYER_ANCHOR_SAVED",
            "build": PLAYER_ANCHOR_BUILD,
            "enabled": enabled,
            "layout": dict(getattr(self.caller.db, "pokerol_player_anchor_layout", None) or {}),
        }
        self.caller.msg(pokerol_asset_result=((packet,), {}))
        _refresh(self.caller)
