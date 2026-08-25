from evennia import Command

from commands.world_input_v100_commands import CmdSizaValidateV100


QA_BUILD = "1.00.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.99 is closed at 9/9 after proving institutional Facts can climb a strictly increasing faction-authority chain without lateral peer relay. v1.00 closes the holder-provenance policy gap without rewriting Fact origin: holder_acquisition may be ANY, NONTRANSFERRED or LOCAL_TRANSFER. Current-holder acquisition is derived only from the Fact's existing DIRECT_LOCAL transfer_history targeting that holder; original source/learned_by remain untouched. The gate runs after faction policy projection and before the historical v0.89-v0.99 social refresh, so mismatched or malformed rules cannot materialize travel, pending branches are cancelled fail-closed, and correcting the gate reuses normal obligation identities. Missing Facts still defer to v0.91 source-awareness authority."
        )
        _run_command(CmdSizaValidateV100, self.caller)
        self.caller.msg(
            "QA POLICY: v1.00 adds one deterministic pre-social holder-acquisition gate plus wrapper wiring. The validator covers historical ANY compatibility, NONTRANSFERRED eligibility, real first-hop transfer with immutable origin provenance, received-holder blocking, LOCAL_TRANSFER continuation, malformed-gate cancellation, same-id recovery, ordered two-hop history and natural v0.99 top-authority stop with exact state restoration. qwen, faction policy projection, Knowledge persistence, fact_share_rule target/selection logic, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
