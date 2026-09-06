"""Importer for POKEROL Pokémon Creator exports.

This imports species/move templates into the persistent species registry. It never
creates owned Pokémon, modifies Party/Bag, or spawns creatures in Rooms.
"""

import json
from pathlib import Path

from services.pokemon_species_registry import import_species_set, validate_species_set


def _read_json(path):
    candidate = Path(str(path or "")).expanduser()
    if not candidate.is_file():
        raise ValueError("No se encontró el archivo: {}".format(candidate))
    with candidate.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("El archivo Pokémon debe contener un objeto JSON.")
    return data


def preview_pokemon_file(path):
    report = validate_species_set(_read_json(path))
    report["kind"] = "pokemon_species_set"
    return report


def apply_pokemon_file(path):
    report = import_species_set(_read_json(path))
    report["kind"] = "pokemon_species_set"
    return report
