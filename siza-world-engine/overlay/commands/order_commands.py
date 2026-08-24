from evennia import Command

from services.authority_order_engine import (
    AUTHORITY_ORDER_BUILD,
    collect_order_candidates,
    inspect_orders,
    set_order_active,
)
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

        self.caller.msg(f"=== SIZA AUTHORITY ORDERS | {AUTHORITY_ORDER_BUILD} ===")
        if npc:
            self.caller.msg(f"NPC: {npc.key}")
            candidates = collect_order_candidates(npc)
            if not candidates:
                self.caller.msg("  order_candidates=NONE")
            for item in candidates:
                self.caller.msg(
                    f"  {item.get('order_id')} | authority={item.get('authority_name') or item.get('authority_id')} | "
                    f"kind={item.get('order_kind')} | priority={item.get('priority')} | "
                    f"target={item.get('target_room_key')} | occurrence={item.get('occurrence')}"
                )
            self.caller.msg("===============================================")
            return

        rows = inspect_orders()
        if not rows:
            self.caller.msg("No hay órdenes persistentes registradas.")
        for row in rows:
            audience = row.get("npc_ids") or row.get("job_ids") or []
            self.caller.msg(
                f"{row.get('order_id')} | authority={row.get('authority_name') or row.get('authority_id')} | "
                f"kind={row.get('order_kind')} | active={row.get('active')} | status={row.get('status')} | "
                f"base_priority={row.get('priority')} | occurrence={row.get('occurrence')}"
            )
            self.caller.msg(
                f"  source={row.get('site_name')} | target={row.get('target_room_key')} | "
                f"audience={audience if audience else 'ALL'} | completed_by={row.get('completed_by') or []}"
            )
        self.caller.msg("===============================================")


class CmdSizaOrderToggle(Command):
    """Admin/debug: issue or withdraw one authored persistent order."""

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
        self.caller.msg(
            f"{order_id}: active={producer.get('event_active')} | status={producer.get('event_status')} | "
            f"occurrence={producer.get('occurrence')} | authority={packet.get('authority_name') or packet.get('authority_id')}"
        )
