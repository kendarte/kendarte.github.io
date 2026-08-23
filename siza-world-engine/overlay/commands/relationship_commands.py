from evennia import Command

from services.npc_simulation import find_npc
from services.relationship_engine import (
    collect_relationship_candidates,
    inspect_relationships,
    set_relationship_obligation_active,
)


class CmdSizaRelationships(Command):
    """Inspect persistent relationship records and pending social obligations."""

    key = "siza-relationships"
    aliases = ["siza-relations", "relations-state"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("Uso: siza-relationships <NPC>")
            return

        self.caller.msg("=== SIZA RELATIONSHIPS ===")
        self.caller.msg(f"NPC: {npc.key}")
        rows = inspect_relationships(npc)
        if not rows:
            self.caller.msg("  relationships=NONE")
        for row in rows:
            self.caller.msg(
                f"  target={row.get('target_name')} | npc_id={row.get('target_npc_id')} | "
                f"location={row.get('target_location')}"
            )
            obligations = row.get("obligations") or []
            if not obligations:
                self.caller.msg("    obligations=NONE")
            for item in obligations:
                self.caller.msg(
                    f"    {item.get('id')} | active={bool(item.get('active'))} | "
                    f"status={item.get('status')} | priority={item.get('priority', 50)} | "
                    f"kind={item.get('kind') or 'OBLIGATION'}"
                )

        candidates = collect_relationship_candidates(npc)
        if not candidates:
            self.caller.msg("  relationship_candidates=NONE")
        else:
            self.caller.msg("  relationship_candidates:")
            for item in candidates:
                self.caller.msg(
                    f"    {item.get('relationship_obligation_id')} -> "
                    f"{item.get('relationship_target_name')} @ {item.get('target_room_key')} | "
                    f"priority={item.get('priority')}"
                )
        self.caller.msg("==========================")


class CmdSizaRelationshipToggle(Command):
    """Admin/debug: activate/deactivate one authored relationship obligation."""

    key = "siza-rel-toggle"
    aliases = ["relationship-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-rel-toggle <NPC> <OBLIGATION_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        obligation_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = set_relationship_obligation_active(
            npc, obligation_id, state_word == "on"
        )
        if not packet:
            self.caller.msg(
                f"Obligación no encontrada en relationships de {npc.key}: {obligation_id}"
            )
            return

        self.caller.msg(
            f"{npc.key}: {obligation_id} | active={packet.get('active')} | "
            f"status={packet.get('status')} | target_npc_id={packet.get('target_npc_id')}"
        )
