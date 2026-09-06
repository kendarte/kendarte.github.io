"""Create/update a POKEROL biome from a Map Creator JSON export.

Unlike the content-only importer, this is intended for a blank POKEROL world: it
may CREATE rooms, exits and authored static props. It never deletes anything,
never deletes/moves characters and never rewrites an existing exit whose
source/destination conflict with the authored identifiers.
"""

import json
from pathlib import Path

from evennia import create_object
from evennia.objects.models import ObjectDB

from world.pokemon_biome_importer import ROOM_POKEROL_FIELDS, ENTITY_POKEROL_FIELDS


ROOM_FIELDS = (
    "zone_id", "region_id", "settlement_id", "district_id", "canon_status",
    "scene_image", "scene_manifest", "sensory_facts", "space_profile",
    "perception_facts", "job_tasks", "conditions", "world_state",
    "state_presentations",
) + ROOM_POKEROL_FIELDS

EXIT_FIELDS = (
    "door_state", "is_locked", "hidden", "canon_status", "state_requirements",
    "state_block_message", "campaign_tags",
)

PROP_FIELDS = (
    "desc", "portable", "hidden", "state", "interaction_facts",
    "object_actions", "state_visibility_requirements", "canon_status",
) + ENTITY_POKEROL_FIELDS


def _read(path):
    candidate = Path(str(path or "")).expanduser()
    if not candidate.is_file():
        raise ValueError("No se encontró el mapa: {}".format(candidate))
    with candidate.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("El mapa debe contener un objeto JSON.")
    if not isinstance(data.get("rooms"), list) or not isinstance(data.get("exits"), list):
        raise ValueError("El mapa necesita listas rooms y exits.")
    return data


def _index(attr):
    output = {}
    for obj in ObjectDB.objects.all():
        value = getattr(obj.db, attr, None)
        if value:
            output[str(value)] = obj
    return output


def _copy(obj, row, fields):
    changed = []
    for field in fields:
        if field not in row:
            continue
        value = row[field]
        if getattr(obj.db, field, None) != value:
            setattr(obj.db, field, value)
            changed.append(field)
    return changed


def _aliases(obj, values):
    desired = sorted({str(v).strip() for v in values or [] if str(v).strip()})
    try:
        current = sorted(str(v) for v in obj.aliases.all())
    except Exception:
        current = []
    if current == desired:
        return False
    try:
        obj.aliases.clear()
        for alias in desired:
            obj.aliases.add(alias)
        return True
    except Exception:
        return False


def _scene_entities(room_row):
    manifest = room_row.get("scene_manifest")
    if not isinstance(manifest, dict):
        return []
    rows = manifest.get("entities")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def materialize_pokemon_biome_file(path):
    data = _read(path)
    rooms_by_id = _index("room_id")
    exits_by_id = _index("exit_id")
    props_by_id = _index("object_id")
    editor_rooms = {}
    report = {
        "kind": "pokerol_biome_materialization",
        "rooms_created": [], "rooms_updated": [],
        "exits_created": [], "exits_updated": [], "exit_conflicts": [],
        "props_created": [], "props_updated": [], "prop_conflicts": [],
    }

    # Rooms first so every exit can resolve stable endpoints.
    for row in data.get("rooms") or []:
        if not isinstance(row, dict):
            continue
        editor_id = str(row.get("id") or "").strip()
        room_id = str(row.get("room_id") or "").strip()
        key = str(row.get("key") or room_id or "Room").strip()
        if not editor_id or not room_id:
            continue
        room = rooms_by_id.get(room_id)
        created = room is None
        if created:
            room = create_object("typeclasses.rooms.Room", key=key)
            room.db.room_id = room_id
            rooms_by_id[room_id] = room
        elif room.key != key:
            room.key = key
        if "desc" in row:
            room.db.desc = row.get("desc") or ""
        changed = _copy(room, row, ROOM_FIELDS)
        editor_rooms[editor_id] = room
        item = {"room_id": room_id, "dbref": int(room.id), "fields": changed}
        report["rooms_created" if created else "rooms_updated"].append(item)

    # Directed exits. Existing conflicting topology is reported, never moved silently.
    for row in data.get("exits") or []:
        if not isinstance(row, dict):
            continue
        exit_id = str(row.get("exit_id") or "").strip()
        source = editor_rooms.get(str(row.get("source") or "").strip())
        target = editor_rooms.get(str(row.get("target") or "").strip())
        if not exit_id or not source or not target:
            report["exit_conflicts"].append({"exit_id": exit_id, "reason": "MISSING_ENDPOINT"})
            continue
        key = str(row.get("key") or target.key).strip()
        exit_obj = exits_by_id.get(exit_id)
        created = exit_obj is None
        if created:
            exit_obj = create_object("typeclasses.exits.Exit", key=key, location=source, destination=target)
            exit_obj.db.exit_id = exit_id
            exits_by_id[exit_id] = exit_obj
        else:
            if exit_obj.location is not source or exit_obj.destination is not target:
                report["exit_conflicts"].append({
                    "exit_id": exit_id,
                    "reason": "EXISTING_TOPOLOGY_DIFFERS",
                    "existing_source": int(exit_obj.location.id) if exit_obj.location else None,
                    "existing_target": int(exit_obj.destination.id) if exit_obj.destination else None,
                })
                continue
            if exit_obj.key != key:
                exit_obj.key = key
        changed = _copy(exit_obj, row, EXIT_FIELDS)
        if _aliases(exit_obj, row.get("aliases")):
            changed.append("aliases")
        item = {"exit_id": exit_id, "dbref": int(exit_obj.id), "fields": changed}
        report["exits_created" if created else "exits_updated"].append(item)

    # Static physical props from scene manifests.
    for row in data.get("rooms") or []:
        if not isinstance(row, dict):
            continue
        room = editor_rooms.get(str(row.get("id") or "").strip())
        if not room:
            continue
        for entity in _scene_entities(row):
            object_id = str(entity.get("object_id") or entity.get("id") or "").strip()
            name = str(entity.get("name") or object_id).strip()
            if not object_id or not name:
                continue
            prop = props_by_id.get(object_id)
            created = prop is None
            if created:
                prop = create_object("typeclasses.siza_objects.WorldObject", key=name, location=room)
                prop.db.object_id = object_id
                props_by_id[object_id] = prop
            elif bool(getattr(prop.db, "is_npc", False)):
                report["prop_conflicts"].append({"object_id": object_id, "reason": "OBJECT_ID_IS_NPC"})
                continue
            elif prop.location is not room:
                report["prop_conflicts"].append({"object_id": object_id, "reason": "EXISTING_PROP_IN_OTHER_ROOM"})
                continue
            elif prop.key != name:
                prop.key = name

            if "visible_description" in entity:
                prop.db.desc = entity.get("visible_description") or ""
            changed = _copy(prop, entity, PROP_FIELDS)
            if _aliases(prop, entity.get("aliases")):
                changed.append("aliases")
            item = {"object_id": object_id, "dbref": int(prop.id), "room_id": room.db.room_id, "fields": changed}
            report["props_created" if created else "props_updated"].append(item)

    for key in list(report):
        if isinstance(report[key], list):
            report[key + "_count"] = len(report[key])
    return report
