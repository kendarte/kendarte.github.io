from commands.siza_commands import CmdSizaNoMatch
from services.object_action_input_engine import (
    OBJECT_ACTION_INPUT_BUILD,
    render_object_action_input_result,
    route_object_action_input,
)


class CmdSizaNoMatchV50(CmdSizaNoMatch):
    """Route authored object-action input first, then preserve the legacy Siza fallback unchanged."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        caller = self.caller
        if raw and getattr(caller, "location", None):
            packet = route_object_action_input(caller, raw)
            if bool(packet.get("matched")):
                text = render_object_action_input_result(packet)
                if text:
                    caller.msg("\n" + text)
                return
        return super().func()


class CmdSizaObjectInputBuild(CommandError if False else CmdSizaNoMatch):
    """Internal placeholder never registered; keeps build discoverable without adding a command."""

    pass
