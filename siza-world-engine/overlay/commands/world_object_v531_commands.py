from evennia import Command

from services.npc_simulation import find_npc
from services.object_action_engine import object_action_history
from services.object_action_input_engine import (
    OBJECT_ACTION_INPUT_BUILD,
    render_object_action_input_result,
    route_object_action_input,
)
from world.upgrade_pilot_v53 import COMPLETE_FIELD, ensure_v53_pilot_content


class CmdSizaValidateV531(Command):
    """Validate that internal object-state blocker codes never leak into player-facing text."""

    key = "siza-validate-v531"
    aliases = ["validate-v531"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        install = ensure_v53_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg("[V0.53.1 VALIDATION] FAIL | actor/install missing")
            return

        site = install.get("site")
        manifest = install.get("manifest")
        original_location = actor.location
        original_state = dict(getattr(manifest.db, "state", {}) or {})
        original_history = list(getattr(actor.db, "object_action_history", []) or [])
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.53.1 | {OBJECT_ACTION_INPUT_BUILD} ===")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.object_action_history = []

            state = dict(original_state)
            state["analyzed"] = True
            state[COMPLETE_FIELD] = True
            manifest.db.state = state

            packet = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V0531-BLOCKED",
            )
            text = render_object_action_input_result(packet)

            blockers = list(((packet.get("action_result") or {}).get("blockers") or []))
            check(
                "completed-action-remains-internally-state-blocked",
                packet.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in blockers),
                f"status={packet.get('status')} blockers={[row.get('kind') for row in blockers]}",
            )
            check(
                "player-facing-blocker-hides-internal-object-state-code",
                "OBJECT_STATE" not in text and "REQUIREMENTS_UNMET" not in text,
                f"text={text}",
            )
            check(
                "blocked-player-input-creates-no-object-action-history",
                len(object_action_history(actor)) == 0,
                f"history={len(object_action_history(actor))}",
            )
        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            manifest.db.state = original_state
            actor.db.object_action_history = original_history
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: manifest state, actor history and location restored")
        self.caller.msg("========================================================")
