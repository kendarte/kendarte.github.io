"""POKEROL first-start bootstrap.

Runs after Evennia has created Account #1, its Character and Limbo. The Kanto
seed is materialized once by Evennia's normal AT_INITIAL_SETUP_HOOK_MODULE.
"""

from pathlib import Path

from evennia import logger
from evennia.accounts.models import AccountDB
from evennia.objects.models import ObjectDB
from evennia.server.models import ServerConfig

from world.pokemon_biome_materializer import materialize_pokemon_biome_file


SEED_NAME = "kanto-pallet-viridian.seed.json"
START_ROOM_ID = "KANTO-PAL-001"


def _seed_path():
    gamedir = Path(__file__).resolve().parents[2]
    return gamedir / "world" / "seeds" / SEED_NAME


def _room_by_room_id(room_id):
    for obj in ObjectDB.objects.all():
        if str(getattr(obj.db, "room_id", "") or "") == room_id:
            return obj
    return None


def at_initial_setup():
    seed_path = _seed_path()
    if not seed_path.is_file():
        raise RuntimeError("POKEROL Kanto seed missing: {}".format(seed_path))

    report = materialize_pokemon_biome_file(seed_path)
    start_room = _room_by_room_id(START_ROOM_ID)
    if start_room is None:
        raise RuntimeError("POKEROL start room was not materialized: {}".format(START_ROOM_ID))

    account = AccountDB.objects.filter(id=1).first()
    character = ObjectDB.objects.filter(db_account=account).first() if account else None
    if character:
        character.location = start_room
        character.home = start_room
        character.save()

    summary = {
        "seed": SEED_NAME,
        "start_room_id": START_ROOM_ID,
        "start_room_dbref": int(start_room.id),
        "rooms_created": int(report.get("rooms_created_count", 0)),
        "exits_created": int(report.get("exits_created_count", 0)),
        "props_created": int(report.get("props_created_count", 0)),
    }
    ServerConfig.objects.conf("pokerol_initial_seed", summary)
    logger.log_info("POKEROL initial Kanto seed materialized: {}".format(summary))
