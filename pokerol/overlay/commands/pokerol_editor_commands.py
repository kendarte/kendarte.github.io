import base64
import json
from uuid import uuid4

from evennia import Command, create_object


MAX_NAME = 96
MAX_DESC = 6000
MAX_SPRITE = 1500000


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


def _result(caller, status, message, **extra):
    packet = {"status": status, "message": message}
    packet.update(extra)
    caller.msg(pokerol_editor_result=((packet,), {}))
    return packet


def _refresh(caller):
    try:
        from commands.pokerol_ui_runtime_commands import emit_room_snapshot
        emit_room_snapshot(caller, visible_text=False)
    except Exception:
        pass


def _editable_target(caller, dbref):
    location = getattr(caller, "location", None)
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    if int(getattr(location, "id", -1)) == wanted:
        return location
    for obj in list(getattr(location, "contents", []) or []):
        if int(getattr(obj, "id", -1)) == wanted:
            return obj
    for exit_obj in list(getattr(location, "exits", []) or []):
        if int(getattr(exit_obj, "id", -1)) == wanted:
            return exit_obj
    return None


def _valid_sprite(value):
    sprite = _clean(value)
    if not sprite:
        return ""
    if len(sprite) > MAX_SPRITE:
        raise ValueError("sprite demasiado grande")
    if not sprite.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,", "data:image/gif;base64,")):
        raise ValueError("formato de sprite no permitido")
    return sprite


class CmdPokerolEditorUpdateEntity(Command):
    key = "pokerol-editor-update"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            data = _decode_payload(self.args)
        except ValueError as exc:
            _result(self.caller, "ERROR", str(exc))
            return

        target = _editable_target(self.caller, data.get("dbref"))
        if not target:
            _result(self.caller, "ERROR", "El hotspot ya no pertenece a este cuarto.")
            return

        changed = []
        name = _clean(data.get("name"), MAX_NAME)
        if name and name != str(target.key):
            target.key = name
            changed.append("name")

        if "description" in data:
            desc = _clean(data.get("description"), MAX_DESC)
            if str(getattr(target.db, "desc", "") or "") != desc:
                target.db.desc = desc
                changed.append("description")

        for field, low, high in (("scene_x", 0, 100), ("scene_y", 0, 100), ("scene_scale", 0.2, 4.0)):
            if field not in data:
                continue
            value = _number(data.get(field), None, low, high)
            if value is not None and getattr(target.db, field, None) != value:
                setattr(target.db, field, value)
                changed.append(field)

        if bool(data.get("clear_sprite")):
            if _clean(getattr(target.db, "scene_sprite", "")):
                target.db.scene_sprite = ""
                changed.append("scene_sprite")
        elif "scene_sprite" in data:
            try:
                sprite = _valid_sprite(data.get("scene_sprite"))
            except ValueError as exc:
                _result(self.caller, "ERROR", str(exc))
                return
            if sprite and _clean(getattr(target.db, "scene_sprite", "")) != sprite:
                target.db.scene_sprite = sprite
                changed.append("scene_sprite")

        if bool(getattr(target.db, "is_npc", False)) and "dialogue_greeting" in data:
            greeting = _clean(data.get("dialogue_greeting"), 2000)
            if str(getattr(target.db, "dialogue_greeting", "") or "") != greeting:
                target.db.dialogue_greeting = greeting
                changed.append("dialogue_greeting")

        _result(
            self.caller,
            "UPDATED",
            "Cambios guardados en el World Engine.",
            dbref=int(target.id),
            kind="NPC" if bool(getattr(target.db, "is_npc", False)) else ("EXIT" if getattr(target, "destination", None) else "ROOM" if target is getattr(self.caller, "location", None) else "OBJECT"),
            changed=changed,
        )
        _refresh(self.caller)


class CmdPokerolEditorCreateRoom(Command):
    key = "pokerol-editor-create-room"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        current = getattr(self.caller, "location", None)
        if not current:
            _result(self.caller, "ERROR", "No hay un cuarto actual desde el cual conectar el nuevo.")
            return
        try:
            data = _decode_payload(self.args)
        except ValueError as exc:
            _result(self.caller, "ERROR", str(exc))
            return

        name = _clean(data.get("name"), MAX_NAME)
        if not name:
            _result(self.caller, "ERROR", "El nuevo cuarto necesita nombre.")
            return
        desc = _clean(data.get("description"), MAX_DESC)
        forward_name = _clean(data.get("exit_name"), MAX_NAME) or ("Ir a " + name)
        return_name = _clean(data.get("return_exit_name"), MAX_NAME) or ("Volver a " + str(current.key))

        room = create_object("typeclasses.rooms.Room", key=name)
        room.db.room_id = "ROOM-USER-" + uuid4().hex[:12].upper()
        room.db.desc = desc
        room.db.canon_status = "prototype"

        forward = create_object("typeclasses.exits.Exit", key=forward_name, location=current, destination=room)
        forward.db.exit_id = "EXIT-USER-" + uuid4().hex[:12].upper()
        forward.db.canon_status = "prototype"

        backward = create_object("typeclasses.exits.Exit", key=return_name, location=room, destination=current)
        backward.db.exit_id = "EXIT-USER-" + uuid4().hex[:12].upper()
        backward.db.canon_status = "prototype"

        _result(
            self.caller,
            "ROOM_CREATED",
            "Cuarto creado y conectado al World Engine.",
            room_dbref=int(room.id),
            room_id=str(room.db.room_id),
            room_name=str(room.key),
            exit_dbref=int(forward.id),
            exit_name=str(forward.key),
        )
        _refresh(self.caller)
