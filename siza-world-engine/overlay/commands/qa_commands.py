from evennia import Command

from commands.world_input_v87_commands import CmdSizaValidateV87


QA_BUILD = "0.87.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.86.1 is closed at 12/12 after proving one ranked fact_id owns disclosure, conversation memory and transfer even with an earlier public one-token decoy. v0.87 changes no input, qwen, transfer, consequence, Fact-goal or NPC decision engine. It adds authored pilot integration only: when the existing v0.86 Knowledge-gated Manifest action completes, a normal explicit consequence teaches Mara one structured Fact and Knowledge key. Mara's existing v0.59 Fact-goal engine then materializes a high-priority one-shot goal from that exact Fact, and the existing decision engine moves her from Pescaderia de Darsena to Calle de Servicio. Running install/idempotency, natural object action, exact NPC Fact/provenance, Fact-goal materialization, real NPC movement/completion and one-shot non-reactivation with exact state restoration."
        )
        _run_command(CmdSizaValidateV87, self.caller)
        self.caller.msg(
            "QA POLICY: v0.87 is authored deterministic cross-system integration. It changes no qwen boundary and no shared engine implementation; all new risk is covered by the validator executing the real Object Action -> Consequence -> NPC Knowledge Fact -> Fact Goal -> decision_step path. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
