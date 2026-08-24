from evennia import Command

from services.consequence_engine import (
    CONSEQUENCE_BUILD,
    inspect_consequence_state,
    set_consequence_rule_active,
)


class CmdSizaConsequences(Command):
    """Inspect persistent Action -> Consequence rules and recent emitted actions."""

    key = "siza-consequences"
    aliases = ["consequences-state", "action-consequences"]
    locks = "cmd:all()"

    def func(self):
        state = inspect_consequence_state()
        self.caller.msg(f"=== SIZA ACTION / CONSEQUENCE | {CONSEQUENCE_BUILD} ===")
        if not state.get("registry_exists"):
            self.caller.msg("Registry: NONE")
            self.caller.msg("====================================================")
            return

        rules = state.get("rules") or []
        if not rules:
            self.caller.msg("Rules: NONE")
        else:
            self.caller.msg("Rules:")
            for rule in rules:
                memory = dict(rule.get("memory") or {})
                effect = dict(memory.get("decision_effect") or {})
                knowledge = dict(rule.get("knowledge") or {})
                extras = []
                if effect:
                    extras.append(
                        f"memory_effect={effect.get('id')} value={int(effect.get('value', 0) or 0):+} "
                        f"when={effect.get('when') or {}}"
                    )
                if knowledge:
                    extras.append(
                        f"knowledge={knowledge.get('knowledge_key')} mode={knowledge.get('mode') or 'SET'} "
                        f"value={knowledge.get('value')}"
                    )
                extra_text = " | " + " | ".join(extras) if extras else ""
                self.caller.msg(
                    f"  {rule.get('id')} | enabled={bool(rule.get('enabled'))} | "
                    f"when={rule.get('when') or {}} | recipients={rule.get('recipient_mode') or 'ACTION_RECIPIENTS'}"
                    f"{extra_text} | status={rule.get('canon_status') or 'prototype'}"
                )

        log = state.get("action_log") or []
        self.caller.msg(f"Recent actions: {len(log)}")
        for entry in log[-5:]:
            applied = []
            for result in entry.get("rule_results") or []:
                applied.append(f"{result.get('rule_id')}:{result.get('status')}")
            subject = ""
            if entry.get("order_id"):
                subject = f" | order={entry.get('order_id')}"
            elif entry.get("task_id"):
                subject = f" | task={entry.get('task_id')}"
            self.caller.msg(
                f"  {entry.get('action_id')} | type={entry.get('action_type')} | "
                f"actor={entry.get('actor_name') or entry.get('actor_npc_id')} | "
                f"occurrence={entry.get('occurrence')}{subject} | recipients={entry.get('recipient_ids') or []} | "
                f"rules={applied or 'NONE'}"
            )
            for result in entry.get("rule_results") or []:
                for row in result.get("applied") or []:
                    details = []
                    if row.get("memory_applied"):
                        details.append(
                            f"memory={row.get('memory_id')} occurrences={row.get('occurrences_after')}"
                        )
                    if row.get("knowledge_applied"):
                        details.append(
                            f"knowledge={row.get('knowledge_key')} {row.get('knowledge_before')}->{row.get('knowledge_after')} "
                            f"mode={row.get('knowledge_mode')} changed={row.get('knowledge_changed')}"
                        )
                    self.caller.msg(
                        f"    {result.get('rule_id')} -> {row.get('npc_name') or row.get('npc_id')} | "
                        + (" | ".join(details) if details else row.get("status", "APPLIED"))
                    )
        self.caller.msg("====================================================")


class CmdSizaConsequenceToggle(Command):
    """Admin/debug: enable or disable one persistent consequence rule."""

    key = "siza-consequence-toggle"
    aliases = ["consequence-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 2 or parts[1].lower() not in {"on", "off"}:
            self.caller.msg("Uso: siza-consequence-toggle <RULE_ID> <on|off>")
            return

        rule_id, state_word = parts
        packet = set_consequence_rule_active(rule_id, state_word.lower() == "on")
        if not packet:
            self.caller.msg(f"Consequence rule no encontrada: {rule_id}")
            return
        self.caller.msg(
            f"{rule_id}: enabled={bool(packet.get('enabled'))} | "
            f"when={packet.get('when') or {}} | status={packet.get('canon_status') or 'prototype'}"
        )
