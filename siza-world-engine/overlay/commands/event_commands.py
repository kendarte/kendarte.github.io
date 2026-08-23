from evennia import Command

from services.world_event_engine import (
    collect_event_candidates,
    inspect_event_sites,
    refresh_world_event_rules,
    set_event_state,
)
from services.npc_simulation import find_npc


def _find_event_site(query):
    query = str(query or "").strip().lower()
    rows = inspect_event_sites()
    exact = []
    partial = []
    for row in rows:
        site = row.get("site")
        name = str(row.get("name") or "").lower()
        room_id = str(row.get("room_id") or "").lower()
        if query in {name, room_id}:
            exact.append(site)
        elif query and (query in name or query in room_id):
            partial.append(site)
    if len(exact) == 1:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


def _goal_type(item):
    return str((item or {}).get("goal_type") or (item or {}).get("type") or "EVENT").upper()


class CmdSizaEvents(Command):
    """Inspect persistent world incident sites, state and active EVENT/DANGER instances."""

    key = "siza-events"
    aliases = ["events-state"]
    locks = "cmd:all()"

    def func(self):
        refresh_world_event_rules()
        query = (self.args or "").strip()
        npc = find_npc(query) if query else None

        self.caller.msg("=== SIZA WORLD EVENTS ===")
        if npc:
            self.caller.msg(f"NPC: {npc.key}")
            candidates = collect_event_candidates(npc)
            if not candidates:
                self.caller.msg("  event_candidates=NONE")
            for item in candidates:
                self.caller.msg(
                    f"  {_goal_type(item)} {item.get('event_id')} | priority={item.get('priority')} | "
                    f"target={item.get('target_room_key')} | occurrence={item.get('occurrence')}"
                )
            self.caller.msg("=========================")
            return

        rows = inspect_event_sites()
        if not rows:
            self.caller.msg("No hay event sites persistentes registrados.")
        for row in rows:
            self.caller.msg(
                f"{row.get('name')} | room_id={row.get('room_id')} | state={row.get('state')}"
            )
            for event in row.get("instances") or []:
                goal_type = _goal_type(event)
                ack_text = "NA" if goal_type == "DANGER" else str(event.get("acknowledged_by") or [])
                self.caller.msg(
                    f"  {goal_type} {event.get('id')} | active={event.get('active')} | "
                    f"status={event.get('status')} | priority={event.get('priority')} | "
                    f"occurrence={event.get('occurrence')} | ack={ack_text}"
                )
        self.caller.msg("=========================")


class CmdSizaEventSet(Command):
    """Admin/debug: set one persistent incident-state field on an event site."""

    key = "siza-eventset"
    aliases = ["event-set"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 3:
            self.caller.msg("Uso: siza-eventset <ROOM_ID> <field> <value>")
            return

        site_query, field, value = parts
        site = _find_event_site(site_query)
        if not site:
            self.caller.msg("No identifico un event site de Siza con ese ROOM_ID.")
            return

        state = set_event_state(site, field, value)
        results = refresh_world_event_rules()
        self.caller.msg(f"{site.key}: {field}={state.get(field)}")
        for packet in results:
            if packet.get("site") != site.key:
                continue
            goal_type = str(packet.get("goal_type") or "EVENT").upper()
            self.caller.msg(
                f"[{goal_type} PRODUCER] {packet.get('event_id')}: condition={packet.get('condition_met')} | "
                f"active={packet.get('event_active')} | status={packet.get('event_status')} | "
                f"occurrence={packet.get('occurrence')}"
            )


class CmdSizaEventRefresh(Command):
    """Admin/debug: reevaluate all persistent world incident producer rules."""

    key = "siza-event-refresh"
    aliases = ["event-refresh"]
    locks = "cmd:perm(Admin)"

    def func(self):
        results = refresh_world_event_rules()
        self.caller.msg(f"World incident producer refreshed: {len(results)} rule(s).")
        for packet in results:
            goal_type = str(packet.get("goal_type") or "EVENT").upper()
            self.caller.msg(
                f"{goal_type} {packet.get('event_id')} | site={packet.get('site')} | "
                f"condition={packet.get('condition_met')} | active={packet.get('event_active')} | "
                f"occurrence={packet.get('occurrence')}"
            )
