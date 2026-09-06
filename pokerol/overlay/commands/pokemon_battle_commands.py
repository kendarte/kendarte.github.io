import base64
import json

from evennia import Command

from services.pokemon_battle_runtime import (
    abandon_battle,
    current_battle,
    start_pokemon_battle,
)
from services.pokemon_battle_tactical_runtime import (
    emit_position_options,
    submit_tactical_battle_action,
)
from services.pokemon_party_engine import active_pokemon


def _decode_token(token):
    raw = str(token or "").strip()
    if not raw:
        raise ValueError("EMPTY_TOKEN")
    raw += "=" * (-len(raw) % 4)
    data = base64.urlsafe_b64decode(raw.encode("ascii"))
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("ACTION_NOT_OBJECT")
    return value


def _demo_move(move_id, name, pokemon_type, power, accuracy, damage_class="SPECIAL", priority=0):
    return {
        "move_id": move_id,
        "name": name,
        "pokemon_type": pokemon_type,
        "damage_class": damage_class,
        "power": power,
        "accuracy": accuracy,
        "priority": priority,
        "pp": 20,
        "world_enabled": False,
        "world_effects": [],
        "materials": ["CREATURE"],
        "delivery": "PROJECTILE",
        "requirements": {},
    }


def _demo_pikachu():
    return {
        "entity_id": "DEMO-PLAYER-PIKACHU",
        "species_id": "PKMN-025",
        "species_name": "Pikachu",
        "level": 8,
        "types": ["Electric"],
        "base_stats": {"HP": 35, "ATK": 55, "DEF": 40, "SPA": 50, "SPD": 50, "SPE": 90},
        "locomotion": ["WALK", "CLIMB"],
        "body_tags": ["SMALL", "CLIMBER"],
        "moves": [
            _demo_move("THUNDER-SHOCK", "Thunder Shock", "Electric", 40, 100),
            _demo_move("QUICK-ATTACK", "Quick Attack", "Normal", 40, 100, "PHYSICAL", 1),
        ],
        "sprite": {
            "front": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
            "back": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/25.png",
            "icon": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
            "scale": 1.25,
        },
        "wild": False,
    }


def _demo_caterpie():
    return {
        "entity_id": "DEMO-WILD-CATERPIE",
        "species_id": "PKMN-010",
        "species_name": "Caterpie",
        "level": 5,
        "types": ["Bug"],
        "base_stats": {"HP": 45, "ATK": 30, "DEF": 35, "SPA": 20, "SPD": 20, "SPE": 45},
        "moves": [
            _demo_move("TACKLE", "Tackle", "Normal", 40, 100, "PHYSICAL"),
            _demo_move("STRING-SHOT", "String Shot", "Bug", 0, 95, "STATUS"),
        ],
        "sprite": {
            "front": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/10.png",
            "back": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/10.png",
            "icon": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/10.png",
            "scale": 1.3,
        },
        "wild": True,
    }


class CmdPokerolBattleState(Command):
    key = "batalla"
    aliases = ["pokemon-battle", "pokerol-battle"]
    locks = "cmd:all()"

    def func(self):
        battle = current_battle(self.caller)
        if not battle:
            self.caller.msg("No hay una batalla Pokémon activa.")
            return
        player = battle.get("player") or {}
        enemy = battle.get("enemy") or {}
        self.caller.msg(
            f"BATTLE {battle.get('battle_id')} | {battle.get('status')} | turno={battle.get('turn')} | fase={battle.get('phase')}\n"
            f"{player.get('name')} HP {player.get('hp_current')}/{player.get('hp_max')} vs "
            f"{enemy.get('name')} HP {enemy.get('hp_current')}/{enemy.get('hp_max')}"
        )


class CmdPokerolBattleTest(Command):
    key = "batalla-prueba"
    aliases = ["pokemon-battle-test"]
    locks = "cmd:perm(Admin)"

    def func(self):
        player = active_pokemon(self.caller) or _demo_pikachu()
        result = start_pokemon_battle(
            self.caller,
            player,
            _demo_caterpie(),
            battle_kind="WILD",
            source_event_id="DEMO",
        )
        self.caller.msg(f"Pokémon battle runtime: {result.get('status')}")


class CmdPokerolBattleAction(Command):
    key = "pokerol-battle-action"
    locks = "cmd:all()"

    def func(self):
        try:
            action = _decode_token(self.args)
        except Exception as exc:
            self.caller.msg(f"Acción de batalla inválida: {exc}")
            return
        result = submit_tactical_battle_action(self.caller, action)
        if not result.get("accepted"):
            self.caller.msg(f"Acción rechazada: {result.get('status')}")


class CmdPokerolPositionOptions(Command):
    key = "pokerol-position-options"
    aliases = ["posiciones-batalla"]
    locks = "cmd:all()"

    def func(self):
        result = emit_position_options(self.caller)
        if not result.get("accepted"):
            self.caller.msg(f"Posición no disponible: {result.get('status')}")


class CmdPokerolBattleMove(Command):
    key = "movimiento"
    aliases = ["move"]
    locks = "cmd:all()"

    def func(self):
        move_id = str(self.args or "").strip()
        if not move_id:
            self.caller.msg("Uso: movimiento <MOVE_ID>")
            return
        result = submit_tactical_battle_action(self.caller, {"type": "MOVE", "move_id": move_id})
        self.caller.msg(str(result.get("status")))


class CmdPokerolBattleCapture(Command):
    key = "capturar"
    aliases = ["capture"]
    locks = "cmd:all()"

    def func(self):
        item_id = str(self.args or "").strip().upper() or "POKE_BALL"
        result = submit_tactical_battle_action(self.caller, {"type": "CAPTURE", "item_id": item_id})
        self.caller.msg(str(result.get("status")))


class CmdPokerolBattleRun(Command):
    key = "huir"
    aliases = ["run"]
    locks = "cmd:all()"

    def func(self):
        result = submit_tactical_battle_action(self.caller, {"type": "RUN"})
        self.caller.msg(str(result.get("status")))


class CmdPokerolBattleAbandon(Command):
    key = "batalla-abandonar"
    aliases = ["pokemon-battle-abandon"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = abandon_battle(self.caller)
        self.caller.msg(str(result.get("status")))
