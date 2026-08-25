from evennia import Command

from commands.world_input_v86_commands import CmdSizaValidateV86


QA_BUILD = "0.86.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.85 is closed after its precedence-aware targeted follow-up passed 4/4. v0.86 closes the next cross-system gameplay loop without changing qwen or core engines: a clean persistent Fact known by the Informant is protected by the existing holder-local v0.85 disclosure policy, real v0.54 CONFRONT state unlocks disclosure, existing transfer_knowledge_fact raises the player's Knowledge level, and that exact Knowledge key is consumed by the existing v0.44 action requirement engine to unlock a new authored Manifest action. The action then flows through the unchanged Object Action and Consequence engines into persistent object/room state and presentation. Running install/idempotency, pre-acquisition Knowledge blocker, disclosure block, real failed/successful CONFRONT, authoritative Fact acquisition, exact Knowledge unlock, natural action execution, consequence/presentation and self-locking completion."
        )
        _run_command(CmdSizaValidateV86, self.caller)
        self.caller.msg(
            "QA POLICY: v0.86 adds authored pilot content and a deterministic cross-system integration only. qwen boundaries were not changed and were already live-tested in v0.85, so no new Ollama roundtrip or manual acceptance is required if all v0.86 assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
