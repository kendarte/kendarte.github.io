import base64
import json

from evennia import Command

from services.pokerol_event_editor_service import (
    EVENT_EDITOR_BUILD,
    list_room_events,
    reset_or_delete_room_event,
    save_room_event,
)


def _clean(value):
    return str(value or "").strip()


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


def _room_packet(caller):
    room = getattr(caller, "location", None)
    if not room:
        return {
            "build": EVENT_EDITOR_BUILD,
            "room_dbref": None,
            "room_id": "",
            "room_name": "",
            "events": [],
        }
    return {
        "build": EVENT_EDITOR_BUILD,
        "room_dbref": int(room.id),
        "room_id": str(getattr(room.db, "room_id", "") or ""),
        "room_name": str(room.key),
        "events": list_room_events(room),
    }


def _emit_state(caller):
    packet = _room_packet(caller)
    caller.msg(pokerol_event_editor_state=((packet,), {}))
    return packet


def _emit_result(caller, status, message, **extra):
    packet = {"build": EVENT_EDITOR_BUILD, "status": status, "message": message}
    packet.update(extra)
    caller.msg(pokerol_event_editor_result=((packet,), {}))
    return packet


class CmdPokerolEventEditorList(Command):
    key = "pokerol-event-editor-list"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        _emit_state(self.caller)


class CmdPokerolEventEditorSave(Command):
    key = "pokerol-event-editor-save"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        room = getattr(self.caller, "location", None)
        if not room:
            _emit_result(self.caller, "ERROR", "No hay cuarto activo.")
            return
        try:
            data = _decode_payload(self.args)
            event = save_room_event(room, data)
        except ValueError as exc:
            _emit_result(self.caller, "ERROR", str(exc))
            return
        except Exception as exc:
            _emit_result(self.caller, "ERROR", f"No se pudo guardar el evento: {exc}")
            return

        _emit_result(
            self.caller,
            "SAVED",
            "Evento guardado en el World Engine.",
            event_id=str((event or {}).get("id") or ""),
            source=str((event or {}).get("source") or ""),
        )
        _emit_state(self.caller)

        try:
            from commands.pokerol_ui_runtime_commands import emit_room_snapshot
            emit_room_snapshot(self.caller, visible_text=False)
        except Exception:
            pass


class CmdPokerolEventEditorDelete(Command):
    key = "pokerol-event-editor-delete"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        room = getattr(self.caller, "location", None)
        if not room:
            _emit_result(self.caller, "ERROR", "No hay cuarto activo.")
            return
        try:
            data = _decode_payload(self.args)
            event_id = _clean(data.get("id"))
            if not event_id:
                raise ValueError("Falta el id del evento.")
            result = reset_or_delete_room_event(room, event_id)
        except ValueError as exc:
            _emit_result(self.caller, "ERROR", str(exc))
            return
        except Exception as exc:
            _emit_result(self.caller, "ERROR", f"No se pudo modificar el evento: {exc}")
            return

        status = str(result.get("status") or "UPDATED")
        message = "Evento restaurado a sus valores del sistema." if status == "RESET" else "Evento borrado del cuarto."
        _emit_result(self.caller, status, message, event_id=event_id)
        _emit_state(self.caller)
