from evennia import Command

from services.decision_personality import (
    DECISION_PERSONALITY_BUILD,
    inspect_decision_personality,
    set_decision_modifier_active,
)
from services.npc_simulation import find_npc


def _signed(value):
    try:
        return f"{int(value or 0):+}"
    except (TypeError, ValueError):
        return "+0"


class CmdSizaPersonality(Command):
    """Inspect data-driven decision modifiers for one NPC."""

    key = "siza-personality"
    aliases = ["decision-personality", "npc-personality"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("Uso: siza-personality <NPC>")
            return

        state = inspect_decision_personality(npc)
        self.caller.msg(f"=== SIZA PERSONALITY | {DECISION_PERSONALITY_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={state.get('npc_id')}")

        priorities = state.get("decision_priorities") or {}
        biases = state.get("decision_biases") or {}
        self.caller.msg(f"Base priority overrides: {priorities if priorities else 'NONE'}")
        self.caller.msg(f"Type biases: {biases if biases else 'NONE'}")

        modifiers = state.get("decision_modifiers") or []
        if not modifiers:
            self.caller.msg("Modifiers: NONE")
        else:
            self.caller.msg("Modifiers:")
            for item in modifiers:
                self.caller.msg(
                    f"  {item.get('id')} | enabled={bool(item.get('enabled'))} | "
                    f"value={_signed(item.get('value'))} | when={item.get('when') or {}} | "
                    f"status={item.get('canon_status') or 'prototype'}"
                )
        self.caller.msg("===============================================")


class CmdSizaPersonalityToggle(Command):
    """Admin/debug: enable or disable one authored decision modifier."""

    key = "siza-personality-toggle"
    aliases = ["personality-toggle", "decision-mod-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-personality-toggle <NPC> <MODIFIER_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        modifier_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        modifier = set_decision_modifier_active(npc, modifier_id, state_word == "on")
        if not modifier:
            self.caller.msg(f"Modifier no encontrado en {npc.key}: {modifier_id}")
            return

        self.caller.msg(
            f"{npc.key}: {modifier_id} | enabled={bool(modifier.get('enabled'))} | "
            f"value={_signed(modifier.get('value'))} | when={modifier.get('when') or {}}"
        )
