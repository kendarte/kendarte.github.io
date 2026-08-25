from evennia import Command

from commands.world_input_v89_commands import CmdSizaValidateV89


QA_BUILD = "0.89.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.88 is closed at 10/10 after proving direct witness Knowledge follows physical site presence rather than NPC identity. v0.89 closes the next information-propagation gap without giving remote NPCs magical awareness: an authored fact_share_rule only materializes after the source NPC actually knows the exact Fact; it creates a SHARE_FACT relationship obligation that dynamically follows the target NPC's current room. The existing decision engine moves the source toward that target, and resolution calls the closed transfer_knowledge_fact engine only after both NPCs physically coincide. Original witness provenance remains on the Fact while direct-local transfer_history records the social hop. Completed one-shot share obligations are not reactivated on later decision refreshes. Running pre-knowledge no-obligation, real v0.88 witness acquisition, no instant remote transfer, obligation materialization, dynamic relationship candidate, real NPC movement/contact, exact Fact transfer/provenance and one-shot completion/idempotency."
        )
        _run_command(CmdSizaValidateV89, self.caller)
        self.caller.msg(
            "QA POLICY: v0.89 changes shared relationship-goal behavior by adding SHARE_FACT and adds a pre-decision Fact-share refresh. The validator therefore exercises the real Object Action -> SITE_NPCS witness Fact -> authored social rule -> relationship goal -> NPC traversal -> transfer_knowledge_fact path, proves the absent target stays ignorant until physical contact, verifies original witness provenance plus transfer history, and restores all touched NPC/world state. qwen and narration are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
