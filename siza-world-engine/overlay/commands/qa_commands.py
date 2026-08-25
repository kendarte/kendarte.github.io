from evennia import Command

from commands.world_input_v94_commands import CmdSizaValidateV94


QA_BUILD = "0.94.0-risk-based-one-command-qa"


def _run_command(command_cls, caller, args=""):
    """Run one existing synchronous Evennia command against the real caller."""
    cmd = command_cls()
    cmd.caller = caller
    cmd.args = str(args or "")
    cmd.raw_string = f"{cmd.key} {cmd.args}".strip()
    cmd.cmdstring = cmd.key
    try:
        cmd.account = caller.account
    except Exception:
        pass
    try:
        sessions = list(caller.sessions.all())
        cmd.session = sessions[0] if sessions else None
    except Exception:
        cmd.session = None
    return cmd.func()


class CmdSizaQALatest(Command):
    """Run the newest risk-based validator; manual acceptance is only required when risk remains."""

    key = "siza-qa-latest"
    aliases = ["qa-latest"]
    locks = "cmd:perm(Admin)"

    def func(self):
        self.caller.msg(f"=== SIZA QA LATEST | {QA_BUILD} ===")
        self.caller.msg(
            "RISK PROFILE: v0.93 is closed at 7/7 after proving FACTION Fact-share rules may filter current recipients by existing faction authority while preserving v0.92 all-member behavior when no threshold is authored. v0.94 closes the chain-of-command fanout gap: the same FACTION rule may optionally use selection=NEAREST with max_targets=N. Eligibility still comes from v0.92 membership plus v0.93 min_authority; only then are reachable recipients ranked by the existing passable Exit graph using find_path. Shorter path wins, then higher current faction authority, then npc_id for deterministic ties. Selection is reevaluated every refresh, so movement can prune an old pending branch and reactivate another normal SHARE_FACT obligation. Omitting selection preserves v0.93 behavior. Malformed selection/limits fail closed by cancelling pending branches from that rule."
        )
        _run_command(CmdSizaValidateV94, self.caller)
        self.caller.msg(
            "QA POLICY: v0.94 changes deterministic recipient subset selection only. The validator covers v0.93 no-selection compatibility, real one-hop vs two-hop nearest selection, holder-local selection metadata, dynamic branch switching when NPC locations change, authority tie-breaking at equal path length, max_targets=2, malformed selection fail-closed, same-id recovery and malformed max_targets fail-closed with exact state restoration. qwen, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding implementation and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
