from services.pokemon_battle_position_engine import (
    apply_verified_position,
    position_accuracy_multiplier,
    position_move_gate,
    position_targets,
)
from services.pokemon_battle_reaction_engine import (
    arm_reaction,
    dodge_chance,
    settle_incoming_attack_reaction,
)


class FakeDB:
    pass


class FakeObj:
    def __init__(self, obj_id, key, **attrs):
        self.id = obj_id
        self.key = key
        self.db = FakeDB()
        for name, value in attrs.items():
            setattr(self.db, name, value)


class FakeActor:
    def __init__(self, room):
        self.location = room


def battle_pokemon(entity_id, name, speed=50, moves=None):
    return {
        "entity_id": entity_id,
        "name": name,
        "species_name": name,
        "types": ["NORMAL"],
        "stats": {"HP": 40, "ATK": 40, "DEF": 40, "SPA": 40, "SPD": 40, "SPE": speed},
        "hp_max": 40,
        "hp_current": 40,
        "status": "OK",
        "battle_stages": {"ATK": 0, "DEF": 0, "SPA": 0, "SPD": 0, "SPE": 0, "ACC": 0, "EVA": 0},
        "moves": moves or [],
    }


def move(move_id="TACKLE", delivery="CONTACT"):
    return {
        "move_id": move_id,
        "name": move_id,
        "delivery": delivery,
        "world_effects": [],
        "requirements": {},
        "pp": 20,
        "pp_current": 20,
    }


def test_enter_water_sets_shared_medium():
    pokemon = battle_pokemon("P1", "Pikachu")
    result = apply_verified_position(pokemon, {
        "action": "ENTER_WATER",
        "target_id": "WATER:WB-TEST",
        "name": "Estanque",
        "water_body_id": "WB-TEST",
        "medium_kind": "POND",
        "mobility_modifier": 0.72,
    })
    assert result["applied"] is True
    assert pokemon["battle_position"]["stance"] == "WATER"
    assert pokemon["contact_medium_id"] == "WB-TEST"


def test_contact_move_cannot_reach_airborne_target_but_beam_can():
    attacker = battle_pokemon("A", "Rattata")
    defender = battle_pokemon("D", "Pidgey")
    defender["battle_position"] = {"stance": "AIR", "altitude": "LOW", "mobility_modifier": 1.08}
    blocked = position_move_gate(attacker, defender, move("TACKLE", "CONTACT"))
    allowed = position_move_gate(attacker, defender, move("THUNDER-SHOCK", "BEAM"))
    assert blocked["allowed"] is False
    assert blocked["status"] == "TARGET_OUT_OF_REACH_AIR"
    assert allowed["allowed"] is True


def test_cover_reduces_incoming_accuracy():
    attacker = battle_pokemon("A", "Charmander")
    defender = battle_pokemon("D", "Pikachu")
    defender["battle_position"] = {
        "stance": "GROUND",
        "cover": {"name": "Roca", "rating": 0.40},
        "mobility_modifier": 0.94,
    }
    assert position_accuracy_multiplier(attacker, defender) < 1.0


def test_room_authority_exposes_water_and_biome_cover():
    room = FakeObj(1, "Ruta")
    room.db.biome_profile = {"cover": ["trees", "shrubs"]}
    room.db.water_bodies = [{"water_body_id": "WB-TEST", "kind": "POND"}]
    room.db.world_state = {"weather": "mild"}
    water = FakeObj(
        2,
        "Agua del estanque",
        materials=["WATER"],
        pokemon_interaction_tags=["SHARED_CONDUCTIVE_MEDIUM"],
        water_body_id="WB-TEST",
        physical_properties={"conductivity": 1.0},
        environmental_state={"wetness": 1.0},
        object_id="OBJ-WATER",
    )
    water.location = room
    room.contents = [water]
    actor = FakeActor(room)
    player = battle_pokemon("P1", "Pikachu")
    battle = {
        "player": player,
        "enemy": battle_pokemon("E1", "Rattata"),
        "_source_player_profile": {"locomotion": ["WALK", "CLIMB"], "body_tags": ["CLIMBER"]},
    }
    rows = position_targets(actor, battle)
    assert any(row.get("action") == "ENTER_WATER" and row.get("water_body_id") == "WB-TEST" for row in rows)
    assert any(row.get("action") == "TAKE_COVER" and row.get("source") == "BIOME_PROFILE" for row in rows)
    assert any(row.get("action") == "CLIMB" for row in rows)


def test_faster_defender_gets_meaningful_dodge_chance():
    attacker = battle_pokemon("A", "Slow", speed=30)
    defender = battle_pokemon("D", "Fast", speed=100)
    battle = {"turn": 1, "player": defender, "enemy": attacker}
    arm_reaction(battle, "PLAYER", "DODGE")
    assert dodge_chance(attacker, defender) > 0.18


def test_successful_miss_is_promoted_to_dodge_and_consumes_reaction():
    enemy_move = move("TACKLE", "CONTACT")
    player = battle_pokemon("P", "Pikachu", speed=90)
    enemy = battle_pokemon("E", "Rattata", speed=50, moves=[enemy_move])
    battle = {"turn": 1, "phase": "ACTION", "player": player, "enemy": enemy, "log": []}
    arm_reaction(battle, "PLAYER", "DODGE")
    battle["log"].extend([
        {"kind": "MOVE", "actor": "E", "move_id": "TACKLE", "text": "Rattata usa Tackle."},
        {"kind": "MISS", "actor": "E", "target": "P", "text": "El ataque falla."},
    ])
    result = settle_incoming_attack_reaction(battle, "PLAYER", 0)
    assert result["consumed"] is True
    assert result["success"] is True
    assert battle["log"][-1]["kind"] == "DODGE_SUCCESS"
    assert battle["player"]["battle_reaction"]["armed"] is False


def test_enemy_self_move_does_not_consume_dodge():
    enemy_move = move("HARDEN", "SELF")
    player = battle_pokemon("P", "Pikachu", speed=90)
    enemy = battle_pokemon("E", "Metapod", speed=30, moves=[enemy_move])
    battle = {"turn": 1, "phase": "ACTION", "player": player, "enemy": enemy, "log": []}
    arm_reaction(battle, "PLAYER", "DODGE")
    battle["log"].append({"kind": "MOVE", "actor": "E", "move_id": "HARDEN", "text": "Metapod usa Harden."})
    result = settle_incoming_attack_reaction(battle, "PLAYER", 0)
    assert result["consumed"] is False
    assert result["status"] == "INCOMING_MOVE_IS_SELF"
    assert battle["player"]["battle_reaction"]["armed"] is True
