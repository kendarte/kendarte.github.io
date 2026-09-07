import base64
import json
import re

from evennia import Command


MAX_HOTSPOT_GEOMETRY = 240


def _clean(value, limit=None):
    text = str(value or "").strip()
    return text[:limit] if limit else text


def _number(value, default=None, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _safe_key(value):
    value = _clean(value, 96)
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value or "") else ""


def _decode_payload(raw):
    value = _clean(raw)
    if not value:
        raise ValueError("payload vacío")
    value += "=" * (-len(value) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise ValueError("payload inválido") from exc
    if not isinstance(data, dict):
        raise ValueError("payload inválido")
    return data


def _result(caller, status, message, **extra):
    packet = {"status": status, "message": message}
    packet.update(extra)
    caller.msg(pokerol_asset_result=((packet,), {}))


def _refresh(caller):
    try:
        from commands.pokerol_ui_runtime_commands import emit_room_snapshot
        emit_room_snapshot(caller, visible_text=False)
    except Exception:
        pass


class CmdPokerolEditorHotspotGeometry(Command):
    key = "pokerol-editor-hotspot-geometry"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        room = getattr(self.caller, "location", None)
        if not room:
            _result(self.caller, "ERROR", "No hay cuarto actual.")
            return
        try:
            data = _decode_payload(self.args)
            incoming = data.get("geometry") or {}
            if not isinstance(incoming, dict) or len(incoming) > MAX_HOTSPOT_GEOMETRY:
                raise ValueError("Geometría de hotspots inválida.")
            geometry = {}
            for raw_key, raw in incoming.items():
                key = _safe_key(raw_key)
                if not key or not isinstance(raw, dict):
                    continue
                geometry[key] = {
                    "width": _number(raw.get("width"), 80, 12, 600),
                    "height": _number(raw.get("height"), 80, 12, 500),
                    "hidden": bool(raw.get("hidden", False)),
                }
            room.db.pokerol_hotspot_geometry = geometry
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return

        _result(
            self.caller,
            "HOTSPOT_GEOMETRY_SAVED",
            "Tamaño y estado de hotspots guardados en el proyecto.",
            count=len(geometry),
            room_dbref=int(room.id),
        )
        _refresh(self.caller)
