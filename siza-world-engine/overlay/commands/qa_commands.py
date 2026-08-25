from evennia import Command

from commands.world_input_v98_commands import CmdSizaValidateV98


QA_BUILD = "0.98.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.97 is closed at 9/9 after proving one faction fact_type policy may expand into exact managed rules for multiple stored matching Facts while existing source-Knowledge and SHARE_FACT authority remain exact per fact_id. v0.98 adds optional non-negative severity filtering to fact_type policies only: Facts may carry severity, and policies may author min_severity/max_severity. Disjoint severity ranges can therefore route incidents of the same fact_type to different existing authority thresholds without implicit precedence. A Fact changing severity dynamically removes the old derived rule, cancels its old pending intent and projects the appropriate new range using normal obligation identities. Missing/invalid Fact severity fails closed for filtered policies, overlapping ranges remain a concrete-fact conflict, malformed policy ranges fail closed, and exact v0.96 fact_id policies remain unchanged."
        )
        _run_command(CmdSizaValidateV98, self.caller)
        self.caller.msg(
            "QA POLICY: v0.98 changes deterministic typed faction-policy projection only. The validator covers v0.97 unfiltered compatibility, disjoint severity-range projection, existing authority/nearest routing, dynamic escalation and de-escalation, overlapping-range conflict fail-closed behavior, malformed severity filters, and exact v0.96 compatibility. qwen, Knowledge persistence, faction_engine, fact_share_rule selection, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
