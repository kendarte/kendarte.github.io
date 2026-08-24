from evennia import Command

from services.faction_engine import (
    FACTION_BUILD,
    inspect_factions,
    inspect_memberships,
    set_loyalty_bias,
    set_membership_active,
)
from services.npc_simulation import find_npc


class CmdSizaFactions(Command):
    """Inspect persistent faction definitions or one NPC's memberships."""

    key = "siza-factions"
    aliases = ["factions-state", "npc-factions"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        self.caller.msg(f"=== SIZA FACTIONS | {FACTION_BUILD} ===")

        if query:
            npc = find_npc(query)
            if not npc:
                self.caller.msg("No identifico un NPC de Siza con ese nombre.")
                self.caller.msg("===============================================")
                return
            self.caller.msg(f"NPC: {npc.key} | npc_id={npc.db.npc_id}")
            rows = inspect_memberships(npc)
            if not rows:
                self.caller.msg("  memberships=NONE")
            for row in rows:
                self.caller.msg(
                    f"  {row.get('faction_id')} | faction={row.get('faction_name')} | "
                    f"active={bool(row.get('active'))} | role={row.get('role') or 'NONE'} | "
                    f"rank={row.get('rank') or 'NONE'} | loyalty_bias={int(row.get('loyalty_bias', 0) or 0):+} | "
                    f"status={row.get('canon_status') or 'prototype'}"
                )
            self.caller.msg("===============================================")
            return

        state = inspect_factions()
        rows = state.get("factions") or []
        if not rows:
            self.caller.msg("No hay facciones persistentes registradas.")
        for row in rows:
            self.caller.msg(
                f"{row.get('id')} | name={row.get('name')} | active={bool(row.get('active', True))} | "
                f"status={row.get('canon_status') or 'prototype'}"
            )
        self.caller.msg("===============================================")


class CmdSizaFactionLoyalty(Command):
    """Admin/debug: set the signed ORDER bias for one NPC toward one faction."""

    key = "siza-faction-loyalty"
    aliases = ["faction-loyalty"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-faction-loyalty <NPC> <FACTION_ID> <-100..100>")
            return

        faction_id = parts[-2]
        value = parts[-1]
        npc_query = " ".join(parts[:-2])
        try:
            numeric = int(value)
        except ValueError:
            self.caller.msg("La lealtad debe ser un entero entre -100 y 100.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        membership = set_loyalty_bias(npc, faction_id, numeric)
        if not membership:
            self.caller.msg(f"{npc.key} no tiene membership en {faction_id}.")
            return

        self.caller.msg(
            f"{npc.key}: faction={faction_id} | loyalty_bias={int(membership.get('loyalty_bias', 0) or 0):+} | "
            f"active={bool(membership.get('active'))}"
        )


class CmdSizaFactionMembershipToggle(Command):
    """Admin/debug: activate or suspend one existing faction membership."""

    key = "siza-faction-membership-toggle"
    aliases = ["faction-membership-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-faction-membership-toggle <NPC> <FACTION_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        faction_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        membership = set_membership_active(npc, faction_id, state_word == "on")
        if not membership:
            self.caller.msg(f"{npc.key} no tiene membership en {faction_id}.")
            return

        self.caller.msg(
            f"{npc.key}: faction={faction_id} | active={bool(membership.get('active'))} | "
            f"loyalty_bias={int(membership.get('loyalty_bias', 0) or 0):+}"
        )
