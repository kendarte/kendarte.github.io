from evennia import Command

from typeclasses.world_tick import TRACE_LIMIT, world_tick_state


def _need_lines(packet):
    lines = []
    npc = packet.get("npc", "UNKNOWN")
    clock = packet.get("clock")
    if packet.get("error"):
        return [f"[NEED CLOCK] {npc} clock={clock} ERROR={packet.get('error')}"]

    for change in packet.get("changes") or []:
        lines.append(
            f"[NEED CLOCK] {npc} clock={clock} | {change.get('field')} "
            f"{change.get('before')} -> {change.get('after')} "
            f"({change.get('id')})"
        )
    return lines


def _activity_need_lines(packet):
    lines = []
    npc = packet.get("npc", "UNKNOWN")
    kind = packet.get("activity_kind") or "UNKNOWN"
    if packet.get("error"):
        return [f"[NEED ACTIVITY] {npc} action={kind} ERROR={packet.get('error')}"]

    for change in packet.get("changes") or []:
        lines.append(
            f"[NEED ACTIVITY] {npc} action={kind} | {change.get('field')} "
            f"{change.get('before')} -> {change.get('after')} "
            f"({change.get('id')} count={change.get('action_count')})"
        )
    return lines


def _producer_lines(packet):
    if packet.get("status") == "ERROR":
        return [f"[WORLD] {packet.get('producer')} ERROR={packet.get('error')}"]

    condition = packet.get("condition_met")
    task_status = packet.get("task_status")
    if condition or task_status == "completed":
        progress = ""
        if packet.get("work_required") is not None:
            progress = f" | work={packet.get('work_done')}/{packet.get('work_required')}"
        return [
            f"[WORLD] {packet.get('site')} | {packet.get('field')}={packet.get('actual')} | "
            f"rule={packet.get('rule_id')} condition={condition} | "
            f"task={packet.get('task_id')} status={task_status}{progress}"
        ]
    return []


def _arbitration_lines(packet):
    if packet.get("status") == "ERROR":
        return [f"[ARBITRATION] ERROR={packet.get('error')}"]

    task_id = packet.get("task_id")
    policy = packet.get("policy")
    status = packet.get("status")
    winner = packet.get("winner_name") or "NONE"
    distance = packet.get("distance")
    candidates = packet.get("candidates") or []
    candidate_text = ", ".join(
        f"{row.get('npc_name')}:{row.get('distance')}"
        for row in candidates
    ) or "NONE"

    return [
        f"[ARBITRATION] {task_id} | policy={policy} | status={status} | "
        f"winner={winner} | distance={distance} | candidates={candidate_text}"
    ]


def _npc_lines(result):
    npc = result.get("npc", "UNKNOWN")
    status = result.get("status", "UNKNOWN")
    goal_type = result.get("goal_type")
    goal_id = result.get("goal_id")
    engine = result.get("engine")
    action_kind = result.get("action_kind")

    head = f"[NPC] {npc} | {status}"
    if goal_type:
        head += f" | {goal_type} {goal_id}"
    if action_kind:
        head += f" | action={action_kind}"
    if engine:
        head += f" | engine={engine}"

    movement = None
    if result.get("from") or result.get("to"):
        movement = f"      {result.get('from')} -> {result.get('to') or result.get('target')}"
    elif result.get("location"):
        movement = f"      location={result.get('location')}"

    lines = [head]
    if result.get("job_claim_acquired"):
        lines.append(
            f"      [CLAIM] {goal_id} -> {result.get('job_claim_owner_name') or npc}"
        )
    if movement:
        lines.append(movement)
    if result.get("activity"):
        lines.append(f"      activity={result.get('activity')}")

    if result.get("work_required") is not None and result.get("work_done") is not None:
        before = result.get("work_done_before")
        added = result.get("work_added")
        prefix = ""
        if before is not None:
            prefix = f"{before} -> "
        suffix = f" (+{added})" if added is not None else ""
        lines.append(
            f"      [WORK] {prefix}{result.get('work_done')}/{result.get('work_required')}{suffix}"
        )

    for effect in result.get("job_completion_effects") or []:
        lines.append(
            f"      [WORK EFFECT] {effect.get('field')} "
            f"{effect.get('before')} -> {effect.get('after')}"
        )

    if result.get("job_claim_released"):
        lines.append(f"      [CLAIM RELEASED] {goal_id}")

    for effect in result.get("need_effects") or []:
        lines.append(
            f"      [RESOLVE NEED] {effect.get('field')} "
            f"{effect.get('before')} -> {effect.get('after')}"
        )

    return lines


class CmdSizaSimTrace(Command):
    """Show recent persistent World Tick history, including arbitration, needs, claims and work."""

    key = "siza-sim-trace"
    aliases = ["sim-trace"]
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        try:
            count = int(raw) if raw else 8
        except ValueError:
            self.caller.msg("Uso: siza-sim-trace [1-20]")
            return

        count = max(1, min(TRACE_LIMIT, count))
        state = world_tick_state()
        history = list(state.get("trace_history") or [])

        self.caller.msg("=== SIZA SIM TRACE ===")
        self.caller.msg(f"Build: {state.get('build')} | stored={len(history)}")
        if not history:
            self.caller.msg("No hay trace todavía. Ejecute el World Tick al menos una vez.")
            self.caller.msg("======================")
            return

        for entry in history[-count:]:
            self.caller.msg(
                f"Tick {entry.get('tick')} | {entry.get('timestamp') or 'UNKNOWN TIME'}"
            )
            emitted = False

            for packet in entry.get("need_results") or []:
                for line in _need_lines(packet):
                    self.caller.msg("  " + line)
                    emitted = True

            for packet in entry.get("producer_results") or []:
                for line in _producer_lines(packet):
                    self.caller.msg("  " + line)
                    emitted = True

            for packet in entry.get("arbitration_results") or []:
                for line in _arbitration_lines(packet):
                    self.caller.msg("  " + line)
                    emitted = True

            for result in entry.get("npc_results") or []:
                for line in _npc_lines(result):
                    self.caller.msg("  " + line)
                    emitted = True

            for packet in entry.get("activity_need_results") or []:
                for line in _activity_need_lines(packet):
                    self.caller.msg("  " + line)
                    emitted = True

            if not emitted:
                self.caller.msg("  no meaningful changes")

        self.caller.msg("======================")
