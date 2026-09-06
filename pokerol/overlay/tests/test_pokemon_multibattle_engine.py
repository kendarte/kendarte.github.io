import random

from services.pokemon_battle_engine import normalize_pokemon
from services.pokemon_multibattle_engine import (
    human_order_requirements,
    resolve_locked_round,
    terminal_team_state,
    validate_order,
)


def _move(move_id="TACKLE", *, power=40, priority=0, pp=20, damage_class="PHYSICAL"):
    return {
        "move_id": move_id,
        "name": move_id.replace("-", " ").title(),
        "pokemon_type": "NORMAL",
        "damage_class": damage_class,
        "power": power,
        "accuracy": 100,
        "priority": priority,
        "pp": pp,
        "delivery": "CONTACT",
        "world_enabled": False,
        "world_effects": [],
        "materials": ["CREATURE"],
        "requirements": {},
    }


def _pokemon(entity_id, name, *, speed=50, hp=80, attack=60, defense=50, moves=None):
    profile = {
        "entity_id": entity_id,
        "species_id": entity_id,
        "species_name": name,
        "level": 25,
        "types": ["Normal"],
        "base_stats": {"HP": hp, "ATK": attack, "DEF": defense, "SPA": 50, "SPD": 50, "SPE": speed},
        "moves": moves or [_move()],
        "known_moves": [row["move_id"] for row in (moves or [_move()])],
        "wild": False,
    }
    return normalize_pokemon(profile)


def _human(combatant_id, participant_id, team, pokemon):
    return {
        "combatant_id": combatant_id,
        "controller_kind": "HUMAN",
        "controller_participant_id": participant_id,
        "actor_dbref": 1 if team == "A" else 2,
        "trainer_name": participant_id,
        "team": team,
        "pokemon": pokemon,
        "active": True,
        "needs_switch": False,
    }


def _ai(combatant_id, team, pokemon):
    return {
        "combatant_id": combatant_id,
        "controller_kind": "AI",
        "controller_participant_id": "AI",
        "actor_dbref": None,
        "trainer_name": "AI",
        "team": team,
        "pokemon": pokemon,
        "active": True,
        "needs_switch": False,
    }


def _state(combatants):
    return {
        "session_id": "TEST-MULTI",
        "status": "ACTIVE",
        "phase": "COMMAND",
        "turn": 1,
        "combatants": combatants,
        "pending_orders": {},
        "log": [],
    }


def test_human_order_requirements_lists_each_human_controller_once():
    state = _state([
        _human("A1", "P1", "A", _pokemon("A1", "Pikachu")),
        _human("B1", "P2", "B", _pokemon("B1", "Rattata")),
        _ai("B2", "B", _pokemon("B2", "Caterpie")),
    ])
    assert human_order_requirements(state) == ["P1", "P2"]


def test_validate_order_rejects_ally_target():
    state = _state([
        _human("A1", "P1", "A", _pokemon("A1", "Pikachu")),
        _human("A2", "P2", "A", _pokemon("A2", "Pidgey")),
        _ai("B1", "B", _pokemon("B1", "Caterpie")),
    ])
    result = validate_order(state, "P1", {"type": "MOVE", "move_id": "TACKLE", "target_entity_id": "A2"})
    assert result["accepted"] is False
    assert result["status"] == "INVALID_TARGET"
    assert result["valid_target_ids"] == ["B1"]


def test_multitarget_requires_explicit_target():
    state = _state([
        _human("A1", "P1", "A", _pokemon("A1", "Pikachu")),
        _ai("B1", "B", _pokemon("B1", "Caterpie")),
        _ai("B2", "B", _pokemon("B2", "Weedle")),
    ])
    result = validate_order(state, "P1", {"type": "MOVE", "move_id": "TACKLE"})
    assert result["accepted"] is False
    assert result["status"] == "INVALID_TARGET"
    assert set(result["valid_target_ids"]) == {"B1", "B2"}


def test_round_waits_until_every_required_human_locks_order():
    state = _state([
        _human("A1", "P1", "A", _pokemon("A1", "Pikachu")),
        _human("B1", "P2", "B", _pokemon("B1", "Rattata")),
    ])
    result = resolve_locked_round(
        state,
        {"P1": {"type": "MOVE", "move_id": "TACKLE", "target_entity_id": "B1", "actor_entity_id": "A1"}},
        rng=random.Random(4),
    )
    assert result["accepted"] is False
    assert result["status"] == "WAITING_FOR_ORDERS"
    assert result["missing_participant_ids"] == ["P2"]


def test_shared_round_consumes_pp_for_both_human_actions():
    state = _state([
        _human("A1", "P1", "A", _pokemon("A1", "Pikachu", speed=80)),
        _human("B1", "P2", "B", _pokemon("B1", "Rattata", speed=70)),
    ])
    orders = {
        "P1": {"type": "MOVE", "move_id": "TACKLE", "target_entity_id": "B1", "actor_entity_id": "A1"},
        "P2": {"type": "MOVE", "move_id": "TACKLE", "target_entity_id": "A1", "actor_entity_id": "B1"},
    }
    result = resolve_locked_round(state, orders, rng=random.Random(7))
    assert result["accepted"] is True
    combatants = result["state"]["combatants"]
    pp = {row["combatant_id"]: row["pokemon"]["moves"][0]["pp_current"] for row in combatants}
    assert pp["A1"] == 19
    assert pp["B1"] == 19


def test_priority_move_resolves_before_faster_normal_move():
    quick = _move("QUICK-ATTACK", power=300, priority=1)
    tackle = _move("TACKLE", power=40, priority=0)
    state = _state([
        _human("A1", "P1", "A", _pokemon("A1", "Rattata", speed=20, attack=120, moves=[quick])),
        _human("B1", "P2", "B", _pokemon("B1", "Pidgey", speed=120, hp=20, defense=20, moves=[tackle])),
    ])
    orders = {
        "P1": {"type": "MOVE", "move_id": "QUICK-ATTACK", "target_entity_id": "B1", "actor_entity_id": "A1"},
        "P2": {"type": "MOVE", "move_id": "TACKLE", "target_entity_id": "A1", "actor_entity_id": "B1"},
    }
    result = resolve_locked_round(state, orders, rng=random.Random(1))
    initiative = result["initiative"]
    assert initiative[0]["actor_combatant_id"] == "A1"
    b1 = next(row for row in result["state"]["combatants"] if row["combatant_id"] == "B1")
    assert b1["pokemon"]["hp_current"] == 0


def test_zero_alive_teams_is_draw_terminal_state():
    a = _human("A1", "P1", "A", _pokemon("A1", "Pikachu"))
    b = _human("B1", "P2", "B", _pokemon("B1", "Rattata"))
    a["pokemon"]["hp_current"] = 0
    b["pokemon"]["hp_current"] = 0
    terminal = terminal_team_state([a, b])
    assert terminal == {"terminal": True, "outcome": "DRAW", "winning_team": ""}
    result = resolve_locked_round(_state([a, b]), {}, rng=random.Random(2))
    assert result["accepted"] is True
    assert result["state"]["status"] == "COMPLETE"
    assert result["state"]["outcome"] == "DRAW"
