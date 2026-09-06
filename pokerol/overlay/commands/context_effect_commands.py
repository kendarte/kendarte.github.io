from evennia import Command

from services.context_effect_engine import (
    CONTEXT_EFFECT_BUILD,
    inspect_context_effects,
    set_context_effect_active,
)
from services.npc_simulation import find_npc


class CmdSizaContextEffects(Command):
    """Inspect explicit decision effects stored in one NPC's memories/relationships."""

    key = "siza-context-effects"
    aliases = ["context-effects", "memory-effects"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        self.caller.msg(f"=== SIZA CONTEXT EFFECTS | {CONTEXT_EFFECT_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={npc.db.npc_id}")
        rows = inspect_context_effects(npc)
        if not rows:
            self.caller.msg("  effects=NONE")
        for row in rows:
            effect = row.get("effect") or {}
            self.caller.msg(
                f"  {effect.get('id')} | source={row.get('source')} | enabled={bool(effect.get('enabled', False))} | "
                f"value={int(effect.get('value', 0) or 0):+} | subject={row.get('subject_name') or row.get('subject_npc_id') or 'NONE'}"
            )
            self.caller.msg(
                f"    container={row.get('container_id') or 'NONE'} | when={effect.get('when') or {}} | "
                f"status={effect.get('canon_status') or 'prototype'}"
            )
        self.caller.msg("===============================================")


class CmdSizaContextEffectToggle(Command):
    """Admin/debug: toggle one explicit memory/relationship decision effect."""

    key = "siza-context-effect-toggle"
    aliases = ["context-effect-toggle", "memory-effect-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-context-effect-toggle <NPC> <EFFECT_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        effect_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = set_context_effect_active(npc, effect_id, state_word == "on")
        if not packet:
            self.caller.msg(f"Effect no encontrado en memories/relationships de {npc.key}: {effect_id}")
            return

        effect = packet.get("effect") or {}
        self.caller.msg(
            f"{npc.key}: {effect_id} | source={packet.get('source')} | enabled={bool(effect.get('enabled'))} | "
            f"value={int(effect.get('value', 0) or 0):+} | when={effect.get('when') or {}}"
        )
