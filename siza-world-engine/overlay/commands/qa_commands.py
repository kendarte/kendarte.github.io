from evennia import Command

from commands.world_input_v96_commands import CmdSizaValidateV96


QA_BUILD = "0.96.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.95 is closed at 6/6 after proving limited NEAREST Fact sharing assigns scarce slots only to recipients that still need the exact Fact. v0.96 closes the institutional-authoring scale gap without changing faction or SHARE_FACT authority: an active faction definition may carry fact_share_policies, and a deterministic pre-decision sync projects those policies into managed namespaced NPC rules for current members. Existing v0.89-v0.95 refresh then owns target filtering, nearest selection, stale pruning and local transfer as before. Leaving the source faction or removing the faction policy removes the managed rule and cancels its pending intent; rejoining reuses the same normal obligation identity. A local NPC rule for the same fact overrides the inherited policy. Multiple active faction policies for the same fact fail closed instead of silently picking one. Running inheritance, normal nearest/authority materialization, wrapper ordering, membership churn, policy removal/recovery, local override and cross-faction conflict with exact registry/NPC state restoration."
        )
        _run_command(CmdSizaValidateV96, self.caller)
        self.caller.msg(
            "QA POLICY: v0.96 adds deterministic faction-policy projection plus one pre-social-refresh wrapper call. The validator proves inherited policies reuse the existing v0.89-v0.95 SHARE_FACT authority, that managed intent follows source membership/policy state, that local rules override rather than duplicate institutional authority, and that conflicting inherited policies fail closed. qwen, faction_engine implementation, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
