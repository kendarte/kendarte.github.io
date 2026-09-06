import base64
import json

from evennia import Command

from services.pokemon_multiplayer_reaction_engine import arm_intercept, clear_intercept
from services.pokemon_multiplayer_runtime import submit_multiplayer_order, submit_multiplayer_switch
from services.pokemon_multiplayer_session_engine import (
    accept_invitation,
    add_ai_combatant,
    create_session,
    emit_session,
    invite_actor,
    leave_session,
    public_session,
    session_for_actor,
    set_ready,
    start_session,
)
from services.pokemon_species_registry import spawn_species_profile


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


def _show(caller, result):
    caller.msg(str((result or {}).get("status") or "UNKNOWN"))


class CmdPokerolMultiCreate(Command):
    key = "multi-crear"
    aliases = ["multiplayer-crear", "batalla-multi-crear"]
    locks = "cmd:all()"
    def func(self):
        _show(self.caller, create_session(self.caller, str(self.args or "PVE_COOP").strip().upper() or "PVE_COOP"))


class CmdPokerolMultiInvite(Command):
    key = "multi-invitar"
    aliases = ["multiplayer-invitar", "batalla-multi-invitar"]
    locks = "cmd:all()"
    def func(self):
        parts = str(self.args or "").strip().split()
        if not parts:
            self.caller.msg("Uso: multi-invitar <jugador> [A|B]")
            return
        team = parts[-1].upper() if len(parts) > 1 and parts[-1].upper() in {"A", "B"} else ""
        name = " ".join(parts[:-1] if team else parts).strip()
        target = self.caller.search(name, location=self.caller.location)
        if target:
            _show(self.caller, invite_actor(self.caller, target, team=team))


class CmdPokerolMultiAccept(Command):
    key = "multi-aceptar"
    aliases = ["multiplayer-aceptar", "batalla-multi-aceptar"]
    locks = "cmd:all()"
    def func(self):
        _show(self.caller, accept_invitation(self.caller, str(self.args or "").strip()))


class CmdPokerolMultiReady(Command):
    key = "multi-listo"
    aliases = ["multiplayer-listo", "batalla-multi-listo"]
    locks = "cmd:all()"
    def func(self):
        raw = str(self.args or "si").strip().lower()
        _show(self.caller, set_ready(self.caller, raw not in {"no", "0", "false", "off"}))


class CmdPokerolMultiStart(Command):
    key = "multi-iniciar"
    aliases = ["multiplayer-iniciar", "batalla-multi-iniciar"]
    locks = "cmd:all()"
    def func(self):
        _show(self.caller, start_session(self.caller))


class CmdPokerolMultiLeave(Command):
    key = "multi-salir"
    aliases = ["multiplayer-salir", "batalla-multi-salir"]
    locks = "cmd:all()"
    def func(self):
        _show(self.caller, leave_session(self.caller))


class CmdPokerolMultiState(Command):
    key = "multi-estado"
    aliases = ["multiplayer", "batalla-multi"]
    locks = "cmd:all()"
    def func(self):
        session = session_for_actor(self.caller)
        if not session:
            self.caller.msg("No estás en una sesión multiplayer.")
            return
        state = public_session(session, self.caller)
        self.caller.msg(
            f"{state.get('session_id')} | {state.get('kind')} | {state.get('status')} | "
            f"fase={state.get('phase')} turno={state.get('turn')} | outcome={state.get('outcome') or '-'} | "
            f"jugadores={len(state.get('participants') or [])} combatientes={len(state.get('combatants') or [])}"
        )
        for row in state.get("participants") or []:
            self.caller.msg(f"[{row.get('team')}] {row.get('name')} | {'READY' if row.get('ready') else 'WAIT'} | orden_turno={row.get('submitted_turn') or 0}")


class CmdPokerolMultiOrder(Command):
    key = "multi-orden"
    aliases = ["multiplayer-orden"]
    locks = "cmd:all()"
    def func(self):
        try:
            action = _decode_token(self.args)
        except Exception as exc:
            self.caller.msg(f"Orden multiplayer inválida: {exc}")
            return
        result = submit_multiplayer_order(self.caller, action)
        if not result.get("accepted"):
            self.caller.msg(f"Orden rechazada: {result.get('status')}")


class CmdPokerolMultiMove(Command):
    key = "multi-movimiento"
    aliases = ["multi-move"]
    locks = "cmd:all()"
    def func(self):
        parts = str(self.args or "").strip().split()
        if not parts:
            self.caller.msg("Uso: multi-movimiento <MOVE_ID> [TARGET_ENTITY_ID]")
            return
        action = {"type": "MOVE", "move_id": parts[0]}
        if len(parts) > 1:
            action["target_entity_id"] = parts[1]
        _show(self.caller, submit_multiplayer_order(self.caller, action))


class CmdPokerolMultiProtect(Command):
    key = "multi-proteger"
    aliases = ["multi-interceptar", "multi-protect"]
    locks = "cmd:all()"
    def func(self):
        session = session_for_actor(self.caller)
        if not session:
            self.caller.msg("NO_BATTLE_SESSION")
            return
        target = str(self.args or "").strip()
        if target.lower() in {"no", "none", "off", "cancelar"}:
            result = clear_intercept(session, self.caller)
        else:
            if not target:
                self.caller.msg("Uso: multi-proteger <ALLY_COMBATANT_ID> | multi-proteger no")
                return
            result = arm_intercept(session, self.caller, target)
        if result.get("accepted"):
            emit_session(session, event="REACTION")
        _show(self.caller, result)


class CmdPokerolMultiSwitch(Command):
    key = "multi-cambiar"
    aliases = ["multi-switch"]
    locks = "cmd:all()"
    def func(self):
        try:
            slot = int(str(self.args or "").strip()) - 1
        except ValueError:
            self.caller.msg("Uso: multi-cambiar <slot 1-6>")
            return
        _show(self.caller, submit_multiplayer_switch(self.caller, slot))


class CmdPokerolMultiAddEnemy(Command):
    key = "multi-enemigo"
    aliases = ["multi-ai"]
    locks = "cmd:perm(Admin)"
    def func(self):
        parts = str(self.args or "").strip().split()
        if not parts:
            self.caller.msg("Uso: multi-enemigo <SPECIES_ID> [nivel] [A|B]")
            return
        species_id = parts[0]
        level = None
        team = "B"
        if len(parts) > 1:
            try:
                level = int(parts[1])
            except ValueError:
                team = parts[1].upper()
        if len(parts) > 2:
            team = parts[2].upper()
        session = session_for_actor(self.caller)
        if not session:
            self.caller.msg("NO_BATTLE_SESSION")
            return
        profile = spawn_species_profile(species_id, level=level, wild=True)
        if not profile:
            self.caller.msg("SPECIES_NOT_FOUND")
            return
        _show(self.caller, add_ai_combatant(session, profile, team=team))
