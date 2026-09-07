import base64
import json
import os
import re
import shutil
from pathlib import Path
from uuid import uuid4

from evennia import Command


ASSET_ROOT = Path(os.environ.get("POKEROL_ASSET_ROOT", "/data/pokerol_assets"))
PUBLIC_PREFIX = "/pokerol-assets/"
MAX_ASSET_BYTES = 8 * 1024 * 1024
MAX_CUSTOM_HOTSPOTS = 80
MAX_ACTION_HOTSPOTS = 160
MIME_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


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
    caller.msg(pokerol_asset_result=((packet,), {}))
    return packet


def _refresh(caller):
    try:
        from commands.pokerol_ui_runtime_commands import emit_room_snapshot
        emit_room_snapshot(caller, visible_text=False)
    except Exception:
        pass


def _uploads(caller):
    uploads = getattr(caller.ndb, "pokerol_asset_uploads", None)
    if not isinstance(uploads, dict):
        uploads = {}
        caller.ndb.pokerol_asset_uploads = uploads
    return uploads


def _local_target(caller, dbref):
    location = getattr(caller, "location", None)
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    if int(getattr(location, "id", -1)) == wanted:
        return location
    for obj in list(getattr(location, "contents", []) or []) + list(getattr(location, "exits", []) or []):
        if int(getattr(obj, "id", -1)) == wanted:
            return obj
    return None


def _safe_hotspot_id(value):
    value = _clean(value, 96)
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value or "") else ""


def _asset_slot(caller, kind, dbref=None, hotspot_id=None):
    kind = _clean(kind).lower()
    if kind == "room_background":
        target = getattr(caller, "location", None)
        if not target:
            raise ValueError("No hay cuarto actual.")
        return target, "scene_image", "rooms", int(target.id), ""
    if kind == "entity_sprite":
        target = _local_target(caller, dbref)
        if not target:
            raise ValueError("El hotspot ya no pertenece a este cuarto.")
        return target, "scene_sprite", "entities", int(target.id), ""
    if kind == "player_sprite":
        return caller, "scene_sprite", "players", int(caller.id), ""
    if kind == "player_fullbody":
        return caller, "profile_fullbody_image", "players", int(caller.id), ""
    if kind == "custom_hotspot_sprite":
        room = getattr(caller, "location", None)
        hid = _safe_hotspot_id(hotspot_id)
        if not room or not hid:
            raise ValueError("Hotspot personalizado inválido.")
        rows = list(getattr(room.db, "pokerol_custom_hotspots", None) or [])
        if not any(str(row.get("id") or "") == hid for row in rows if isinstance(row, dict)):
            raise ValueError("Ese hotspot personalizado no existe en este cuarto.")
        return room, "pokerol_custom_hotspots", "hotspots", int(room.id), hid
    raise ValueError("Tipo de asset no permitido.")


def _current_url(target, attr, hotspot_id=""):
    if hotspot_id:
        rows = list(getattr(target.db, attr, None) or [])
        for row in rows:
            if isinstance(row, dict) and str(row.get("id") or "") == hotspot_id:
                return _clean(row.get("sprite"))
        return ""
    return _clean(getattr(target.db, attr, ""))


def _set_url(target, attr, url, hotspot_id=""):
    if hotspot_id:
        rows = [dict(row) for row in list(getattr(target.db, attr, None) or []) if isinstance(row, dict)]
        found = False
        for row in rows:
            if str(row.get("id") or "") == hotspot_id:
                row["sprite"] = url
                found = True
                break
        if not found:
            raise ValueError("Ese hotspot personalizado no existe en este cuarto.")
        setattr(target.db, attr, rows)
    else:
        setattr(target.db, attr, url)


def _delete_managed_asset(url):
    url = _clean(url)
    if not url.startswith(PUBLIC_PREFIX):
        return
    rel = url[len(PUBLIC_PREFIX):].lstrip("/")
    candidate = (ASSET_ROOT / rel).resolve()
    root = ASSET_ROOT.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return
    if candidate.is_file():
        try:
            candidate.unlink()
        except OSError:
            pass


def _ensure_public_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o755)
    except OSError:
        pass
    return path


def _folder_for(folder):
    _ensure_public_dir(ASSET_ROOT)
    return _ensure_public_dir(ASSET_ROOT / folder)


class CmdPokerolAssetBegin(Command):
    key = "pokerol-asset-begin"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            data = _decode_payload(self.args)
            mime = _clean(data.get("mime")).lower()
            if mime not in MIME_EXT:
                raise ValueError("Formato de imagen no permitido.")
            size = int(data.get("size") or 0)
            if size <= 0 or size > MAX_ASSET_BYTES:
                raise ValueError("La imagen supera el límite de 8 MB o está vacía.")
            kind = _clean(data.get("kind")).lower()
            dbref = data.get("dbref")
            hotspot_id = _safe_hotspot_id(data.get("hotspot_id"))
            target, attr, folder, target_id, hid = _asset_slot(self.caller, kind, dbref, hotspot_id)
        except (ValueError, TypeError) as exc:
            _result(self.caller, "ERROR", str(exc))
            return

        _ensure_public_dir(ASSET_ROOT)
        tmp_dir = _ensure_public_dir(ASSET_ROOT / ".tmp")
        token = uuid4().hex
        temp_path = tmp_dir / (token + ".part")
        temp_path.write_bytes(b"")
        _uploads(self.caller)[token] = {
            "kind": kind,
            "mime": mime,
            "size": size,
            "received": 0,
            "next_index": 0,
            "temp": str(temp_path),
            "attr": attr,
            "folder": folder,
            "target_id": target_id,
            "dbref": int(getattr(target, "id", target_id)),
            "hotspot_id": hid,
        }
        _result(self.caller, "UPLOAD_READY", "Carga preparada.", token=token, chunk_size=32768)


class CmdPokerolAssetChunk(Command):
    key = "pokerol-asset-chunk"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            data = _decode_payload(self.args)
            token = _clean(data.get("token"), 64)
            upload = _uploads(self.caller).get(token)
            if not upload:
                raise ValueError("La carga ya no existe.")
            index = int(data.get("index"))
            if index != int(upload.get("next_index", 0)):
                raise ValueError("Chunk fuera de orden.")
            raw = base64.b64decode(str(data.get("data") or ""), validate=True)
            if not raw or len(raw) > 40000:
                raise ValueError("Chunk inválido.")
            if int(upload.get("received", 0)) + len(raw) > int(upload.get("size", 0)):
                raise ValueError("La carga excede el tamaño declarado.")
            with open(upload["temp"], "ab") as handle:
                handle.write(raw)
            upload["received"] = int(upload.get("received", 0)) + len(raw)
            upload["next_index"] = index + 1
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return
        _result(self.caller, "CHUNK_OK", "Chunk guardado.", token=token, index=index, received=upload["received"])


class CmdPokerolAssetFinish(Command):
    key = "pokerol-asset-finish"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        token = ""
        try:
            data = _decode_payload(self.args)
            token = _clean(data.get("token"), 64)
            upload = _uploads(self.caller).get(token)
            if not upload:
                raise ValueError("La carga ya no existe.")
            if int(upload.get("received", 0)) != int(upload.get("size", 0)):
                raise ValueError("La imagen está incompleta.")
            kind = upload["kind"]
            target, attr, folder, target_id, hid = _asset_slot(
                self.caller, kind, upload.get("dbref"), upload.get("hotspot_id")
            )
            ext = MIME_EXT[upload["mime"]]
            final_dir = _folder_for(folder)
            filename = f"{folder.rstrip('s')}-{target_id}-{uuid4().hex[:12]}{ext}"
            final_path = final_dir / filename
            shutil.move(upload["temp"], final_path)
            try:
                final_path.chmod(0o644)
            except OSError:
                pass
            url = PUBLIC_PREFIX + folder + "/" + filename
            old_url = _current_url(target, attr, hid)
            _set_url(target, attr, url, hid)
            _delete_managed_asset(old_url)
            del _uploads(self.caller)[token]
        except Exception as exc:
            upload = _uploads(self.caller).pop(token, None) if token else None
            if upload:
                try:
                    Path(upload.get("temp", "")).unlink(missing_ok=True)
                except Exception:
                    pass
            _result(self.caller, "ERROR", str(exc))
            return

        _result(
            self.caller,
            "UPLOAD_DONE",
            "Imagen guardada en el proyecto.",
            token=token,
            kind=kind,
            url=url,
            dbref=int(getattr(target, "id", target_id)),
            hotspot_id=hid,
        )
        _refresh(self.caller)


class CmdPokerolAssetClear(Command):
    key = "pokerol-asset-clear"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            data = _decode_payload(self.args)
            kind = _clean(data.get("kind")).lower()
            target, attr, _folder, target_id, hid = _asset_slot(
                self.caller, kind, data.get("dbref"), data.get("hotspot_id")
            )
            old_url = _current_url(target, attr, hid)
            _set_url(target, attr, "", hid)
            _delete_managed_asset(old_url)
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return
        _result(self.caller, "ASSET_CLEARED", "Imagen quitada del proyecto.", kind=kind, dbref=target_id, hotspot_id=hid)
        _refresh(self.caller)


class CmdPokerolEditorSaveHotspots(Command):
    key = "pokerol-editor-save-hotspots"
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
            incoming = data.get("custom") or []
            if not isinstance(incoming, list) or len(incoming) > MAX_CUSTOM_HOTSPOTS:
                raise ValueError("Lista de hotspots inválida.")
            existing = {
                str(row.get("id") or ""): dict(row)
                for row in list(getattr(room.db, "pokerol_custom_hotspots", None) or [])
                if isinstance(row, dict)
            }
            rows = []
            for raw in incoming:
                if not isinstance(raw, dict):
                    continue
                hid = _safe_hotspot_id(raw.get("id"))
                if not hid:
                    continue
                previous = existing.get(hid, {})
                sprite = _clean(raw.get("sprite") or previous.get("sprite"))
                if sprite and not sprite.startswith(PUBLIC_PREFIX):
                    sprite = _clean(previous.get("sprite")) if _clean(previous.get("sprite")).startswith(PUBLIC_PREFIX) else ""
                rows.append({
                    "id": hid,
                    "name": _clean(raw.get("name"), 96) or "HOTSPOT",
                    "command": _clean(raw.get("command"), 500) or "mirar",
                    "x": _number(raw.get("x"), 50, 0, 100),
                    "y": _number(raw.get("y"), 20, 0, 100),
                    "description": _clean(raw.get("description"), 6000),
                    "scale": _number(raw.get("scale"), 1, 0.2, 4),
                    "sprite": sprite,
                })
            removed = set(existing) - {row["id"] for row in rows}
            for hid in removed:
                _delete_managed_asset(existing[hid].get("sprite"))
            room.db.pokerol_custom_hotspots = rows

            incoming_actions = data.get("actions") or {}
            if not isinstance(incoming_actions, dict) or len(incoming_actions) > MAX_ACTION_HOTSPOTS:
                raise ValueError("Layout de hotspots de acción inválido.")
            action_layouts = {}
            for raw_key, raw in incoming_actions.items():
                key = _safe_hotspot_id(raw_key)
                if not key or not isinstance(raw, dict):
                    continue
                action_layouts[key] = {
                    "x": _number(raw.get("x"), 50, 0, 100),
                    "y": _number(raw.get("y"), 20, 0, 100),
                    "scale": _number(raw.get("scale"), 1, 0.2, 4),
                }
            room.db.pokerol_action_hotspot_layouts = action_layouts
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return
        _result(
            self.caller,
            "HOTSPOTS_SAVED",
            "Hotspots guardados en el proyecto.",
            count=len(rows),
            action_count=len(action_layouts),
            room_dbref=int(room.id),
        )
        _refresh(self.caller)


class CmdPokerolEditorPlayerLayout(Command):
    key = "pokerol-editor-player-layout"
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
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return

        key = _clean(getattr(room.db, "room_id", "")) or f"DBREF:{int(room.id)}"
        if bool(data.get("reset")):
            room.db.pokerol_player_layout = None
        else:
            room.db.pokerol_player_layout = {
                "x": _number(data.get("x"), 11, 1, 99),
                "y": _number(data.get("y"), 94, 0, 500),
                "scale": _number(data.get("scale"), 1, 0.35, 3),
            }
        _result(
            self.caller,
            "PLAYER_LAYOUT_SAVED",
            "Posición y tamaño del jugador guardados en el Room del proyecto.",
            room_key=key,
            room_dbref=int(room.id),
        )
        _refresh(self.caller)
