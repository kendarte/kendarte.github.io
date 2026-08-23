from evennia import Command

from services.npc_decision import (
    DECISION_BUILD,
    choose_goal,
    decision_step,
    set_goal_active,
)
from services.npc_simulation import find_npc


def _candidate_line(item, selected_id=None):
    marker = "SELECTED" if item.get("id") == selected_id else "candidate"
    reachable = "YES" if item.get("reachable") else "NO"
    return (
        f"[{marker}] {item.get('type')} | priority={item.get('priority')} | "
        f"id={item.get('id')} | target={item.get('target_name') or item.get('target_room_key')} | "
        f"reachable={reachable} | path={item.get('path_length')} | source={item.get('source')}"
    )


class CmdSizaDecide(Command):
    """Inspect which persistent goal an NPC would choose, without moving it."""

    key = "siza-decide"
    aliases = ["decide-npc"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        decision = choose_goal(npc)
        selected = decision.get("selected")
        selected_id = selected.get("id") if selected else None

        self.caller.msg(f"=== SIZA DECISION | {DECISION_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | location={decision.get('location')}")
        candidates = decision.get("candidates") or []
        if not candidates:
            self.caller.msg("Candidates: NONE")
        else:
            self.caller.msg("Candidates:")
            for item in candidates:
                self.caller.msg("  " + _candidate_line(item, selected_id=selected_id))

        if selected:
            self.caller.msg(
                f"Winner: {selected.get('type')} {selected.get('id')} -> "
                f"{selected.get('target_name')} | priority={selected.get('priority')}"
            )
        else:
            self.caller.msg("Winner: NONE")
        self.caller.msg("No movement executed.")
        self.caller.msg("========================================")


class CmdSizaGoalToggle(Command):
    """Admin/debug: activate/deactivate one already-authored persistent goal."""

    key = "siza-goal-toggle"
    aliases = ["goal-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-goal-toggle <NPC> <GOAL_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        goal_id = parts[-2]
        npc_query = " ".join(parts[:-2])

        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        active = state_word == "on"
        if not set_goal_active(npc, goal_id, active):
            self.caller.msg(f"Goal no encontrado en {npc.key}: {goal_id}")
            return

        self.caller.msg(
            f"Goal {goal_id} en {npc.key}: {'ACTIVE' if active else 'INACTIVE'}."
        )


class CmdSizaDecisionStep(Command):
    """Choose the winning authorized goal and execute at most one real Exit hop."""

    key = "siza-decision-step"
    aliases = ["decision-step"]
    locks = "cmd:perm(Admin)"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        result = decision_step(npc)
        status = result.get("status")
        goal_id = result.get("goal_id")
        goal_type = result.get("goal_type")
        priority = result.get("priority")

        if status in {"MOVED_GOAL", "ARRIVED_GOAL"}:
            self.caller.msg(
                f"[DECISION] {npc.key}: {goal_type} {goal_id} (priority={priority})"
            )
            self.caller.msg(
                f"[DECISION] {result.get('from')} -> {result.get('to')} por '{result.get('used_exit')}' "
                f"| target={result.get('target')}"
            )
            return

        if status in {"AT_GOAL", "GOAL_COMPLETED"}:
            self.caller.msg(
                f"[DECISION] {npc.key}: {status} | {goal_type} {goal_id} | "
                f"activity={result.get('activity')}"
            )
            return

        if status == "NO_PATH":
            self.caller.msg(
                f"[DECISION] {npc.key}: NO_PATH | goal={goal_id} | "
                f"{result.get('from')} -> {result.get('target')}"
            )
            return

        self.caller.msg(f"[DECISION] {status} | {result}")
