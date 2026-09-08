import base64
import json
import os
import re
import shutil
from pathlib import Path
from uuid import uuid4

from evennia import Command


BATTLE_SCENE_BUILD = "0.1.0-persistent-battle-scene"
ASSET_ROOT = Path(os.environ.get("POKEROL_ASSET_ROOT", "/data/pokerol_assets"))
PUBLIC_PREFIX = "/pokerol-assets/"
MAX_ASSET_BYTES = 8 * 1024 * 1024
MAX_HOTSPOTS = 80
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


def _safe_hotspot_id(value):
    value = _clean(value, 96)
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value or "") else ""


def _uploads(caller):
    uploads = getattr(caller.ndb, "pokerol_battle_scene_uploads", None)
    if not isinstance(uploads, dict):
        uploads = {}
        caller.ndb.pokerol_battle_scene_uploads = uploads
    return uploads


def _room(caller):
    room = getattr(caller, "location", None)
    if not room:
        raise ValueError("No hay cuarto actual.")
    return room


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


def _ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o755)
    except OSError:
        pass
    return path


def _hotspots(room):
    output = []
    for raw in list(getattr(room.db, "pokerol_battle_hotspots", None) or []):
        if not isinstance(raw, dict):
            continue
        output.append({
            "id": _safe_hotspot_id(raw.get("id")),
            "name": _clean(raw.get("name"), 96) or "HOTSPOT",
            "command": _clean(raw.get("command"), 500),
            "description": _clean(raw.get("description"), 6000),
            "x": _number(raw.get("x"), 50, 0, 100),
            "y": _number(raw.get("y"), 50, 0, 100),
            "width": _number(raw.get("width"), 12, 2, 80),
            "height": _number(raw.get("height"), 12, 2, 80),
            "hidden": bool(raw.get("hidden", False)),
            "target_dbref": raw.get("target_dbref"),
        })
    return [row for row in output if row.get("id")]


def _scene_packet(caller):
    room = _room(caller)
    background = _clean(getattr(room.db, "pokerol_battle_scene_image", ""))
    return {
        "status": "BATTLE_SCENE_STATE",
        "build": BATTLE_SCENE_BUILD,
        "room_dbref": int(room.id),
        "room_id": _clean(getattr(room.db, "room_id", "")),
        "room_name": str(room.key),
        "background": background,
        "hotspots": _hotspots(room),
    }


def _emit_state(caller):
    packet = _scene_packet(caller)
    caller.msg(pokerol_battle_scene_state=((packet,), {"build": BATTLE_SCENE_BUILD}))
    return packet


def _result(caller, status, message, **extra):
    packet = {"status": status, "message": message, "build": BATTLE_SCENE_BUILD}
    packet.update(extra)
    caller.msg(pokerol_battle_scene_result=((packet,), {"build": BATTLE_SCENE_BUILD}))
    return packet


class CmdPokerolBattleSceneState(Command):
    key = "pokerol-battle-scene-state"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            _emit_state(self.caller)
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))


class CmdPokerolBattleSceneSave(Command):
    key = "pokerol-battle-scene-save"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            room = _room(self.caller)
            data = _decode_payload(self.args)
            incoming = data.get("hotspots") or []
            if not isinstance(incoming, list) or len(incoming) > MAX_HOTSPOTS:
                raise ValueError("Lista de hotspots inválida.")
            rows = []
            seen = set()
            for raw in incoming:
                if not isinstance(raw, dict):
                    continue
                hid = _safe_hotspot_id(raw.get("id")) or ("BATTLE-HOTSPOT-" + uuid4().hex[:10].upper())
                if hid in seen:
                    continue
                seen.add(hid)
                target_dbref = raw.get("target_dbref")
                try:
                    target_dbref = int(target_dbref) if target_dbref not in (None, "") else None
                except (TypeError, ValueError):
                    target_dbref = None
                rows.append({
                    "id": hid,
                    "name": _clean(raw.get("name"), 96) or "HOTSPOT",
                    "command": _clean(raw.get("command"), 500),
                    "description": _clean(raw.get("description"), 6000),
                    "x": _number(raw.get("x"), 50, 0, 100),
                    "y": _number(raw.get("y"), 50, 0, 100),
                    "width": _number(raw.get("width"), 12, 2, 80),
                    "height": _number(raw.get("height"), 12, 2, 80),
                    "hidden": bool(raw.get("hidden", False)),
                    "target_dbref": target_dbref,
                })
            room.db.pokerol_battle_hotspots = rows
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return
        _result(self.caller, "BATTLE_SCENE_SAVED", "Escena de combate guardada.", count=len(rows), room_dbref=int(room.id))
        _emit_state(self.caller)


class CmdPokerolBattleSceneAssetBegin(Command):
    key = "pokerol-battle-scene-asset-begin"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            room = _room(self.caller)
            data = _decode_payload(self.args)
            mime = _clean(data.get("mime")).lower()
            if mime not in MIME_EXT:
                raise ValueError("Formato de imagen no permitido.")
            size = int(data.get("size") or 0)
            if size <= 0 or size > MAX_ASSET_BYTES:
                raise ValueError("La imagen supera el límite de 8 MB o está vacía.")
            _ensure_dir(ASSET_ROOT)
            temp_dir = _ensure_dir(ASSET_ROOT / ".tmp")
            token = uuid4().hex
            temp_path = temp_dir / ("battle-" + token + ".part")
            temp_path.write_bytes(b"")
            _uploads(self.caller)[token] = {
                "mime": mime,
                "size": size,
                "received": 0,
                "next_index": 0,
                "temp": str(temp_path),
                "room_dbref": int(room.id),
            }
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return
        _result(self.caller, "UPLOAD_READY", "Carga preparada.", token=token, chunk_size=32768)


class CmdPokerolBattleSceneAssetChunk(Command):
    key = "pokerol-battle-scene-asset-chunk"
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


class CmdPokerolBattleSceneAssetFinish(Command):
    key = "pokerol-battle-scene-asset-finish"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        token = ""
        try:
            room = _room(self.caller)
            data = _decode_payload(self.args)
            token = _clean(data.get("token"), 64)
            upload = _uploads(self.caller).get(token)
            if not upload:
                raise ValueError("La carga ya no existe.")
            if int(upload.get("room_dbref", -1)) != int(room.id):
                raise ValueError("La carga pertenece a otro cuarto.")
            if int(upload.get("received", 0)) != int(upload.get("size", 0)):
                raise ValueError("La imagen está incompleta.")
            folder = _ensure_dir(ASSET_ROOT / "battle_rooms")
            ext = MIME_EXT[upload["mime"]]
            filename = f"battle-room-{int(room.id)}-{uuid4().hex[:12]}{ext}"
            final_path = folder / filename
            shutil.move(upload["temp"], final_path)
            try:
                final_path.chmod(0o644)
            except OSError:
                pass
            url = PUBLIC_PREFIX + "battle_rooms/" + filename
            old = _clean(getattr(room.db, "pokerol_battle_scene_image", ""))
            room.db.pokerol_battle_scene_image = url
            _delete_managed_asset(old)
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
        _result(self.caller, "UPLOAD_DONE", "Battle background guardado.", token=token, url=url, room_dbref=int(room.id))
        _emit_state(self.caller)


class CmdPokerolBattleSceneAssetClear(Command):
    key = "pokerol-battle-scene-asset-clear"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        try:
            room = _room(self.caller)
            old = _clean(getattr(room.db, "pokerol_battle_scene_image", ""))
            room.db.pokerol_battle_scene_image = ""
            _delete_managed_asset(old)
        except Exception as exc:
            _result(self.caller, "ERROR", str(exc))
            return
        _result(self.caller, "ASSET_CLEARED", "Battle background eliminado.", room_dbref=int(room.id))
        _emit_state(self.caller)
