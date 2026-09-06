from evennia import Command

from services.information_engine import (
    inspect_event_information,
    share_event_information,
)
from services.npc_simulation import find_npc
from services.relationship_engine import create_information_obligation


class CmdSizaInformation(Command):
    """Inspect persistent event information learned from other characters."""

    key = "siza-information"
    aliases = ["information-state", "event-information"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        npc = find_npc(query)
        if not npc:
            self.caller.msg("Uso: siza-information <NPC>")
            return

        packet = inspect_event_information(npc)
        self.caller.msg(f"=== SIZA INFORMATION | {packet.get('build')} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={packet.get('npc_id')}")
        rows = packet.get("records") or []
        if not rows:
            self.caller.msg("  reported_event_information=NONE")
        for row in rows:
            self.caller.msg(
                f"  {row.get('event_id')} | occurrence={row.get('occurrence')} | "
                f"type={row.get('knowledge_type')} | source={row.get('source_name')} | "
                f"source_via={row.get('source_via')} | hops={row.get('hops')} | "
                f"heard_count={row.get('heard_count')}"
            )
            self.caller.msg(
                f"    origin_npc_id={row.get('origin_npc_id')} | "
                f"room={row.get('room_name')} | sources={row.get('source_npc_ids') or []}"
            )
        self.caller.msg("===============================================")


class CmdSizaInform(Command):
    """Admin/debug: one NPC directly tells another about a known EVENT occurrence."""

    key = "siza-inform"
    aliases = ["inform-event"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|")]
        if len(parts) not in {3, 4} or not all(parts[:3]):
            self.caller.msg(
                "Uso: siza-inform <SOURCE NPC> | <TARGET NPC> | <EVENT_ID> [| occurrence]"
            )
            return

        source = find_npc(parts[0])
        target = find_npc(parts[1])
        if not source or not target:
            self.caller.msg("No identifico source o target como NPC de Siza.")
            return

        occurrence = None
        if len(parts) == 4 and parts[3]:
            try:
                occurrence = int(parts[3])
            except ValueError:
                self.caller.msg("occurrence debe ser un entero.")
                return

        result = share_event_information(
            source,
            target,
            parts[2],
            occurrence=occurrence,
        )
        if not result.get("success"):
            self.caller.msg(
                f"[INFORMATION DENIED] source={source.key} | target={target.key} | "
                f"event={parts[2]} | reason={result.get('reason')}"
            )
            return

        if result.get("reason") == "TARGET_ALREADY_DIRECTLY_AWARE":
            self.caller.msg(
                f"[INFORMATION NO-OP] {target.key} ya conoce directamente "
                f"{result.get('event_id')} occurrence={result.get('occurrence')} | "
                f"via={result.get('target_via')}"
            )
            return

        candidate = result.get("candidate_hops")
        candidate_text = f" | candidate_hops={candidate}" if candidate is not None else ""
        self.caller.msg(
            f"[INFORMATION SHARED] {source.key} -> {target.key} | "
            f"event={result.get('event_id')} | occurrence={result.get('occurrence')} | "
            f"source_via={result.get('source_via')} | created={result.get('created')} | "
            f"hops={result.get('hops')}{candidate_text} | heard_count={result.get('heard_count')}"
        )


class CmdSizaInformGoal(Command):
    """Admin/debug: author one explicit social intent to tell another NPC about an occurrence."""

    key = "siza-inform-goal"
    aliases = ["inform-goal"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|")]
        if len(parts) != 5 or not all(parts):
            self.caller.msg(
                "Uso: siza-inform-goal <SOURCE NPC> | <TARGET NPC> | <EVENT_ID> | <occurrence> | <priority>"
            )
            return

        source = find_npc(parts[0])
        target = find_npc(parts[1])
        if not source or not target:
            self.caller.msg("No identifico source o target como NPC de Siza.")
            return
        try:
            occurrence = int(parts[3])
            priority = int(parts[4])
        except ValueError:
            self.caller.msg("occurrence y priority deben ser enteros.")
            return

        result = create_information_obligation(
            source,
            target,
            parts[2],
            occurrence,
            priority,
        )
        if not result.get("success"):
            self.caller.msg(
                f"[INFORM GOAL DENIED] source={source.key} | target={target.key} | "
                f"event={parts[2]} | occurrence={occurrence} | reason={result.get('reason')}"
            )
            return

        self.caller.msg(
            f"[INFORM GOAL] {source.key} -> {target.key} | id={result.get('obligation_id')} | "
            f"event={result.get('event_id')} | occurrence={result.get('occurrence')} | "
            f"priority={result.get('priority')} | source_via={result.get('source_via')} | "
            f"created={result.get('created')}"
        )
