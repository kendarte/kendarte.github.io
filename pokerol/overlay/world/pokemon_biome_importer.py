"""POKEROL biome importer layered on top of the generic Map Creator importer.

It preserves the generic SIZA/POKEROL map format while copying extra authored
Pokémon ecology and physical-world fields into Evennia attributes.
"""

import json
from pathlib import Path

from evennia.objects.models import ObjectDB

from world.editor_content_importer import apply_map_file, apply_scene_entities_file


ROOM_POKEROL_FIELDS = (
    "biome_profile",
    "pokemon_populations",
    "environmental_state",
    "water_bodies",
    "ecology_rules",
)

ENTITY_POKEROL_FIELDS = (
    "materials",
    "physical_properties",
    "environmental_state",
    "pokemon_interaction_tags",
    "water_body_id",
    "connected_object_ids",
    "area_effects",
)


def _read(path):
    candidate = Path(str(path or "")).expanduser()
    if not candidate.is_file():
        raise ValueError("No se encontró el archivo: {}".format(candidate))
    with candidate.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("El archivo debe contener un objeto JSON.")
    return data


def _index(attribute_name):
    output = {}
    for obj in ObjectDB.objects.all():
        value = getattr(obj.db, attribute_name, None)
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


def _scene_entities(room_row):
    manifest = room_row.get("scene_manifest")
    if not isinstance(manifest, dict):
        return []
    entities = manifest.get("entities")
    return [row for row in entities if isinstance(row, dict)] if isinstance(entities, list) else []


def apply_pokemon_biome_file(path, materialize_scene_props=True):
    """Apply normal map content plus POKEROL ecology/physics metadata.

    This never deletes rooms, exits, characters or props.
    """
    data = _read(path)
    base_map = apply_map_file(path)
    scene_props = apply_scene_entities_file(path) if materialize_scene_props else None

    rooms = _index("room_id")
    props = _index("object_id")
    report = {
        "kind": "pokerol_biome",
        "base_map": base_map,
        "scene_props": scene_props,
        "rooms": [],
        "entities": [],
        "missing_rooms": [],
        "missing_entities": [],
    }

    for room_row in data.get("rooms") or []:
        if not isinstance(room_row, dict):
            continue
        room_id = str(room_row.get("room_id") or "").strip()
        room = rooms.get(room_id)
        if not room:
            report["missing_rooms"].append(room_id or "(sin room_id)")
            continue
        changed = _copy(room, room_row, ROOM_POKEROL_FIELDS)
        report["rooms"].append({"room_id": room_id, "fields": changed})

        for entity in _scene_entities(room_row):
            object_id = str(entity.get("object_id") or entity.get("id") or "").strip()
            if not object_id:
                continue
            prop = props.get(object_id)
            if not prop:
                report["missing_entities"].append({"room_id": room_id, "object_id": object_id})
                continue
            fields = _copy(prop, entity, ENTITY_POKEROL_FIELDS)
            report["entities"].append({"room_id": room_id, "object_id": object_id, "fields": fields})

    report["room_count"] = len(report["rooms"])
    report["entity_count"] = len(report["entities"])
    report["missing_room_count"] = len(report["missing_rooms"])
    report["missing_entity_count"] = len(report["missing_entities"])
    return report
