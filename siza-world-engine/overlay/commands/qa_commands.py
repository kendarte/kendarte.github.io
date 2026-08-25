from evennia import Command

from commands.world_input_v861_validation_commands import CmdSizaValidateV861


QA_BUILD = "0.86.1-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.86 exposed a real multi-Fact selection problem rather than a Knowledge/action failure. The old TALK matcher accepted any one-token overlap and returned the first known matching Fact, so an earlier public Fact could satisfy a specific query like 'sello blanco de auditoria' before the intended restricted Fact. v0.86.1 adds one ranked Fact authority used by both disclosure and transfer: the raw player topic deterministically selects one exact known fact_id by authored topic/alias specificity; that same fact_id is then evaluated by holder-local disclosure, recorded in conversation memory and passed to the existing authoritative transfer engine. The old interaction engine, transfer engine, v0.54 CONFRONT, Knowledge requirements, Object Action and Consequence engines remain unchanged. The validator deliberately places a public one-token 'sello' decoy before the restricted audit Fact and reruns the full blocked->CONFRONT->acquire->Knowledge unlock->world consequence loop."
        )
        _run_command(CmdSizaValidateV861, self.caller)
        self.caller.msg(
            "QA POLICY: v0.86.1 changes TALK fact-selection authority, so the validator covers explicit and semantic TALK wiring, a deliberate earlier public collision, disclosure before/after real CONFRONT, exact transfer identity, Knowledge unlock, natural Object Action execution, consequence/presentation and exact state restoration. qwen target-selection metadata is unchanged from v0.85 and no new factual data is exposed to the model. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
