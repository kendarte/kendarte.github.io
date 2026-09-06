from services.pokemon_battle_engine import normalize_pokemon
from services.pokemon_multiplayer_reaction_engine import expire_unused_intercepts, resolve_interceptor


class _AlwaysSuccessRng:
    def random(self):
        return 0.0


def _pokemon(entity_id, name, speed=50, hp=60):
    return normalize_pokemon({
        "entity_id": entity_id,
        "species_id": entity_id,
        "species_name": name,
        "level": 20,
        "types": ["Normal"],
        "base_stats": {"HP": hp, "ATK": 50, "DEF": 50, "SPA": 50, "SPD": 50, "SPE": speed},
        "moves": [{
            "move_id": "TACKLE", "name": "Tackle", "pokemon_type": "Normal",
            "damage_class": "PHYSICAL", "power": 40, "accuracy": 100,
            "priority": 0, "pp": 35, "delivery": "CONTACT",
            "world_enabled": False, "world_effects": [], "materials": ["CREATURE"],
            "requirements": {},
        }],
    })


def _row(combatant_id, team, pokemon):
    return {
        "combatant_id": combatant_id,
        "controller_kind": "HUMAN",
        "controller_participant_id": "P-" + combatant_id,
        "team": team,
        "pokemon": pokemon,
        "active": True,
        "needs_switch": False,
    }


def test_intercept_success_replaces_real_defender():
    attacker = _row("B1", "B", _pokemon("B1", "Rattata", speed=40))
    protected = _row("A1", "A", _pokemon("A1", "Caterpie", speed=30))
    interceptor = _row("A2", "A", _pokemon("A2", "Pidgey", speed=80))
    interceptor["pokemon"]["battle_reaction"] = {
        "policy": "INTERCEPT",
        "armed": True,
        "armed_turn": 1,
        "protected_target": {"combatant_id": "A1", "pokemon_name": "Caterpie"},
    }
    combatants = [attacker, protected, interceptor]
    result = resolve_interceptor(combatants, attacker, protected, _AlwaysSuccessRng())
    assert result["triggered"] is True
    assert result["success"] is True
    assert result["target"]["combatant_id"] == "A2"
    assert interceptor["pokemon"]["battle_reaction"]["armed"] is False


def test_fainted_interceptor_cannot_protect_ally():
    attacker = _row("B1", "B", _pokemon("B1", "Rattata"))
    protected = _row("A1", "A", _pokemon("A1", "Caterpie"))
    interceptor = _row("A2", "A", _pokemon("A2", "Pidgey"))
    interceptor["pokemon"]["hp_current"] = 0
    interceptor["pokemon"]["battle_reaction"] = {
        "policy": "INTERCEPT",
        "armed": True,
        "armed_turn": 1,
        "protected_target": {"combatant_id": "A1"},
    }
    result = resolve_interceptor([attacker, protected, interceptor], attacker, protected, _AlwaysSuccessRng())
    assert result["triggered"] is False
    assert result["target"]["combatant_id"] == "A1"


def test_unused_intercept_expires_after_round():
    protector = _row("A2", "A", _pokemon("A2", "Pidgey"))
    protector["pokemon"]["battle_reaction"] = {
        "policy": "INTERCEPT",
        "armed": True,
        "armed_turn": 3,
        "protected_target": {"combatant_id": "A1"},
    }
    expired = expire_unused_intercepts([protector])
    assert expired == ["A2"]
    assert protector["pokemon"]["battle_reaction"]["policy"] == "NONE"
    assert protector["pokemon"]["battle_reaction"]["armed"] is False
