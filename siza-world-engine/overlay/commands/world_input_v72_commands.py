import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v71_commands import (
    CmdSizaNoMatchV71,
    classify_v71_input,
    handle_action_proposal_result,
)
from services.action_intent_proposal_engine import build_action_proposal_request, build_local_capability_catalog
from services.action_proposal_async_runtime import (
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
    dispatch_action_proposal_async,
)
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.action_resolution_engine import action_resolution_history
from services.movement_proposal_execution_bridge import (
    MOVEMENT_BRIDGE_BUILD,
    execute_validated_movement_proposal,
)
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_MOVEMENT_INPUT_BUILD = "0.72.0-async-revalidated-movement-proposal"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar ese movimiento."
SEMANTIC_MOVEMENT_PHRASE = "abandono la pescaderia y me voy afuera"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def handle_action_proposal_result_v72(actor, proposal_result, *, emit_messages=True):
    """Add MOVEMENT execution while preserving the v0.71 OBJECT_ACTION and rejection behavior unchanged."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return handle_action_proposal_result(actor, proposal_result, emit_messages=emit_messages)

    if _proposal_kind(proposal_result) != "MOVEMENT":
        return handle_action_proposal_result(actor, proposal_result, emit_messages=emit_messages)

    bridge = execute_validated_movement_proposal(actor, proposal_result)
    bridge_status = str((bridge or {}).get("status") or "")

    if bridge_status == "MOVEMENT_EXECUTED":
        return {
            "status": "MOVEMENT_EXECUTED",
            "executed": True,
            "bridge": bridge,
            "rendered_text": "",
        }

    if bridge_status == "MOVEMENT_REJECTED":
        # The real Exit command owns traversal-denial feedback. Never replace it with model prose.
        return {
            "status": "MOVEMENT_REJECTED",
            "executed": False,
            "bridge": bridge,
            "rendered_text": "",
        }

    if bridge_status in {
        "STALE_OR_MISSING_CAPABILITY",
        "CURRENT_KIND_MISMATCH",
        "CURRENT_EXIT_NOT_FOUND",
        "DESTINATION_MISMATCH",
    }:
        if emit_messages:
            actor.msg("\n" + SITUATION_CHANGED_TEXT)
        return {"status": "NO_MOVEMENT_STALE", "executed": False, "bridge": bridge}

    logger.log_err(f"SIZA movement proposal rejected before traversal: status={bridge_status}")
    if emit_messages:
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return {"status": "NO_MOVEMENT_REJECTED", "executed": False, "bridge": bridge}


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA movement/action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v72(actor, raw, **provider_options):
    return dispatch_action_proposal_async(
        actor,
        raw,
        on_result=handle_action_proposal_result_v72,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV72(CmdSizaNoMatchV71):
    """Preserve v0.71 routing; allow high-confidence fresh MOVEMENT proposals to traverse a real Exit."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v71_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v72(self.caller, raw)
            return None
        return super().func()


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


def _accepted_result(capability, confidence=1.0, reason="validator-model-reason-never-render"):
    return {
        "status": "ACCEPTED",
        "accepted": True,
        "proposal": {
            "kind": str(capability.get("kind") or ""),
            "capability_id": str(capability.get("capability_id") or ""),
            "confidence": float(confidence),
            "reason": str(reason),
        },
        "capability": dict(capability),
    }


class CmdSizaValidateV72(Command):
    key = "siza-validate-v72"
    aliases = ["validate-v72"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.72 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.72 | {NATURAL_MOVEMENT_INPUT_BUILD} ===")
        self.caller.msg(
            "unknown semantic movement -> structured proposal -> fresh MOVE capability -> exact real Evennia Exit command"
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

            direct = classify_v71_input(actor, "salir a la calle")
            check(
                "known-deterministic-movement-still-bypasses-action-llm",
                direct.get("route") == "MOVEMENT" and direct.get("ai_allowed") is False,
                f"route={direct.get('route')}",
            )

            semantic_route = classify_v71_input(actor, SEMANTIC_MOVEMENT_PHRASE)
            check(
                "semantic-movement-not-understood-by-deterministic-parser-reaches-proposal-route",
                semantic_route.get("route") == "AI_ACTION_PROPOSAL"
                and semantic_route.get("ai_allowed") is True,
                f"route={semantic_route.get('route')}",
            )

            request = build_action_proposal_request(actor, SEMANTIC_MOVEMENT_PHRASE)
            catalog = list(request.get("catalog") or [])
            movement_cap = next(
                (
                    row
                    for row in catalog
                    if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"
                ),
                None,
            )
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            check(
                "snapshot-contains-exact-real-exit-capability-and-object-action-regression-capability",
                movement_cap is not None
                and movement_cap.get("target_dbref") is not None
                and analyze_cap is not None,
                f"movement={(movement_cap or {}).get('capability_id')} analyze={bool(analyze_cap)} catalog={len(catalog)}",
            )
            if not movement_cap or not analyze_cap:
                raise RuntimeError("required v0.72 capabilities missing")

            destination = next(
                (
                    getattr(exit_obj, "destination", None)
                    for exit_obj in list(getattr(site, "exits", []) or [])
                    if str(exit_obj.key) == "salir a la calle"
                ),
                None,
            )
            if not destination:
                raise RuntimeError("movement destination missing")

            not_accepted = execute_validated_movement_proposal(
                actor,
                {"status": "UNSUPPORTED", "accepted": True, "proposal": {"kind": "UNSUPPORTED", "capability_id": "", "confidence": 1.0, "reason": "none"}},
            )
            check(
                "movement-bridge-rejects-nonaccepted-proposal-without-moving",
                not_accepted.get("status") == "PROPOSAL_NOT_ACCEPTED"
                and actor.location == site,
                f"status={not_accepted.get('status')}",
            )

            low = execute_validated_movement_proposal(
                actor,
                _accepted_result(movement_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
            )
            check(
                "movement-bridge-rejects-low-confidence-before-exit-command",
                low.get("status") == "LOW_CONFIDENCE"
                and not low.get("executed")
                and actor.location == site,
                f"status={low.get('status')}",
            )

            actor.move_to(destination, quiet=True)
            stale = execute_validated_movement_proposal(actor, _accepted_result(movement_cap, 1.0))
            check(
                "movement-proposal-is-revalidated-and-rejected-after-location-changes",
                stale.get("status") == "STALE_OR_MISSING_CAPABILITY"
                and not stale.get("executed")
                and actor.location == destination,
                f"status={stale.get('status')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

            fixture = execute_validated_movement_proposal(actor, _accepted_result(movement_cap, 1.0))
            check(
                "accepted-fresh-movement-proposal-executes-the-real-exit",
                fixture.get("status") == "MOVEMENT_EXECUTED"
                and fixture.get("executed") is True
                and fixture.get("exit_key") == "salir a la calle"
                and actor.location == destination,
                f"status={fixture.get('status')} exit={fixture.get('exit_key')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_regression = handle_action_proposal_result_v72(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v072-preserves-v071-object-action-bridge",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (object_regression.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')} engine={(object_regression.get('bridge') or {}).get('world_engine_status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            unsupported = handle_action_proposal_result_v72(
                actor,
                {"status": "UNSUPPORTED", "accepted": True, "proposal": {"kind": "UNSUPPORTED", "capability_id": "", "confidence": 1.0, "reason": "none"}},
                emit_messages=False,
            )
            check(
                "unsupported-action-remains-no-op-under-v072-handler",
                unsupported.get("status") == "NO_ACTION_UNSUPPORTED"
                and not unsupported.get("executed")
                and actor.location == site,
                f"status={unsupported.get('status')}",
            )

            self.caller.msg(
                f"LIVE V072 MOVEMENT PROBE: action={SEMANTIC_MOVEMENT_PHRASE!r} target='salir a la calle'"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-real-movement-capability-for-semantic-paraphrase",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "MOVEMENT"
                and str((live.get("proposal") or {}).get("capability_id") or "") == str(movement_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_live_obj = len(object_action_history(actor))
            before_live_res = len(action_resolution_history(actor))
            live_handled = handle_action_proposal_result_v72(actor, live, emit_messages=False)
            check(
                "live-structured-movement-revalidates-and-traverses-real-exit",
                live_handled.get("status") == "MOVEMENT_EXECUTED"
                and live_handled.get("executed") is True
                and actor.location == destination,
                f"handler={live_handled.get('status')} location={actor.location.key if actor.location else None}",
            )

            check(
                "movement-path-does-not-create-action-resolution-history-or-copy-model-prose",
                len(object_action_history(actor)) == before_live_obj
                and len(action_resolution_history(actor)) == before_live_res
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts
                and str((live.get("proposal") or {}).get("reason") or "") not in json.dumps(live_handled, ensure_ascii=False),
                "histories_unchanged=True model_reason_not_forwarded=True",
            )

            self.caller.msg("--- LIVE V072 MOVEMENT RESULT ---")
            self.caller.msg(
                json.dumps(
                    {
                        "proposal": live.get("proposal"),
                        "handler_status": live_handled.get("status"),
                        "bridge_status": (live_handled.get("bridge") or {}).get("status"),
                        "exit_key": (live_handled.get("bridge") or {}).get("exit_key"),
                        "destination": (live_handled.get("bridge") or {}).get("destination_name"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            self.caller.msg("--- END LIVE V072 MOVEMENT RESULT ---")

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
        self.caller.msg("STATE RESTORED: actor location/stats/action histories/Knowledge/Facts and manifest state restored exactly")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: structured MOVEMENT uses the exact real Exit after fresh revalidation; OBJECT_ACTION remains on v0.71/v0.70 bridge"
        )
        self.caller.msg("========================================================")
