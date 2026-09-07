import base64
import json

from evennia import Command


PLAYER_ANCHOR_BUILD = "0.2.0-authoritative-player-state"


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

        # Always save the current Room layout too. This means disabling ANCLAR
        # never jumps the player back to an older Room position.
        room.db.pokerol_player_layout = dict(layout)
        self.caller.db.pokerol_player_anchor_enabled = anchored
        if anchored:
            self.caller.db.pokerol_player_anchor_layout = dict(layout)

        packet = {
            "status": "PLAYER_STATE_SAVED",
            "build": PLAYER_ANCHOR_BUILD,
            "seq": seq,
            "anchored": anchored,
            "layout": dict(layout),
            "room_dbref": int(room.id),
            "scope": "PLAYER_ANCHOR" if anchored else "ROOM",
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

        if enabled:
            self.caller.db.pokerol_player_anchor_layout = {
                "x": _number(data.get("x"), 11, 1, 99),
                "y": _number(data.get("y"), 94, 0, 500),
                "scale": _number(data.get("scale"), 1, 0.35, 3),
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
