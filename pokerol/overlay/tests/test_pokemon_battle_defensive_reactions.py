from services.pokemon_battle_reaction_engine import (
    arm_reaction,
    reaction_accuracy_multiplier,
    reaction_options,
    set_incoming_reaction_context,
    settle_incoming_attack_reaction,
)


def move(move_id, name=None, delivery="PROJECTILE", damage_class="PHYSICAL", pp=10, effects=None, defense_profile="NONE"):
    return {
        "move_id": move_id,
        "name": name or move_id,
        "delivery": delivery,
        "damage_class": damage_class,
        "pp": pp,
        "pp_max": pp,
        "pp_current": pp,
        "world_effects": effects or [],
        "defense_profile": defense_profile,
    }


def pokemon(entity_id, name, speed=60, moves=None):
    return {
        "entity_id": entity_id,
        "name": name,
        "species_name": name,
        "hp_current": 40,
        "hp_max": 40,
        "status": "OK",
        "stats": {"SPE": speed},
        "battle_stages": {"SPE": 0},
        "moves": moves or [],
    }


def test_gust_authorizes_redirect_and_harden_authorizes_block():
    defender = pokemon("P", "Butterfree", moves=[
        move("GUST", "Gust", delivery="WAVE", damage_class="SPECIAL", effects=["CREATE_WIND"]),
        move("HARDEN", "Harden", delivery="SELF", damage_class="STATUS", effects=["HARDEN_BODY"]),
    ])
    battle = {"turn": 1, "player": defender, "enemy": pokemon("E", "Pidgey")}
    options = reaction_options(battle, "PLAYER")
    assert any(row.get("policy") == "REDIRECT" and row.get("method_move_id") == "GUST" for row in options)
    assert any(row.get("policy") == "BLOCK" and row.get("method_move_id") == "HARDEN" for row in options)


def test_redirect_does_not_apply_to_beam_when_using_gust():
    gust = move("GUST", "Gust", delivery="WAVE", damage_class="SPECIAL", effects=["CREATE_WIND"])
    attacker = pokemon("E", "Pikachu", speed=90, moves=[move("THUNDER-SHOCK", "Thunder Shock", delivery="BEAM", damage_class="SPECIAL")])
    defender = pokemon("P", "Butterfree", speed=70, moves=[gust])
    battle = {"turn": 1, "player": defender, "enemy": attacker, "log": []}
    result = arm_reaction(battle, "PLAYER", "REDIRECT", method_move_id="GUST")
    assert result["accepted"] is True
    set_incoming_reaction_context(defender, attacker["moves"][0])
    assert reaction_accuracy_multiplier(attacker, defender) == 1.0


def test_redirect_projectile_consumes_defense_pp_when_triggered():
    gust = move("GUST", "Gust", delivery="WAVE", damage_class="SPECIAL", pp=5, effects=["CREATE_WIND"])
    incoming = move("POISON-STING", "Poison Sting", delivery="PROJECTILE", damage_class="PHYSICAL")
    attacker = pokemon("E", "Weedle", speed=50, moves=[incoming])
    defender = pokemon("P", "Butterfree", speed=70, moves=[gust])
    battle = {"turn": 1, "phase": "ACTION", "player": defender, "enemy": attacker, "log": []}
    arm_reaction(battle, "PLAYER", "REDIRECT", method_move_id="GUST")
    set_incoming_reaction_context(defender, incoming)
    assert reaction_accuracy_multiplier(attacker, defender) < 1.0
    battle["log"].extend([
        {"kind": "MOVE", "actor": "E", "move_id": "POISON-STING", "text": "Weedle usa Poison Sting."},
        {"kind": "MISS", "actor": "E", "target": "P", "text": "El ataque falla."},
    ])
    settled = settle_incoming_attack_reaction(battle, "PLAYER", 0)
    assert settled["consumed"] is True
    assert settled["success"] is True
    assert battle["log"][-1]["kind"] == "REDIRECT_SUCCESS"
    assert defender["moves"][0]["pp_current"] == 4


def test_harden_block_ignores_special_projectile_and_preserves_pp():
    harden = move("HARDEN", "Harden", delivery="SELF", damage_class="STATUS", pp=7, effects=["HARDEN_BODY"])
    incoming = move("EMBER", "Ember", delivery="PROJECTILE", damage_class="SPECIAL")
    attacker = pokemon("E", "Charmander", moves=[incoming])
    defender = pokemon("P", "Metapod", moves=[harden])
    battle = {"turn": 1, "phase": "ACTION", "player": defender, "enemy": attacker, "log": []}
    arm_reaction(battle, "PLAYER", "BLOCK", method_move_id="HARDEN")
    set_incoming_reaction_context(defender, incoming)
    assert reaction_accuracy_multiplier(attacker, defender) == 1.0
    battle["log"].append({"kind": "MOVE", "actor": "E", "move_id": "EMBER", "text": "Charmander usa Ember."})
    settled = settle_incoming_attack_reaction(battle, "PLAYER", 0)
    assert settled["consumed"] is False
    assert settled["status"] == "REACTION_NOT_COMPATIBLE_WITH_MOVE"
    assert defender["moves"][0]["pp_current"] == 7
    assert defender["battle_reaction"]["armed"] is True


def test_intercept_is_not_offered_without_real_protected_target():
    defender = pokemon("P", "Pikachu")
    battle = {"turn": 1, "player": defender, "enemy": pokemon("E", "Rattata")}
    assert not any(row.get("policy") == "INTERCEPT" for row in reaction_options(battle, "PLAYER"))


def test_intercept_is_gated_on_explicit_protected_target():
    defender = pokemon("P", "Pikachu")
    battle = {
        "turn": 1,
        "player": defender,
        "enemy": pokemon("E", "Rattata"),
        "protected_target": {"entity_id": "ALLY-1", "name": "Entrenador"},
    }
    assert any(row.get("policy") == "INTERCEPT" for row in reaction_options(battle, "PLAYER"))
