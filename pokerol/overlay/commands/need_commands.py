from evennia import Command

from services.need_dynamics import inspect_need_dynamics
from services.need_engine import inspect_needs, set_need_value
from services.npc_simulation import find_npc


def _parse_value(raw):
    text = str(raw or "").strip()
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer():
        return int(value)
    return value


class CmdSizaNeeds(Command):
    """Inspect persistent NPC need state, dynamics, rules and resolving world affordances."""

    key = "siza-needs"
    aliases = ["needs-state"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = inspect_needs(npc)
        dynamics = inspect_need_dynamics(npc)
        self.caller.msg("=== SIZA NPC NEEDS ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={npc.db.npc_id}")
        self.caller.msg(f"State: {packet.get('needs') or {}}")
        self.caller.msg(f"Dynamics clock: {dynamics.get('clock', 0)}")
        self.caller.msg(f"Activity counters: {dynamics.get('activity_counters') or {}}")

        dynamic_rules = dynamics.get("rules") or []
        if dynamic_rules:
            self.caller.msg("Dynamics:")
            for rule in dynamic_rules:
                source = str(rule.get("source") or "clock").upper()
                if source == "ACTIVITY":
                    cadence = (
                        f"cada {rule.get('every_actions', 1)} acciones "
                        f"{str(rule.get('activity_kind') or 'UNKNOWN').upper()}"
                    )
                else:
                    cadence = f"cada {rule.get('every_ticks', 1)} ticks"
                self.caller.msg(
                    f"  {rule.get('id')} | enabled={rule.get('enabled', True)} | source={source} | "
                    f"{rule.get('field')} {rule.get('op', 'add')} {rule.get('value')} | "
                    f"{cadence} | min={rule.get('min')} | max={rule.get('max')}"
                )
        else:
            self.caller.msg("Dynamics: NONE")

        rules = packet.get("rules") or []
        if rules:
            self.caller.msg("Rules:")
            for rule in rules:
                self.caller.msg(
                    f"  {rule.get('id')} | enabled={rule.get('enabled', True)} | "
                    f"if {rule.get('need_key')} {rule.get('op')} {rule.get('value')} "
                    f"-> affordance={rule.get('affordance')} | priority={rule.get('priority')}"
                )
        else:
            self.caller.msg("Rules: NONE")

        sites = packet.get("sites") or []
        if sites:
            self.caller.msg("World affordances:")
            for site in sites:
                for affordance in site.get("affordances") or []:
                    self.caller.msg(
                        f"  {site.get('site')} | {affordance.get('id')} | "
                        f"kind={affordance.get('kind')} | need={affordance.get('need_key')} | "
                        f"enabled={affordance.get('enabled', True)}"
                    )

        candidates = packet.get("candidates") or []
        if candidates:
            self.caller.msg("Active NEED candidates:")
            for item in candidates:
                self.caller.msg(
                    f"  {item.get('id')} | need={item.get('need_key')}={item.get('need_value')} | "
                    f"target={item.get('target_room_key')} | affordance={item.get('affordance')} | "
                    f"priority={item.get('priority')}"
                )
        else:
            self.caller.msg("Active NEED candidates: NONE")

        self.caller.msg("======================")


class CmdSizaNeedSet(Command):
    """Admin/debug: set one persistent NPC need value without creating a goal directly."""

    key = "siza-needset"
    aliases = ["need-set"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-needset <NPC> <need_key> <valor>")
            return

        raw_value = parts[-1]
        need_key = parts[-2]
        npc_query = " ".join(parts[:-2])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        value = _parse_value(raw_value)
        stored = set_need_value(npc, need_key, value)
        packet = inspect_needs(npc)
        candidates = [
            item for item in packet.get("candidates") or []
            if str(item.get("need_key")) == str(need_key)
        ]

        self.caller.msg(f"{npc.key}: need {need_key}={stored}")
        if candidates:
            for item in candidates:
                self.caller.msg(
                    f"[NEED PRODUCER] {item.get('id')} active=True | "
                    f"target={item.get('target_room_key')} | priority={item.get('priority')}"
                )
        else:
            self.caller.msg(f"[NEED PRODUCER] {need_key}: no active candidate.")
