from evennia import Command

from services.npc_simulation import find_npc
from services.trait_engine import TRAIT_BUILD, inspect_traits, set_trait_active


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


class CmdSizaTraits(Command):
    """Inspect persistent virtue/defect traits and their explicit decision effects."""

    key = "siza-traits"
    aliases = ["traits-state", "npc-traits"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        state = inspect_traits(npc)
        self.caller.msg(f"=== SIZA TRAITS | {TRAIT_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={state.get('npc_id')}")
        rows = state.get("traits") or []
        if not rows:
            self.caller.msg("Traits: NONE")
        else:
            for trait in rows:
                trait_id = trait.get("id")
                self.caller.msg(
                    f"  {trait_id} | kind={str(trait.get('kind') or 'TRAIT').upper()} | "
                    f"name={trait.get('name') or trait_id} | enabled={bool(trait.get('enabled'))} | "
                    f"status={trait.get('canon_status') or trait.get('status') or 'prototype'}"
                )
                for raw in _plain_list(trait.get("decision_effects")):
                    effect = _record(raw)
                    if not effect:
                        continue
                    try:
                        value = int(effect.get("value", 0) or 0)
                    except (TypeError, ValueError):
                        value = 0
                    self.caller.msg(
                        f"    effect={effect.get('id')} | enabled={bool(effect.get('enabled', True))} | "
                        f"value={value:+} | when={effect.get('when') or {}}"
                    )
        self.caller.msg("===============================================")


class CmdSizaTraitToggle(Command):
    """Admin/debug: enable or disable one persistent trait as a whole."""

    key = "siza-trait-toggle"
    aliases = ["trait-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3 or parts[-1].lower() not in {"on", "off"}:
            self.caller.msg("Uso: siza-trait-toggle <NPC> <TRAIT_ID> <on|off>")
            return

        state_word = parts[-1].lower()
        trait_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = set_trait_active(npc, trait_id, state_word == "on")
        if not packet:
            self.caller.msg(f"Trait no encontrado en {npc.key}: {trait_id}")
            return

        self.caller.msg(
            f"{npc.key}: {trait_id} | kind={str(packet.get('kind') or 'TRAIT').upper()} | "
            f"enabled={bool(packet.get('enabled'))} | name={packet.get('name') or trait_id}"
        )
