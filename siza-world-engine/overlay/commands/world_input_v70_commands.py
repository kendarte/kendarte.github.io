import json

from evennia import Command

from services.action_intent_proposal_engine import (
    build_local_capability_catalog,
    call_ollama_action_proposal,
)
from services.action_proposal_execution_bridge import (
    ACTION_BRIDGE_BUILD,
    MIN_EXECUTION_CONFIDENCE,
    execute_validated_object_action_proposal,
)
from services.object_action_engine import object_action_history
from services.action_resolution_engine import action_resolution_history
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V70_ATTEMPT_ID = "V070-BRIDGE-ANALYZE-001"


def _clone(value):
    if hasattr(value, "items"):
        try:
            return {str(key): _clone(item) for key, item in value.items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_clone(item) for item in value]
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        try:
            return [_clone(item) for item in value]
        except Exception:
            pass
    return value


def _accepted_result(capability, confidence=1.0):
    return {
        "status": "ACCEPTED",
        "accepted": True,
        "proposal": {
            "kind": str(capability.get("kind") or ""),
            "capability_id": str(capability.get("capability_id") or ""),
            "confidence": float(confidence),
            "reason": "validator fixture",
        },
        "capability": dict(capability),
    }


class CmdSizaValidateV70(Command):
    key = "siza-validate-v70"
    aliases = ["validate-v70"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.70 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        manifest = context.get("manifest")
        original_location = actor.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.70 | {ACTION_BRIDGE_BUILD} ===")
        self.caller.msg(
            "accepted structured proposal -> fresh current-room revalidation -> real Object Action Engine -> stop at pending resolution"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)

            stats = _clone(getattr(actor.db, "adventure_stats", {}))
            if not isinstance(stats, dict):
                stats = {}
            stats["PER"] = max(7, int(stats.get("PER", 0) or 0))
            actor.db.adventure_stats = stats

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state

            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            catalog = build_local_capability_catalog(actor)
            analyze_cap = next(
                (row for row in catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID),
                None,
            )
            check(
                "bridge-test-uses-real-current-manifest-capability",
                analyze_cap is not None
                and analyze_cap.get("kind") == "OBJECT_ACTION"
                and int(analyze_cap.get("target_dbref") or 0) == int(manifest.id),
                f"capability={(analyze_cap or {}).get('capability_id')}",
            )
            if not analyze_cap:
                raise RuntimeError("analyze capability missing")

            baseline_obj = len(object_action_history(actor))
            baseline_res = len(action_resolution_history(actor))

            not_accepted = execute_validated_object_action_proposal(
                actor,
                {"status": "UNSUPPORTED", "accepted": True, "proposal": {"kind": "UNSUPPORTED", "capability_id": "", "confidence": 1.0, "reason": "none"}},
            )
            check(
                "bridge-rejects-any-proposal-that-is-not-accepted-action",
                not_accepted.get("status") == "PROPOSAL_NOT_ACCEPTED"
                and not not_accepted.get("executed")
                and len(object_action_history(actor)) == baseline_obj
                and len(action_resolution_history(actor)) == baseline_res,
                f"status={not_accepted.get('status')}",
            )

            wrong_kind = _accepted_result(analyze_cap, 1.0)
            wrong_kind["proposal"]["kind"] = "MOVEMENT"
            wrong_kind_result = execute_validated_object_action_proposal(actor, wrong_kind)
            check(
                "bridge-v070-supports-only-object-action-kind",
                wrong_kind_result.get("status") == "UNSUPPORTED_EXECUTION_KIND"
                and not wrong_kind_result.get("executed")
                and len(object_action_history(actor)) == baseline_obj
                and len(action_resolution_history(actor)) == baseline_res,
                f"status={wrong_kind_result.get('status')}",
            )

            low_conf = execute_validated_object_action_proposal(
                actor,
                _accepted_result(analyze_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
            )
            check(
                "bridge-rejects-low-confidence-model-proposals-before-world-engine",
                low_conf.get("status") == "LOW_CONFIDENCE"
                and not low_conf.get("executed")
                and len(object_action_history(actor)) == baseline_obj
                and len(action_resolution_history(actor)) == baseline_res,
                f"confidence={low_conf.get('confidence')} required={low_conf.get('required_confidence')}",
            )

            hallucinated = _accepted_result(analyze_cap, 1.0)
            hallucinated["proposal"]["capability_id"] = "OBJECT_ACTION:DBREF:999999:INVENTED"
            hallucinated_result = execute_validated_object_action_proposal(actor, hallucinated)
            check(
                "bridge-rebuilds-current-catalog-and-rejects-hallucinated-capability",
                hallucinated_result.get("status") == "STALE_OR_MISSING_CAPABILITY"
                and not hallucinated_result.get("executed")
                and len(object_action_history(actor)) == baseline_obj
                and len(action_resolution_history(actor)) == baseline_res,
                f"status={hallucinated_result.get('status')}",
            )

            other_room = next(
                (getattr(exit_obj, "destination", None) for exit_obj in list(getattr(site, "exits", []) or []) if getattr(exit_obj, "destination", None)),
                None,
            )
            if not other_room:
                raise RuntimeError("no alternate room for stale capability test")
            actor.move_to(other_room, quiet=True)
            stale = execute_validated_object_action_proposal(actor, _accepted_result(analyze_cap, 1.0))
            check(
                "bridge-rejects-stale-capability-after-actor-location-changes",
                stale.get("status") == "STALE_OR_MISSING_CAPABILITY"
                and not stale.get("executed")
                and len(object_action_history(actor)) == baseline_obj
                and len(action_resolution_history(actor)) == baseline_res,
                f"status={stale.get('status')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

            blocked_state = _clone(getattr(manifest.db, "state", {}))
            blocked_state["analyzed"] = True
            manifest.db.state = blocked_state
            mechanics_block = execute_validated_object_action_proposal(
                actor,
                _accepted_result(analyze_cap, 1.0),
                attempt_id="V070-BLOCKED-REQUIREMENTS",
            )
            check(
                "real-object-action-engine-rechecks-mechanical-requirements-after-bridge",
                mechanics_block.get("status") == "WORLD_ENGINE_REJECTED"
                and mechanics_block.get("world_engine_status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and not mechanics_block.get("executed")
                and len(object_action_history(actor)) == baseline_obj
                and len(action_resolution_history(actor)) == baseline_res,
                f"engine_status={mechanics_block.get('world_engine_status')}",
            )
            ready_state = _clone(getattr(manifest.db, "state", {}))
            ready_state["analyzed"] = False
            manifest.db.state = ready_state

            self.caller.msg(
                f"LIVE PROPOSAL->ENGINE PROBE: endpoint={DEFAULT_OLLAMA_ENDPOINT} model={DEFAULT_OLLAMA_MODEL} action='quiero analizar el manifiesto de carga'"
            )
            live = call_ollama_action_proposal(
                actor,
                "quiero analizar el manifiesto de carga",
                endpoint=DEFAULT_OLLAMA_ENDPOINT,
                model=DEFAULT_OLLAMA_MODEL,
                timeout=60,
            )
            check(
                "live-qwen-proposal-is-accepted-and-high-confidence-before-bridge",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and str((live.get("capability") or {}).get("object_action_id") or "") == ANALYZE_ACTION_ID
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            state_before_bridge = _clone(getattr(manifest.db, "state", {}))
            bridged = execute_validated_object_action_proposal(
                actor,
                live,
                attempt_id=V70_ATTEMPT_ID,
            )
            after_obj_rows = object_action_history(actor)
            after_res_rows = action_resolution_history(actor)
            check(
                "live-accepted-proposal-enters-real-world-engine-and-stops-at-pending-resolution",
                bridged.get("status") == "WORLD_ENGINE_ACCEPTED"
                and bridged.get("executed") is True
                and bridged.get("world_engine_status") == "PENDING_RESOLUTION"
                and (bridged.get("world_engine_result") or {}).get("attempt_id") == V70_ATTEMPT_ID
                and len(after_obj_rows) == before_obj + 1
                and len(after_res_rows) == before_res + 1,
                f"bridge={bridged.get('status')} engine={bridged.get('world_engine_status')} obj_history={len(after_obj_rows)-before_obj} res_history={len(after_res_rows)-before_res}",
            )

            latest_obj = after_obj_rows[-1] if after_obj_rows else {}
            latest_res = after_res_rows[-1] if after_res_rows else {}
            check(
                "pending-resolution-records-retain-real-action-identity",
                latest_obj.get("object_action_id") == ANALYZE_ACTION_ID
                and latest_obj.get("object_dbref") == int(manifest.id)
                and latest_obj.get("resolution_id") == latest_res.get("resolution_id")
                and latest_res.get("status") == "PENDING_RESOLUTION",
                f"action={latest_obj.get('object_action_id')} resolution={latest_res.get('resolution_id')}",
            )

            check(
                "bridge-does-not-resolve-roll-or-apply-object-consequence",
                _clone(getattr(manifest.db, "state", {})) == state_before_bridge
                and not bool(latest_obj.get("resolved"))
                and latest_obj.get("outcome") is None,
                f"manifest_unchanged={_clone(getattr(manifest.db, 'state', {})) == state_before_bridge} resolved={latest_obj.get('resolved')}",
            )

            duplicate_before_obj = len(object_action_history(actor))
            duplicate_before_res = len(action_resolution_history(actor))
            duplicate = execute_validated_object_action_proposal(
                actor,
                live,
                attempt_id=V70_ATTEMPT_ID,
            )
            check(
                "duplicate-attempt-id-is-rejected-by-existing-engine-without-double-dispatch",
                duplicate.get("status") == "WORLD_ENGINE_REJECTED"
                and duplicate.get("world_engine_status") == "DUPLICATE_ATTEMPT_ID"
                and len(object_action_history(actor)) == duplicate_before_obj
                and len(action_resolution_history(actor)) == duplicate_before_res,
                f"engine_status={duplicate.get('world_engine_status')}",
            )

            check(
                "bridge-never-copies-llm-reason-into-knowledge-or-facts",
                _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts,
                "knowledge_and_facts_unchanged=True",
            )

            self.caller.msg("--- LIVE BRIDGE RESULT ---")
            self.caller.msg(
                json.dumps(
                    {
                        "proposal": live.get("proposal"),
                        "bridge_status": bridged.get("status"),
                        "world_engine_status": bridged.get("world_engine_status"),
                        "attempt_id": (bridged.get("world_engine_result") or {}).get("attempt_id"),
                        "resolution_id": (bridged.get("world_engine_result") or {}).get("resolution_id"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            self.caller.msg("--- END LIVE BRIDGE RESULT ---")

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            actor.db.adventure_stats = original_stats
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts
            manifest.db.state = original_manifest_state

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor location/stats/action histories/Knowledge/Facts and manifest state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: only high-confidence fresh OBJECT_ACTION proposals may enter the existing World Engine; resolution and consequences remain separate"
        )
        self.caller.msg("========================================================")
