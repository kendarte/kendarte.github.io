from evennia import Command

from commands.siza_ui_runtime_commands import (
    _room_text_block,
    context_action_packet as _legacy_context_action_packet,
    room_snapshot_packet as _legacy_room_snapshot_packet,
)

POKEROL_UI_RUNTIME_BUILD = "0.4.1-pokerol-native-ui-protocol"


def _stamp(packet):
    packet = dict(packet or {})
    packet["build"] = POKEROL_UI_RUNTIME_BUILD
    packet["game"] = "POKEROL"
    return packet


def room_snapshot_packet(actor):
    return _stamp(_legacy_room_snapshot_packet(actor))


def context_action_packet(actor):
    return _stamp(_legacy_context_action_packet(actor))


def emit_room_snapshot(actor, *, visible_text=False):
    """Publish POKEROL-native room state to the web client.

    Packet construction still reuses the proven World Engine serializers while
    the fork is being migrated, but no SIZA event or command name is exposed to
    the POKEROL client.
    """
    packet = room_snapshot_packet(actor)
    actions = context_action_packet(actor)
    actor.msg(pokerol_room_snapshot=((packet,), {}))
    actor.msg(pokerol_context_actions=((actions,), {}))
    if visible_text:
        actor.msg(_room_text_block(packet))
    return packet


class CmdPokerolRoomState(Command):
    key = "pokerol-room-state"
    aliases = ("estado-escena",)
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        emit_room_snapshot(self.caller, visible_text=False)


class CmdPokerolUiContext(Command):
    key = "pokerol-ui-context"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        self.caller.msg(pokerol_context_actions=((context_action_packet(self.caller),), {}))
