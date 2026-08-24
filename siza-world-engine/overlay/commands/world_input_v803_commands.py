from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v77_commands import _accepted_result
from commands.world_input_v80_commands import handle_action_proposal_result_v80
from services.action_resolution_engine import action_resolution_history
from services.action_intent_proposal_engine import build_local_capability_catalog
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V0803_VALIDATION_BUILD = "0.80.3-targeted-nested-object-bridge-regression"


class CmdSizaValidateV803(Command):
    key = "siza-validate-v803"
    aliases = ["validate-v803"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.80.3 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        manifest = context.get("manifest")
        original_location = actor.location
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.80.3 | {V0803_VALIDATION_BUILD} ===")
        self.caller.msg("targeted rerun: read OBJECT_ACTION engine status from the handler's nested bridge packet")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)

            state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(state, dict):
                state = {}
            state["analyzed"] = False
            manifest.db.state = state
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)

            catalog = build_local_capability_catalog(actor)
            analyze_cap = next(
                (row for row in catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID),
                None,
            )
            check(
                "isolated-valid-fixture-exposes-analyze-capability",
                analyze_cap is not None and getattr(manifest.db, "state", {}).get("analyzed") is False,
                f"capability={(analyze_cap or {}).get('capability_id')} analyzed={getattr(manifest.db, 'state', {}).get('analyzed')}",
            )
            if not analyze_cap:
                raise RuntimeError("analyze capability missing")

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            accepted = handle_action_proposal_result_v80(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            accepted_bridge = dict(accepted.get("bridge") or {})
            accepted_engine = dict(accepted_bridge.get("world_engine_result") or {})
            check(
                "nested-bridge-confirms-valid-object-action-enters-real-resolution",
                accepted.get("status") == "WORLD_ENGINE_ACCEPTED"
                and accepted.get("executed") is True
                and accepted_bridge.get("world_engine_status") == "PENDING_RESOLUTION"
                and accepted_engine.get("status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"outer={accepted.get('status')} bridge={accepted_bridge.get('world_engine_status')} engine={accepted_engine.get('status')}",
            )

            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)
            blocked_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(blocked_state, dict):
                blocked_state = {}
            blocked_state["analyzed"] = True
            manifest.db.state = blocked_state

            rejected = handle_action_proposal_result_v80(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            rejected_bridge = dict(rejected.get("bridge") or {})
            rejected_engine = dict(rejected_bridge.get("world_engine_result") or {})
            blockers = list(rejected_engine.get("blockers") or [])
            object_state_blocked = any(
                str((row or {}).get("kind") or "") == "OBJECT_STATE"
                and str((row or {}).get("id") or "") == "analyzed"
                for row in blockers
            )
            check(
                "nested-bridge-confirms-analyzed-state-is-authoritatively-rejected",
                rejected.get("status") == "WORLD_ENGINE_REJECTED"
                and rejected.get("executed") is False
                and rejected_bridge.get("world_engine_status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and rejected_engine.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and object_state_blocked,
                f"outer={rejected.get('status')} bridge={rejected_bridge.get('world_engine_status')} blockers={blockers}",
            )
        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            manifest.db.state = original_manifest_state
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor location, manifest state and action histories restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: production OBJECT_ACTION bridge and v0.80/v0.80.1 Knowledge acquisition code remain unchanged")
        self.caller.msg("========================================================")
