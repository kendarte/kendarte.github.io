from evennia import Command

from commands.world_input_v99_commands import CmdSizaValidateV99


QA_BUILD = "0.99.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.98 is closed at 8/8 after proving typed institutional Facts can route through disjoint severity ranges while preserving exact fact_id transfer authority. v0.99 closes the hierarchical relay gap in faction Fact sharing: FACTION rules may optionally author authority_relation=HIGHER_THAN_SOURCE. Recipient eligibility then requires strictly greater current authority in the same target faction before the existing min_authority, need-aware, NEAREST/max_targets, relationship movement/contact and transfer pipeline continues. Equal-authority peers, lower ranks and the source itself cannot become upchain recipients. The relation is reevaluated from current memberships every refresh, so promotion can open a branch dynamically and the highest current authority stops naturally instead of broadcasting laterally. Omitting authority_relation preserves historical ANY behavior. Malformed relation values fail closed by cancelling pending branches."
        )
        _run_command(CmdSizaValidateV99, self.caller)
        self.caller.msg(
            "QA POLICY: v0.99 changes deterministic FACTION recipient eligibility only. The validator proves inherited relation metadata/build compatibility, 100->500 first-hop selection, real movement/contact/transfer, equal-rank suppression, promotion-driven 500->800 continuation, malformed-relation fail-closed cancellation, same-id recovery, ordered two-hop transfer history and natural stop at the highest current authority. qwen, faction policy projection, Knowledge persistence, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
