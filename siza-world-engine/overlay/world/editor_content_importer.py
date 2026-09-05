"""Safe content-only importers for SIZA Map Creator and NPC Creator exports.

The standard map/NPC importers only update existing objects identified by stable
room_id or npc_id. The separate scene-prop materializer creates or updates only
static WorldObject props authored inside a room scene manifest; it does not touch
characters, exits, player inventory, world state, or campaign progress.
"""

import json
from pathlib import Path

from evennia import create_object
from evennia.objects.models import ObjectDB
from services.knowledge_fact_engine import upsert_knowledge_fact


ROOM_CONTENT_FIELDS = (
    "desc",
    "scene_image",
    "scene_manifest",
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
    "narrative_profile",
    "social_affordances",
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


def _scene_entity_rows(row):
    manifest = row.get("scene_manifest")
    if not isinstance(manifest, dict):
        return []
    entities = manifest.get("entities")
    return [entry for entry in entities if isinstance(entry, dict)] if isinstance(entities, list) else []


def _scene_prop_index():
    indexed = {}
    for obj in ObjectDB.objects.all():
        object_id = str(getattr(obj.db, "object_id", "") or "").strip()
        if object_id:
            indexed[object_id] = obj
    return indexed


def preview_scene_entities_file(path):
    """Report authored static scene props without mutating the running world."""
    data = _read_json(path)
    rooms = _objects_by_identifier("room_id")
    props = _scene_prop_index()
    report = {"kind": "scene_props", "rooms": [], "create": [], "update": [], "invalid": [], "missing_rooms": []}

    for row in _room_rows(data):
        room_id = str(row.get("room_id") or "").strip()
        if room_id not in rooms:
            report["missing_rooms"].append(room_id or "(sin room_id)")
            continue
        count = 0
        for entity in _scene_entity_rows(row):
            object_id = str(entity.get("object_id") or entity.get("id") or "").strip()
            name = str(entity.get("name") or "").strip()
            if not object_id or not name:
                report["invalid"].append({"room_id": room_id, "entity_id": entity.get("id"), "reason": "object_id o nombre ausente"})
                continue
            count += 1
            item = {"room_id": room_id, "object_id": object_id, "name": name}
            (report["update"] if object_id in props else report["create"]).append(item)
        report["rooms"].append({"room_id": room_id, "entities": count})

    report["create_count"] = len(report["create"])
    report["update_count"] = len(report["update"])
    report["invalid_count"] = len(report["invalid"])
    report["missing_room_count"] = len(report["missing_rooms"])
    return report


def _copy_scene_prop_fields(obj, entity, room):
    changed = []
    desired = {
        "scene_entity_id": str(entity.get("id") or entity.get("object_id") or ""),
        "desc": str(entity.get("visible_description") or entity.get("description") or ""),
        "portable": bool(entity.get("portable", False)),
        "hidden": bool(entity.get("hidden", False)),
        "state": entity.get("state") if isinstance(entity.get("state"), dict) else {},
        "interaction_facts": entity.get("interaction_facts") if isinstance(entity.get("interaction_facts"), list) else [],
        "object_actions": entity.get("object_actions") if isinstance(entity.get("object_actions"), list) else [],
        "state_visibility_requirements": entity.get("state_visibility_requirements") if isinstance(entity.get("state_visibility_requirements"), list) else [],
        "canon_status": str(entity.get("canon_status") or getattr(room.db, "canon_status", "") or "prototype"),
    }
    for field, value in desired.items():
        if getattr(obj.db, field, None) != value:
            setattr(obj.db, field, value)
            changed.append(field)
    aliases = [str(value).strip() for value in entity.get("aliases") or [] if str(value).strip()]
    try:
        current_aliases = sorted(str(value) for value in obj.aliases.all())
    except Exception:
        current_aliases = []
    if current_aliases != sorted(aliases):
        try:
            obj.aliases.clear()
            for alias in aliases:
                obj.aliases.add(alias)
            changed.append("aliases")
        except Exception:
            pass
    return changed


def apply_scene_entities_file(path):
    """Create/update only map-authored static props; never delete or move existing objects."""
    data = _read_json(path)
    rooms = _objects_by_identifier("room_id")
    props = _scene_prop_index()
    report = {
        "kind": "scene_props",
        "created": [],
        "updated": [],
        "unchanged": [],
        "missing_rooms": [],
        "invalid": [],
        "conflicts": [],
    }

    for row in _room_rows(data):
        room_id = str(row.get("room_id") or "").strip()
        room = rooms.get(room_id)
        if not room:
            report["missing_rooms"].append(room_id or "(sin room_id)")
            continue
        for entity in _scene_entity_rows(row):
            object_id = str(entity.get("object_id") or entity.get("id") or "").strip()
            name = str(entity.get("name") or "").strip()
            if not object_id or not name:
                report["invalid"].append({"room_id": room_id, "entity_id": entity.get("id"), "reason": "object_id o nombre ausente"})
                continue
            prop = props.get(object_id)
            if prop is not None and bool(getattr(prop.db, "is_npc", False)):
                report["conflicts"].append({"room_id": room_id, "object_id": object_id, "reason": "object_id pertenece a un NPC"})
                continue
            created = prop is None
            if created:
                prop = create_object("typeclasses.siza_objects.WorldObject", key=name, location=room)
                prop.db.object_id = object_id
                props[object_id] = prop
            if not created and getattr(prop, "location", None) is not room:
                report["conflicts"].append({"room_id": room_id, "object_id": object_id, "reason": "prop existente fuera de su Room; se conserva su ubicación"})
                continue
            if created:
                prop.key = name
            elif prop.key != name:
                prop.key = name
            changed = _copy_scene_prop_fields(prop, entity, room)
            item = {"room_id": room_id, "object_id": object_id, "name": name, "fields": changed}
            if created:
                report["created"].append(item)
            elif changed:
                report["updated"].append(item)
            else:
                report["unchanged"].append(item)

    for key in ("created", "updated", "unchanged", "missing_rooms", "invalid", "conflicts"):
        report[key + "_count"] = len(report[key])
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
        fact_results = []
        if isinstance(row.get("knowledge_facts"), list):
            for fact in row.get("knowledge_facts") or []:
                if not isinstance(fact, dict):
                    continue
                result = upsert_knowledge_fact(npc, fact)
                if str(result.get("status") or "") in {"CREATED", "UPDATED"}:
                    fact_results.append({
                        "fact_id": result.get("fact_id"),
                        "status": result.get("status"),
                    })
            if fact_results:
                changed.append("knowledge_facts")
        target = "updated" if changed else "unchanged"
        report[target].append({"npc_id": npc_id, "fields": changed, "knowledge_facts": fact_results})

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


def apply_files(map_path=None, npc_path=None, materialize_scene_props=False):
    report = {}
    if map_path:
        report["map"] = apply_map_file(map_path)
        if materialize_scene_props:
            report["scene_props"] = apply_scene_entities_file(map_path)
    if npc_path:
        report["npcs"] = apply_npc_file(npc_path)
    if not report:
        raise ValueError("Seleccione al menos un archivo de contenido.")
    return report
