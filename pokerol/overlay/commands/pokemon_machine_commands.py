from evennia import Command

from services.pokemon_bag_engine import bag_state
from services.pokemon_battle_runtime import current_battle
from services.pokemon_machine_engine import machine_state, teach_party_machine


def _in_active_battle(actor):
    battle = current_battle(actor)
    return bool(battle and str(battle.get("status") or "").upper() == "ACTIVE")


class CmdPokerolMachines(Command):
    key = "maquinas"
    aliases = ["machines", "tms", "hms"]
    locks = "cmd:all()"

    def func(self):
        items = (bag_state(self.caller).get("items") or {})
        machine_ids = [key for key, count in sorted(items.items()) if count > 0 and str(key).upper().startswith(("TM", "HM"))]
        if not machine_ids:
            self.caller.msg("No tienes TM/HM en la bolsa.")
            return
        self.caller.msg("=== TM / HM ===")
        for machine_id in machine_ids:
            state = machine_state(machine_id)
            if state.get("exists"):
                reusable = "REUTILIZABLE" if state.get("reusable") else "CONSUMIBLE"
                self.caller.msg(
                    f"{machine_id} x{items[machine_id]} | {state.get('move_name')} [{state.get('move_id')}] | {reusable}"
                )
            else:
                self.caller.msg(f"{machine_id} x{items[machine_id]} | sin move registrado")


class CmdPokerolTeachMachine(Command):
    key = "ensenar"
    aliases = ["enseñar", "teach-machine", "usar-maquina"]
    locks = "cmd:all()"

    def func(self):
        if _in_active_battle(self.caller):
            self.caller.msg("No puedes enseñar una TM/HM durante una batalla activa.")
            return
        parts = str(self.args or "").strip().split()
        if len(parts) < 2:
            self.caller.msg("Uso: ensenar <TM/HM_ID> <slot 1-6> [MOVE_ID_A_REEMPLAZAR]")
            return
        machine_id = parts[0].upper()
        try:
            slot = int(parts[1]) - 1
        except ValueError:
            self.caller.msg("El slot debe ser 1-6.")
            return
        replace_move_id = parts[2] if len(parts) > 2 else ""
        result = teach_party_machine(
            self.caller,
            slot,
            machine_id,
            replace_move_id=replace_move_id,
        )
        status = result.get("status")
        if not result.get("accepted"):
            self.caller.msg(f"{status}")
            return
        if status == "MACHINE_LEARNED_LOADOUT_FULL":
            active = ", ".join(result.get("active_move_ids") or [])
            self.caller.msg(
                f"{result.get('move_name')} fue aprendido, pero el loadout está lleno. "
                f"Activos: {active}. Para equiparlo: ensenar {machine_id} {slot + 1} <MOVE_ID_A_REEMPLAZAR>"
            )
            return
        if result.get("already_known") and not result.get("replaced_move_id"):
            self.caller.msg(f"{result.get('move_name')} ya estaba aprendido.")
            return
        replaced = f" | reemplaza {result.get('replaced_move_id')}" if result.get("replaced_move_id") else ""
        reusable = " | HM/reutilizable" if result.get("reusable") else " | TM consumida"
        self.caller.msg(f"{status} | {result.get('move_name')} equipado{replaced}{reusable}")
