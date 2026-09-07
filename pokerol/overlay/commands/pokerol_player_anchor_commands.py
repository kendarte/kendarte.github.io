import base64
import json

from evennia import Command
from evennia.utils import logger

from services.pokerol_global_player_visual import (
    get_global_player_visual,
    save_global_player_visual,
)


PLAYER_ANCHOR_BUILD = "1.0.0-global-persistent-player-transform"


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


def _room_layout_key(room):
    return str(int(room.id))


class CmdPokerolEditorPlayerState(Command):
    """Save global PLAYER position, scale and anchor state in one transaction."""

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
            if data.get("character_dbref") is not None and int(data["character_dbref"]) != int(self.caller.id):
                raise ValueError("El personaje activo ha cambiado; vuelve a abrir PLAYER.")
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

        saved = save_global_player_visual({
            "x": layout["x"],
            "y": layout["y"],
            "scale": layout["scale"],
            "anchored": anchored,
        }, actor=self.caller)
        revision = int(saved.get("revision", 0) or 0)
        room_layout = {
            "x": saved["x"],
            "y": saved["y"],
            "scale": saved["scale"],
            "revision": revision,
        }
        room_key = _room_layout_key(room)

        logger.log_info(
            "[POKEROL PLAYER GLOBAL SAVE] caller={} room=#{} key={} x={:.3f} y={:.3f} scale={:.3f} anchored={} revision={} source={}".format(
                self.caller.key,
                int(room.id),
                room_key,
                saved["x"],
                saved["y"],
                saved["scale"],
                saved["anchored"],
                revision,
                "GLOBAL_PLAYER_VISUAL_STATE",
            )
        )

        packet = {
            "status": "PLAYER_STATE_SAVED",
            "build": PLAYER_ANCHOR_BUILD,
            "seq": seq,
            "revision": revision,
            "anchored": bool(saved["anchored"]),
            "layout": dict(room_layout),
            "visual_state": dict(saved),
            "room_dbref": int(room.id),
            "room_key": room_key,
            "scope": "GLOBAL_PLAYER_VISUAL_STATE",
            "character_dbref": int(self.caller.id),
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

        current = get_global_player_visual(self.caller, migrate_legacy=True)
        enabled = bool(data.get("enabled"))
        saved = save_global_player_visual({
            "x": _number(data.get("x"), current.get("x", 11), 1, 99),
            "y": _number(data.get("y"), current.get("y", 94), 0, 500),
            "scale": _number(data.get("scale"), current.get("scale", 1), 0.35, 3),
            "anchored": enabled,
        }, actor=self.caller)

        logger.log_info(
            "[POKEROL PLAYER GLOBAL SAVE] caller={} x={} y={} scale={} anchored={} revision={} source=GLOBAL_PLAYER_VISUAL_STATE".format(
                self.caller.key,
                saved["x"],
                saved["y"],
                saved["scale"],
                saved["anchored"],
                saved["revision"],
            )
        )

        packet = {
            "status": "PLAYER_ANCHOR_SAVED",
            "build": PLAYER_ANCHOR_BUILD,
            "enabled": bool(saved["anchored"]),
            "layout": {
                "x": saved["x"],
                "y": saved["y"],
                "scale": saved["scale"],
                "revision": saved["revision"],
            },
            "scope": "GLOBAL_PLAYER_VISUAL_STATE",
        }
        self.caller.msg(pokerol_asset_result=((packet,), {}))
        _refresh(self.caller)
