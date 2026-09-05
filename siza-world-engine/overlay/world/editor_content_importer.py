"""Safe content-only importers for SIZA Map Creator and NPC Creator exports.

These functions only update existing objects identified by their stable room_id or
npc_id. They never create, delete, move, reset, or rename world objects.
"""

import json
from pathlib import Path

from evennia.objects.models import ObjectDB


ROOM_CONTENT_FIELDS = (
    "desc",
    "scene_image",
    "canon_status",
    "sensory_facts",
    "space_profile",
    "perception_facts",
    "job_tasks",
    "conditions",
    "world_state",
    "state_presentations",
)

NPC_CONTENT_FIELDS = (
    "desc",
    "dialogue_greeting",
    "dialogue_topics",
    "canon_status",
)


def _read_json(path):
    candidate = Path(str(path or "")).expanduser()
    if not candidate.is_file():
        raise ValueError("No se encontró el archivo: {}".format(candidate))
    with candidate.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("El archivo debe contener un objeto JSON.")
    return data


def _objects_by_identifier(attribute_name):
    indexed = {}
    for obj in ObjectDB.objects.all():
        identifier = getattr(obj.db, attribute_name, None)
        if identifier:
            indexed[str(identifier)] = obj
    return indexed


def _room_rows(data):
    rows = data.get("rooms")
    if not isinstance(rows, list):
        raise ValueError("El mapa no contiene una lista rooms.")
    return [row for row in rows if isinstance(row, dict)]


def _npc_rows(data):
    rows = data.get("npcs")
    if not isinstance(rows, list):
        raise ValueError("El archivo de NPCs no contiene una lista npcs.")
    return [row for row in rows if isinstance(row, dict)]


def _summary(kind, rows, index, identifier_key):
    found = []
    missing = []
    for row in rows:
        identifier = str(row.get(identifier_key) or "").strip()
        if not identifier:
            missing.append({"id": "", "reason": "sin identificador"})
        elif identifier in index:
            found.append(identifier)
        else:
            missing.append({"id": identifier, "reason": "objeto inexistente"})
    return {
        "kind": kind,
        "source_rows": len(rows),
        "matched": len(found),
        "missing": missing,
        "identifiers": found,
    }


def preview_map_file(path):
    data = _read_json(path)
    return _summary("map", _room_rows(data), _objects_by_identifier("room_id"), "room_id")


def preview_npc_file(path):
    data = _read_json(path)
    return _summary("npcs", _npc_rows(data), _objects_by_identifier("npc_id"), "npc_id")


def _copy_fields(obj, row, field_names):
    changed = []
    for field in field_names:
        if field not in row:
            continue
        value = row[field]
        if getattr(obj.db, field, None) != value:
            setattr(obj.db, field, value)
            changed.append(field)
    return changed


def apply_map_file(path):
    data = _read_json(path)
    rooms = _objects_by_identifier("room_id")
    report = {"kind": "map", "updated": [], "missing": [], "unchanged": []}

    for row in _room_rows(data):
        room_id = str(row.get("room_id") or "").strip()
        room = rooms.get(room_id)
        if not room:
            report["missing"].append(room_id or "(sin room_id)")
            continue
        changed = _copy_fields(room, row, ROOM_CONTENT_FIELDS)
        target = "updated" if changed else "unchanged"
        report[target].append({"room_id": room_id, "fields": changed})

    report["updated_count"] = len(report["updated"])
    report["missing_count"] = len(report["missing"])
    return report


def apply_npc_file(path):
    data = _read_json(path)
    npcs = _objects_by_identifier("npc_id")
    report = {"kind": "npcs", "updated": [], "missing": [], "unchanged": []}

    for row in _npc_rows(data):
        npc_id = str(row.get("npc_id") or "").strip()
        npc = npcs.get(npc_id)
        if not npc:
            report["missing"].append(npc_id or "(sin npc_id)")
            continue
        changed = _copy_fields(npc, row, NPC_CONTENT_FIELDS)
        target = "updated" if changed else "unchanged"
        report[target].append({"npc_id": npc_id, "fields": changed})

    report["updated_count"] = len(report["updated"])
    report["missing_count"] = len(report["missing"])
    return report


def preview_files(map_path=None, npc_path=None):
    report = {}
    if map_path:
        report["map"] = preview_map_file(map_path)
    if npc_path:
        report["npcs"] = preview_npc_file(npc_path)
    if not report:
        raise ValueError("Seleccione al menos un archivo de contenido.")
    return report


def apply_files(map_path=None, npc_path=None):
    report = {}
    if map_path:
        report["map"] = apply_map_file(map_path)
    if npc_path:
        report["npcs"] = apply_npc_file(npc_path)
    if not report:
        raise ValueError("Seleccione al menos un archivo de contenido.")
    return report
