import base64
import json

from evennia import Command

from services.world_combat_handoff_engine import (
    WORLD_COMBAT_HANDOFF_BUILD,
    accept_world_combat_result,
    build_world_combat_encounter,
    clear_pending_world_combat,
    emit_world_combat_encounter,
)


MAX_RESULT_TOKEN_CHARS = 5500


def _decode_result_token(token):
    value = str(token or "").strip()
    if not value:
        return {"status": "MISSING_RESULT_TOKEN", "accepted": False}
    if len(value) > MAX_RESULT_TOKEN_CHARS:
        return {"status": "RESULT_TOKEN_TOO_LARGE", "accepted": False}
    try:
        padding = "=" * ((4 - (len(value) % 4)) % 4)
        raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        packet = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return {"status": "INVALID_RESULT_TOKEN", "accepted": False}
    if not isinstance(packet, dict):
        return {"status": "INVALID_RESULT_SHAPE", "accepted": False}
    return {"status": "RESULT_TOKEN_DECODED", "accepted": True, "result": packet}


class CmdSizaCombatBridgeTest(Command):
    """QA-only handoff: send one local NPC to the browser as a TCG encounter."""

    key = "siza-combat-test"
    aliases = ["siza-tcg-test"]
    locks = "cmd:perm(Admin)"
    help_category = "SIZA QA"

    def func(self):
        target_name = str(self.args or "").strip()
        if not target_name:
            self.caller.msg("Uso: siza-combat-test <NPC local>")
            return
        target = self.caller.search(target_name, location=self.caller.location)
        if not target:
            return
        if target is self.caller or getattr(target, "destination", None):
            self.caller.msg("El objetivo debe ser un personaje local.")
            return
        if not bool(getattr(target.db, "is_npc", False)):
            self.caller.msg("El objetivo de esta prueba debe tener is_npc=True.")
            return

        packet = build_world_combat_encounter(
            self.caller,
            target,
            source_action_id=f"QA:{WORLD_COMBAT_HANDOFF_BUILD}",
        )
        if not packet.get("accepted"):
            self.caller.msg(f"Combat handoff rechazado: {packet.get('status')}")
            return
        emitted = emit_world_combat_encounter(self.caller, packet.get("encounter"))
        if not emitted.get("accepted"):
            self.caller.msg(f"Combat handoff no emitido: {emitted.get('status')}")
            return
        self.caller.msg(
            f"Combat handoff enviado al cliente: {emitted.get('encounter_id')} | "
            "el World Engine aún no aplicará consecuencias persistentes."
        )


class CmdSizaCombatResult(Command):
    """Internal browser callback. Never trusts a result without a matching pending encounter."""

    key = "siza-combat-result"
    locks = "cmd:all()"
    auto_help = False

    def func(self):
        decoded = _decode_result_token(self.args)
        if not decoded.get("accepted"):
            self.caller.msg(f"Combat result rechazado: {decoded.get('status')}")
            return
        accepted = accept_world_combat_result(self.caller, decoded.get("result"))
        if not accepted.get("accepted"):
            self.caller.msg(f"Combat result rechazado: {accepted.get('status')}")
            return
        # This acknowledgement is presentation only. Persistent consequences are a later authority step.
        self.caller.msg(
            f"Resultado de combate recibido: {accepted.get('outcome')} | "
            f"encounter={accepted.get('encounter_id')}"
        )
        self.caller.msg(
            siza_combat_result_accepted=(
                ({
                    "encounter_id": accepted.get("encounter_id"),
                    "outcome": accepted.get("outcome"),
                    "world_consequences_applied": False,
                    "bridge_build": WORLD_COMBAT_HANDOFF_BUILD,
                },),
                {},
            )
        )


class CmdSizaCombatBridgeStatus(Command):
    key = "siza-combat-status"
    locks = "cmd:perm(Admin)"
    help_category = "SIZA QA"

    def func(self):
        pending = getattr(self.caller.db, "pending_tcg_encounter", None)
        last_result = getattr(self.caller.db, "last_tcg_combat_result", None)
        if not pending:
            self.caller.msg("TCG bridge: sin encounter pendiente o resuelto en la sesión persistente.")
        else:
            encounter = dict((pending or {}).get("encounter") or {})
            self.caller.msg(
                "TCG bridge: "
                f"status={(pending or {}).get('status')} "
                f"encounter={encounter.get('encounter_id')} "
                f"outcome={(last_result or {}).get('outcome') if isinstance(last_result, dict) else None}"
            )


class CmdSizaCombatBridgeClear(Command):
    key = "siza-combat-clear"
    locks = "cmd:perm(Admin)"
    help_category = "SIZA QA"

    def func(self):
        clear_pending_world_combat(self.caller)
        self.caller.msg("TCG bridge: pending encounter eliminado.")
