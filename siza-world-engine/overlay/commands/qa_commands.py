from evennia import Command

from commands.world_input_v91_commands import CmdSizaValidateV91


QA_BUILD = "0.91.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.90 is closed at 6/6 after proving target-aware Fact-share pruning prevents redundant social travel and retires pending shares when the target independently learns the exact Fact. v0.91 closes the symmetric persistent-state gap: relationship candidate collection already refused a SHARE_FACT goal when the source no longer knew the Fact, but the underlying obligation remained active/pending forever. refresh_fact_share_obligations now cancels an active pending share as SOURCE_NO_LONGER_KNOWS_FACT before candidate collection. Cancellation is deliberately reversible rather than terminal completion: if the source later relearns the exact Fact while the target remains ignorant, the same obligation id is reactivated without duplication and can complete through the unchanged local transfer_knowledge_fact authority. Historical v0.59/v0.89/v0.90 capability IDs remain stable. Running normal materialization, source-loss cancellation, wrapper candidate pruning, no remote transfer, relearning reactivation and real contact transfer/completion with exact state restoration."
        )
        _run_command(CmdSizaValidateV91, self.caller)
        self.caller.msg(
            "QA POLICY: v0.91 changes only deterministic Fact-share obligation refresh state. The validator proves a pending obligation is cancelled rather than left active when the source loses its exact Fact, that no relationship candidate or transfer survives that loss, and that relearning reactivates the same obligation id before the existing decision/relationship/transfer path completes normally. qwen, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
