from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v77_commands import _accepted_result
from commands.world_input_v80_commands import handle_action_proposal_result_v80
from services.action_resolution_engine import action_resolution_history
from services.action_intent_proposal_engine import build_local_capability_catalog
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V0802_VALIDATION_BUILD = "0.80.2-targeted-object-action-fixture-regression"


class CmdSizaValidateV802(Command):
    key = "siza-validate-v802"
    aliases = ["validate-v802"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.80.2 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.80.2 | {V0802_VALIDATION_BUILD} ===")
        self.caller.msg("targeted rerun: isolate authored manifest precondition -> execute unchanged OBJECT_ACTION bridge -> restore fixture")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state

            catalog = build_local_capability_catalog(actor)
            analyze_cap = next(
                (row for row in catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID),
                None,
            )
            check(
                "isolated-fixture-exposes-authored-analyze-capability",
                analyze_cap is not None and bool(getattr(manifest.db, "state", {}).get("analyzed") is False),
                f"capability={(analyze_cap or {}).get('capability_id')} analyzed={getattr(manifest.db, 'state', {}).get('analyzed')}",
            )
            if not analyze_cap:
                raise RuntimeError("analyze capability missing")

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            result = handle_action_proposal_result_v80(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "unchanged-object-action-bridge-accepts-valid-authored-precondition",
                result.get("status") == "WORLD_ENGINE_ACCEPTED"
                and result.get("executed") is True
                and result.get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={result.get('status')} engine={result.get('world_engine_status')}",
            )

            # Prove the original v0.80 failure premise: an already analyzed manifest is correctly rejected by the engine.
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)
            analyzed_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(analyzed_state, dict):
                analyzed_state = {}
            analyzed_state["analyzed"] = True
            manifest.db.state = analyzed_state
            rejected = handle_action_proposal_result_v80(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            engine_result = dict(rejected.get("world_engine_result") or {})
            check(
                "already-analyzed-manifest-is-correctly-rejected-by-authored-state-gate",
                rejected.get("status") == "WORLD_ENGINE_REJECTED"
                and rejected.get("executed") is False
                and str(rejected.get("world_engine_status") or "") not in {"PENDING_RESOLUTION", "COMPLETED"},
                f"status={rejected.get('status')} engine={rejected.get('world_engine_status')} blockers={engine_result.get('blockers')}",
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
        self.caller.msg("STATE RESTORED: actor location, manifest authored state and action histories restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: OBJECT_ACTION bridge is unchanged; the prior v0.80 failure was an invalid validator fixture against the authored analyzed=False requirement")
        self.caller.msg("========================================================")
