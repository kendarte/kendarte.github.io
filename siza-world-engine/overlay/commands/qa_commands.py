from evennia import Command

from commands.world_input_v95_commands import CmdSizaValidateV95


QA_BUILD = "0.95.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.94 is closed at 9/9 after proving FACTION rules can select a deterministic nearest reachable subset after membership/authority filtering. v0.95 fixes the limited-slot ordering gap: under selection=NEAREST, recipients that already know the exact Fact or whose one-shot SHARE_FACT obligation is already completed are removed before max_targets slots are assigned. Existing v0.90 target-aware retirement remains authoritative for a pending branch whose target learns independently; v0.95 performs that retirement before ranking so the next ignorant reachable recipient can fill the same scarce slot in the same refresh. selection=ALL remains on the v0.93/v0.94 path unchanged. Running normal nearest baseline, additive build metadata, independent-target-learning fallback, completed-one-shot fallback after forgetting, ALL compatibility and no-recipient-needs-the-Fact behavior with exact state restoration."
        )
        _run_command(CmdSizaValidateV95, self.caller)
        self.caller.msg(
            "QA POLICY: v0.95 changes deterministic limited-recipient ordering only. The validator proves v0.94 nearest behavior is unchanged when all recipients need the Fact, that an already-known nearest target is retired before slot assignment and the farther ignorant target is selected immediately, that terminal one-shot recipients cannot consume slots after later forgetting, and that selection=ALL remains unchanged. qwen, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
