from evennia import Command

from services.knowledge_context_engine import (
    KNOWLEDGE_CONTEXT_BUILD,
    inspect_knowledge_context,
    set_knowledge_effect_active,
    set_knowledge_level,
)
from services.npc_simulation import find_npc


class CmdSizaKnowledge(Command):
    """Inspect NPC Knowledge levels, known facts and explicit decision effects."""

    key = "siza-knowledge"
    aliases = ["knowledge-state", "npc-knowledge"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        state = inspect_knowledge_context(npc)
        self.caller.msg(f"=== SIZA KNOWLEDGE | {KNOWLEDGE_CONTEXT_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={state.get('npc_id')}")
        self.caller.msg(f"Levels: {state.get('levels') or {}}")

        rows = state.get("facts") or []
        effects_found = False
        for row in rows:
            effects = row.get("decision_effects") or []
            if not effects:
                continue
            effects_found = True
            self.caller.msg(
                f"  {row.get('fact_id')} | key={row.get('knowledge_key')} | "
                f"level={row.get('knowledge_level')} | required={row.get('required_level')} | "
                f"known={bool(row.get('known'))} | status={row.get('canon_status')}"
            )
            for effect in effects:
                try:
                    value = int(effect.get("value", 0) or 0)
                except (TypeError, ValueError):
                    value = 0
                self.caller.msg(
                    f"    effect={effect.get('id')} | enabled={bool(effect.get('enabled'))} | "
                    f"value={value:+} | when={effect.get('when') or {}}"
                )

        if not effects_found:
            self.caller.msg("Decision-aware facts: NONE")
        self.caller.msg("===============================================")


class CmdSizaKnowledgeEffectToggle(Command):
    """Admin/debug: enable or disable one explicit decision effect on a Knowledge fact."""

    key = "siza-knowledge-effect-toggle"
    aliases = ["knowledge-effect-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3 or parts[-1].lower() not in {"on", "off"}:
            self.caller.msg("Uso: siza-knowledge-effect-toggle <NPC> <EFFECT_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        effect_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = set_knowledge_effect_active(npc, effect_id, state_word == "on")
        if not packet:
            self.caller.msg(f"Knowledge effect no encontrado en {npc.key}: {effect_id}")
            return

        effect = packet.get("effect") or {}
        try:
            value = int(effect.get("value", 0) or 0)
        except (TypeError, ValueError):
            value = 0
        self.caller.msg(
            f"{npc.key}: {effect_id} | enabled={bool(effect.get('enabled'))} | value={value:+} | "
            f"fact={packet.get('fact_id')} | key={packet.get('knowledge_key')} | "
            f"level={packet.get('level')} | required={packet.get('required_level')} | "
            f"known={bool(packet.get('known'))} | when={effect.get('when') or {}}"
        )


class CmdSizaKnowledgeSet(Command):
    """Admin/debug: set one persistent Knowledge level on an NPC."""

    key = "siza-knowledge-set"
    aliases = ["knowledge-set"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-knowledge-set <NPC> <KNOWLEDGE_KEY> <LEVEL>")
            return

        try:
            level = int(parts[-1])
        except ValueError:
            self.caller.msg("LEVEL debe ser un entero >= 0.")
            return
        knowledge_key = parts[-2]
        npc_query = " ".join(parts[:-2])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = set_knowledge_level(npc, knowledge_key, level)
        if not packet:
            self.caller.msg("No pude modificar ese Knowledge level.")
            return
        self.caller.msg(
            f"{npc.key}: knowledge {packet.get('knowledge_key')} "
            f"{packet.get('before')} -> {packet.get('after')}"
        )
