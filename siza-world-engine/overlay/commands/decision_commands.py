from evennia import Command

from services.npc_decision import (
    DECISION_BUILD,
    choose_goal,
    decision_step,
    set_goal_active,
)
from services.npc_simulation import find_npc
from services.world_clock import format_world_time, world_clock_state


def _candidate_line(item, selected_id=None):
    marker = "SELECTED" if item.get("id") == selected_id else "candidate"
    reachable = "YES" if item.get("reachable") else "NO"
    progress = ""
    if item.get("type") == "JOB" and item.get("work_required") is not None:
        progress = f" | work={item.get('work_done')}/{item.get('work_required')}"
    claim = ""
    if item.get("claim_npc_name"):
        claim = f" | claim={item.get('claim_npc_name')}"
    schedule = ""
    if item.get("type") == "JOB" and item.get("shift_schedule"):
        schedule = f" | shift={item.get('shift_schedule')}"
    elif item.get("type") == "ROUTINE" and item.get("routine_schedule_label"):
        schedule = f" | schedule={item.get('routine_schedule_label')}"
    return (
        f"[{marker}] {item.get('type')} | priority={item.get('priority')} | "
        f"id={item.get('id')} | target={item.get('target_name') or item.get('target_room_key')} | "
        f"reachable={reachable} | path={item.get('path_length')} | source={item.get('source')}"
        f"{progress}{claim}{schedule}"
    )


class CmdSizaDecide(Command):
    """Inspect which persistent goal an NPC would choose, without moving or claiming it."""

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
        clock = world_clock_state()

        self.caller.msg(f"=== SIZA DECISION | {DECISION_BUILD} ===")
        self.caller.msg(
            f"NPC: {npc.key} | location={decision.get('location')} | "
            f"decision_enabled={decision.get('decision_enabled')} | "
            f"world_time={format_world_time(clock.get('day'), clock.get('minute'))}"
        )
        candidates = decision.get("candidates") or []
        if not candidates:
            self.caller.msg("Candidates: NONE")
        else:
            self.caller.msg("Candidates:")
            for item in candidates:
                self.caller.msg("  " + _candidate_line(item, selected_id=selected_id))

        if selected:
            winner_progress = ""
            if selected.get("type") == "JOB" and selected.get("work_required") is not None:
                winner_progress = f" | work={selected.get('work_done')}/{selected.get('work_required')}"
            winner_claim = ""
            if selected.get("claim_npc_name"):
                winner_claim = f" | claim={selected.get('claim_npc_name')}"
            winner_schedule = ""
            if selected.get("type") == "JOB" and selected.get("shift_schedule"):
                winner_schedule = f" | shift={selected.get('shift_schedule')}"
            elif selected.get("type") == "ROUTINE" and selected.get("routine_schedule_label"):
                winner_schedule = f" | schedule={selected.get('routine_schedule_label')}"
            self.caller.msg(
                f"Winner: {selected.get('type')} {selected.get('id')} -> "
                f"{selected.get('target_name')} | priority={selected.get('priority')}"
                f"{winner_progress}{winner_claim}{winner_schedule}"
            )
        else:
            self.caller.msg("Winner: NONE")
        self.caller.msg("No movement or claim executed.")
        self.caller.msg("========================================")


class CmdSizaDecisionMode(Command):
    """Enable/disable Decision Layer dispatch for one NPC in the World Tick."""

    key = "siza-decision-mode"
    aliases = ["decision-mode"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 2:
            self.caller.msg("Uso: siza-decision-mode <NPC> <on|off>")
            return

        state_word = parts[-1].lower()
        npc_query = " ".join(parts[:-1])
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        npc.db.decision_enabled = state_word == "on"
        mode = "DECISION" if npc.db.decision_enabled else "ROUTINE_V04"
        self.caller.msg(
            f"{npc.key}: decision_enabled={bool(npc.db.decision_enabled)} | world_tick_mode={mode}."
        )


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
    """Choose the winning authorized goal and execute one hop or one work action."""

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
        engine = result.get("engine")

        if result.get("job_claim_acquired"):
            self.caller.msg(
                f"[CLAIM] {goal_id} -> {result.get('job_claim_owner_name') or npc.key}"
            )

        if status in {"MOVED_GOAL", "ARRIVED_GOAL"}:
            self.caller.msg(
                f"[DECISION] {npc.key}: {goal_type} {goal_id} (priority={priority}) | engine={engine}"
            )
            self.caller.msg(
                f"[DECISION] {result.get('from')} -> {result.get('to')} por '{result.get('used_exit')}' "
                f"| target={result.get('target')} | action={result.get('action_kind')}"
            )
            return

        if status == "WORKING_GOAL":
            self.caller.msg(
                f"[DECISION] {npc.key}: WORKING | {goal_id} | "
                f"work={result.get('work_done')}/{result.get('work_required')} "
                f"(+{result.get('work_added')}) | activity={result.get('activity')}"
            )
            return

        if status == "WAITING_GOAL":
            schedule = ""
            if result.get("routine_schedule_label") and result.get("routine_schedule_label") != "ALWAYS":
                schedule = f" | schedule={result.get('routine_schedule_label')}"
            self.caller.msg(
                f"[DECISION] {npc.key}: ROUTINE WAITING | {result.get('location')} | "
                f"activity={result.get('activity')} | hold={result.get('hold_remaining')}{schedule}"
            )
            return

        if status == "GOAL_COMPLETED" and result.get("from") and result.get("to"):
            self.caller.msg(
                f"[DECISION] {npc.key}: GOAL_COMPLETED | {goal_type} {goal_id} (priority={priority})"
            )
            self.caller.msg(
                f"[DECISION] {result.get('from')} -> {result.get('to')} por '{result.get('used_exit')}' "
                f"| activity={result.get('activity')}"
            )
            return

        if status == "GOAL_COMPLETED" and result.get("work_required") is not None:
            self.caller.msg(
                f"[DECISION] {npc.key}: GOAL_COMPLETED | {goal_type} {goal_id} | "
                f"work={result.get('work_done')}/{result.get('work_required')} | "
                f"activity={result.get('activity')}"
            )
            if result.get("job_completion_effects"):
                self.caller.msg(
                    f"[DECISION] completion_effects={result.get('job_completion_effects')}"
                )
            if result.get("job_claim_released"):
                self.caller.msg(f"[CLAIM RELEASED] {goal_id}")
            return

        if status in {"AT_GOAL", "GOAL_COMPLETED"}:
            self.caller.msg(
                f"[DECISION] {npc.key}: {status} | {goal_type} {goal_id} | "
                f"activity={result.get('activity')} | engine={engine}"
            )
            return

        if status == "NO_PATH":
            self.caller.msg(
                f"[DECISION] {npc.key}: NO_PATH | goal={goal_id} | "
                f"{result.get('from')} -> {result.get('target')}"
            )
            return

        self.caller.msg(f"[DECISION] {status} | {result}")
