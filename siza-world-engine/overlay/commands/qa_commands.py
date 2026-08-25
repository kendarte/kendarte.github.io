from evennia import Command

from commands.world_input_v101_commands import CmdSizaValidateV101


QA_BUILD = "1.01.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v1.00 is closed at 9/9 after proving social policies can distinguish current-holder acquisition without rewriting original Fact provenance. v1.01 introduces holder-local Fact lifecycle as shared Knowledge authority. Facts default ACTIVE for backward compatibility; RETRACTED and SUPERSEDED remain stored with Knowledge level/provenance/history but central fact_knowledge_state reports them non-usable. Retrieval/LLM grounding, disclosure, decision effects, Fact-goals, SHARE_FACT and transfer already converge on that authority. Existing Fact-derived goals are additionally cancelled while their source Fact is inactive and only lifecycle-cancelled goals may reactivate if the same Fact becomes ACTIVE again; normally completed one-shot goals remain terminal. Lifecycle changes do not magically mutate Fact copies already transferred to other holders."
        )
        _run_command(CmdSizaValidateV101, self.caller)
        self.caller.msg(
            "QA POLICY: v1.01 changes shared/core Knowledge authority, so the validator is broad: legacy ACTIVE compatibility, derived goal/share baseline, retraction persistence, retrieval/disclosure/decision-effect exclusion, persistent Fact-goal cancellation, social cancellation, transfer blocking, same-identity reactivation, holder-local copy isolation and SUPERSEDED replacement semantics. Because fact_knowledge_state is shared/core, one minimal manual gameplay acceptance remains after a full pass: verify a retract/reactivate query through the normal player-facing Knowledge path. qwen provider, faction policy projection, pathfinding, relationship resolution and transfer implementation are unchanged."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
