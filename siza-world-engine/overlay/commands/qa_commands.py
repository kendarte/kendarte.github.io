from evennia import Command

from commands.world_input_v88_commands import CmdSizaValidateV88


QA_BUILD = "0.88.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.87 is closed at 10/10 after proving a player world action can teach a structured Fact to an NPC and drive an autonomous Fact-goal response. v0.88 fixes the next world-simulation authority gap: consequences previously had no recipient mode based on physical presence, so authored EXPLICIT rules could teach remote NPCs if used as witnesses. The shared Consequence Engine now adds one deterministic SITE_NPCS recipient mode while preserving EXPLICIT, ACTOR, TARGET and ACTION_RECIPIENTS unchanged. SITE_NPCS resolves current persistent NPC locations from the action's site_dbref/site_room_id and fails closed if the action has no site. The validator executes the real v0.86 Manifest action twice, swapping Mara and the Informant between Pescaderia and Calle de Servicio, and requires the learned witness Fact to follow actual location rather than NPC identity."
        )
        _run_command(CmdSizaValidateV88, self.caller)
        self.caller.msg(
            "QA POLICY: v0.88 changes shared consequence recipient resolution, so the validator covers legacy recipient modes, missing-site fail-closed behavior, dbref/room-id site resolution, two real Object Action -> Consequence executions with swapped NPC positions, exact recipient sets, witness Fact provenance, unique action processing, idempotent content install and restoration of every persistent NPC's Knowledge/Facts/location. qwen and narration are untouched. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
