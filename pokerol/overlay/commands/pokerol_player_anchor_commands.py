import base64
import json

from evennia import Command


PLAYER_ANCHOR_BUILD = "0.1.0-global-player-anchor"


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
