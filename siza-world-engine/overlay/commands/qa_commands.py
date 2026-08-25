from evennia import Command

from commands.world_input_v84_commands import CmdSizaValidateV84


QA_BUILD = "0.84.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.83 is closed after its structural privacy follow-up passed 4/4. v0.84 separates NPC knowledge from willingness to disclose it. A Fact may now carry an authored disclosure.min_familiarity gate. The gate is evaluated deterministically against the existing NPC->player familiarity counter before the closed TALK engine can render, record or transfer that Fact. Missing disclosure remains public; malformed disclosure fails closed. qwen still sees only the visible TALK target capability and raw player text, never Facts or disclosure state. Running public/default behavior, low-familiarity blocking with exact no-mutation proof, provider-boundary privacy, semantic and explicit TALK blocking, authored unlock into the existing transfer/render pipeline, malformed fail-closed behavior, one live qwen target-selection probe, INFORM/Knowledge-query separation, and PERCEPTION/OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV84, self.caller)
        self.caller.msg(
            "QA POLICY: v0.84 changes conversation authority, so the validator includes one real qwen target-selection roundtrip plus deterministic blocked/unlocked state assertions and targeted older-route regressions. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
