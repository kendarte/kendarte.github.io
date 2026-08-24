from evennia import Command

from services.authority_order_engine import (
    check_order_authority,
    collect_order_candidates,
    inspect_orders,
    issue_order,
    set_order_active,
)
from services.faction_engine import FACTION_BUILD
from services.npc_simulation import find_npc


class CmdSizaOrders(Command):
    """Inspect persistent authority orders globally or for one NPC."""

    key = "siza-orders"
    aliases = ["orders-state", "authority-orders"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        npc = find_npc(query) if query else None
        if query and not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        self.caller.msg(f"=== SIZA AUTHORITY ORDERS | {FACTION_BUILD} ===")
        if npc:
            self.caller.msg(f"NPC: {npc.key}")
            candidates = collect_order_candidates(npc)
            if not candidates:
                self.caller.msg("  order_candidates=NONE")
            for item in candidates:
                faction = ""
                if item.get("faction_id"):
                    faction = f" | faction={item.get('faction_id')}"
                issuer = ""
                if item.get("issuer_name") or item.get("issuer_id"):
                    issuer = f" | issuer={item.get('issuer_name') or item.get('issuer_id')}"
                self.caller.msg(
                    f"  {item.get('order_id')} | authority={item.get('authority_name') or item.get('authority_id')} | "
                    f"kind={item.get('order_kind')} | priority={item.get('priority')} | "
                    f"target={item.get('target_room_key')} | occurrence={item.get('occurrence')}{faction}{issuer}"
                )
            self.caller.msg("===============================================")
            return

        rows = inspect_orders()
        if not rows:
            self.caller.msg("No hay órdenes persistentes registradas.")
        for row in rows:
            audience_parts = []
            if row.get("npc_ids"):
                audience_parts.append(f"npc={row.get('npc_ids')}")
            if row.get("job_ids"):
                audience_parts.append(f"job={row.get('job_ids')}")
            if row.get("faction_ids"):
                audience_parts.append(f"faction={row.get('faction_ids')}")
            audience = " | ".join(audience_parts) if audience_parts else "ALL"
            faction = ""
            if row.get("faction_id"):
                faction = f" | faction={row.get('faction_id')}"
            issuer = row.get("issuer_name") or row.get("issuer_id") or "NONE"
            self.caller.msg(
                f"{row.get('order_id')} | authority={row.get('authority_name') or row.get('authority_id')} | "
                f"kind={row.get('order_kind')} | active={row.get('active')} | status={row.get('status')} | "
                f"base_priority={row.get('priority')} | occurrence={row.get('occurrence')}{faction}"
            )
            self.caller.msg(
                f"  source={row.get('site_name')} | target={row.get('target_room_key')} | "
                f"audience={audience} | completed_by={row.get('completed_by') or []}"
            )
            if row.get("required_issuer_authority") or row.get("recipient_rank_ids") or row.get("issuer_rank_ids"):
                self.caller.msg(
                    f"  issuer={issuer} | issuer_rank={row.get('issuer_rank_id') or 'NONE'} | "
                    f"issuer_authority={row.get('issuer_authority')} | required_authority={row.get('required_issuer_authority')} | "
                    f"issuer_ranks={row.get('issuer_rank_ids') or 'ANY'} | recipient_ranks={row.get('recipient_rank_ids') or 'ANY'} | "
                    f"exclude_issuer={bool(row.get('exclude_issuer'))}"
                )
        self.caller.msg("===============================================")


class CmdSizaOrderToggle(Command):
    """Admin/debug bypass: activate or withdraw one authored persistent order."""

    key = "siza-order-toggle"
    aliases = ["order-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 2:
            self.caller.msg("Uso: siza-order-toggle <ORDER_ID> <on|off>")
            return

        order_id, state_word = parts
        state_word = state_word.lower()
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        packet = set_order_active(order_id, state_word == "on")
        if not packet:
            self.caller.msg(f"Orden no encontrada o sin producer válido: {order_id}")
            return

        producer = packet.get("producer") or {}
        faction = f" | faction={packet.get('faction_id')}" if packet.get("faction_id") else ""
        self.caller.msg(
            f"{order_id}: active={producer.get('event_active')} | status={producer.get('event_status')} | "
            f"occurrence={producer.get('occurrence')} | authority={packet.get('authority_name') or packet.get('authority_id')}{faction} | DEBUG_BYPASS=True"
        )


class CmdSizaOrderAuthority(Command):
    """Inspect whether one NPC has enough faction/rank authority to issue an order."""

    key = "siza-order-authority"
    aliases = ["order-authority"]
    locks = "cmd:all()"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 2:
            self.caller.msg("Uso: siza-order-authority <ORDER_ID> <NPC>")
            return

        order_id = parts[0]
        npc_query = " ".join(parts[1:])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = check_order_authority(order_id, npc)
        self.caller.msg(
            f"{order_id} | issuer={npc.key} | allowed={bool(packet.get('allowed'))} | "
            f"reason={packet.get('reason')} | faction={packet.get('faction_id')} | "
            f"rank={packet.get('issuer_rank_id')} | authority={packet.get('issuer_authority')} | "
            f"required={packet.get('required_issuer_authority')}"
        )


class CmdSizaOrderIssue(Command):
    """Issue an authored faction order using real membership/rank authority validation."""

    key = "siza-order-issue"
    aliases = ["order-issue"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 2:
            self.caller.msg("Uso: siza-order-issue <ORDER_ID> <NPC_EMISOR>")
            return

        order_id = parts[0]
        npc_query = " ".join(parts[1:])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = issue_order(order_id, npc)
        if not packet.get("allowed"):
            self.caller.msg(
                f"[ORDER DENIED] {order_id} | issuer={npc.key} | reason={packet.get('reason')} | "
                f"rank={packet.get('issuer_rank_id')} | authority={packet.get('issuer_authority')} | "
                f"required={packet.get('required_issuer_authority')}"
            )
            return

        producer = packet.get("producer") or {}
        self.caller.msg(
            f"[ORDER ISSUED] {order_id} | issuer={npc.key} | rank={packet.get('issuer_rank_id')} | "
            f"authority={packet.get('issuer_authority')} | required={packet.get('required_issuer_authority')} | "
            f"recipients={packet.get('recipient_ids') or []} | active={producer.get('event_active')} | "
            f"occurrence={producer.get('occurrence')}"
        )
