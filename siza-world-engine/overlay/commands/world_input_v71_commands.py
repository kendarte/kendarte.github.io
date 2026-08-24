import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v68_commands import (
    CmdSizaNoMatchV68,
    STRONG_OBJECT_ACTION_MIN_SCORE,
    classify_v68_input,
)
from services.action_intent_proposal_engine import build_action_proposal_request, build_local_capability_catalog
from services.action_proposal_async_runtime import (
    ASYNC_ACTION_PROPOSAL_BUILD,
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
    dispatch_action_proposal_async,
)
from services.action_proposal_execution_bridge import (
    MIN_EXECUTION_CONFIDENCE,
    execute_validated_object_action_proposal,
)
from services.action_resolution_engine import action_resolution_history
from services.object_action_engine import object_action_history
from services.object_action_input_engine import render_object_action_input_result
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_ACTION_INPUT_BUILD = "0.71.1-weak-ambiguity-aware-async-action-proposal"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar esa acción."


def classify_v71_input(actor, raw):
    """Preserve strong v0.68 routes; upgrade unknown or weak ambiguous object matches into structured proposals."""
    base = classify_v68_input(actor, raw)
    object_score = int(base.get("object_score") or 0)
    weak_ambiguous_object = (
        base.get("route") == "OBJECT_ACTION"
        and str(base.get("object_status") or "") == "AMBIGUOUS_OBJECT_ACTION"
        and object_score < STRONG_OBJECT_ACTION_MIN_SCORE
    )
    if base.get("route") == "LEGACY_UNKNOWN" or weak_ambiguous_object:
        return {
            **base,
            "build": NATURAL_ACTION_INPUT_BUILD,
            "route": "AI_ACTION_PROPOSAL",
            "ai_allowed": True,
            "mutation_requires_bridge": True,
            "weak_ambiguous_object_fallback": bool(weak_ambiguous_object),
        }
    return {**base, "build": NATURAL_ACTION_INPUT_BUILD}


def _render_bridge_engine_result(bridge):
    engine = dict((bridge or {}).get("world_engine_result") or {})
    current = dict((bridge or {}).get("current_capability") or {})
    if not engine:
        return ""
    packet = {
        "status": engine.get("status"),
        "object_name": current.get("target_name") or engine.get("object_name"),
        "object_action_name": current.get("label") or engine.get("object_action_name"),
        "action_result": engine,
    }
    return str(render_object_action_input_result(packet) or "").strip()


def handle_action_proposal_result(actor, proposal_result, *, bridge_callable=None, emit_messages=True):
    """Handle one structured proposal on the reactor. Model reason is never rendered or persisted here."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    status = str(proposal_result.get("status") or "")

    if status == "UNSUPPORTED":
        if emit_messages:
            actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
        return {"status": "NO_ACTION_UNSUPPORTED", "executed": False, "proposal_status": status}

    if status != "ACCEPTED" or proposal_result.get("accepted") is not True:
        logger.log_err(f"SIZA action proposal rejected before bridge: status={status}")
        if emit_messages:
            actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
        return {"status": "NO_ACTION_REJECTED", "executed": False, "proposal_status": status}

    bridge_fn = bridge_callable or execute_validated_object_action_proposal
    bridge = bridge_fn(actor, proposal_result)
    bridge_status = str((bridge or {}).get("status") or "")

    if bridge_status in {"WORLD_ENGINE_ACCEPTED", "WORLD_ENGINE_REJECTED"}:
        text = _render_bridge_engine_result(bridge)
        if emit_messages and text:
            actor.msg("\n" + text)
        return {
            "status": bridge_status,
            "executed": bool((bridge or {}).get("executed")),
            "bridge": bridge,
            "rendered_text": text,
        }

    if bridge_status in {"STALE_OR_MISSING_CAPABILITY", "CURRENT_TARGET_NOT_LOCAL", "CURRENT_KIND_MISMATCH"}:
        if emit_messages:
            actor.msg("\n" + SITUATION_CHANGED_TEXT)
        return {"status": "NO_ACTION_STALE", "executed": False, "bridge": bridge}

    if emit_messages:
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return {"status": "NO_ACTION_BRIDGE_REJECTED", "executed": False, "bridge": bridge}


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v71(actor, raw, **provider_options):
    return dispatch_action_proposal_async(
        actor,
        raw,
        on_result=handle_action_proposal_result,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV71(CmdSizaNoMatchV68):
    """Use deterministic v0.68 routing first; unknown or weak ambiguous action text reaches structured proposal."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v71_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v71(self.caller, raw)
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


class CmdSizaValidateV71(Command):
    key = "siza-validate-v71"
    aliases = ["validate-v71"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.71 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.71 | {NATURAL_ACTION_INPUT_BUILD} ===")
        self.caller.msg(
            "real __nomatch unknown/weak-ambiguous action -> reactor snapshot -> worker structured proposal -> reactor bridge -> real Object Action Engine"
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

            direct = classify_v71_input(actor, "analizar manifiesto")
            check(
                "strong-deterministic-object-action-still-bypasses-action-llm",
                direct.get("route") == "OBJECT_ACTION" and direct.get("ai_allowed") is False,
                f"route={direct.get('route')}",
            )

            inquiry = classify_v71_input(actor, "Que se sobre el manifiesto duplicado?")
            check(
                "inquiries-still-use-grounded-narration-not-action-proposal",
                inquiry.get("route") == "AI_INQUIRY" and inquiry.get("mutation_requires_bridge") is None,
                f"route={inquiry.get('route')}",
            )

            paraphrase = "quiero estudiar detenidamente las cifras del documento de carga"
            action_route = classify_v71_input(actor, paraphrase)
            check(
                "weak-ambiguous-or-previously-unknown-action-is-upgraded-to-structured-proposal-route",
                action_route.get("route") == "AI_ACTION_PROPOSAL"
                and action_route.get("ai_allowed") is True
                and action_route.get("mutation_requires_bridge") is True,
                f"route={action_route.get('route')} weak_ambiguous={action_route.get('weak_ambiguous_object_fallback')}",
            )

            request = build_action_proposal_request(actor, paraphrase)
            catalog = list(request.get("catalog") or [])
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            check(
                "reactor-side-request-snapshot-contains-real-local-capability-before-worker",
                request.get("location") == site.key
                and analyze_cap is not None
                and isinstance(request.get("ollama_payload"), dict),
                f"location={request.get('location')} catalog={len(catalog)}",
            )
            if not analyze_cap:
                raise RuntimeError("analyze capability missing")

            unsupported = handle_action_proposal_result(
                actor,
                {"status": "UNSUPPORTED", "accepted": True, "proposal": {"kind": "UNSUPPORTED", "capability_id": "", "confidence": 1.0, "reason": "none"}},
                emit_messages=False,
            )
            check(
                "unsupported-model-result-never-enters-world-engine",
                unsupported.get("status") == "NO_ACTION_UNSUPPORTED"
                and not unsupported.get("executed"),
                f"status={unsupported.get('status')}",
            )

            low = handle_action_proposal_result(
                actor,
                _accepted_result(analyze_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
                emit_messages=False,
            )
            check(
                "accepted-but-low-confidence-result-is-still-blocked-by-v070-bridge",
                low.get("status") == "NO_ACTION_BRIDGE_REJECTED"
                and not low.get("executed"),
                f"bridge={(low.get('bridge') or {}).get('status')}",
            )

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            accepted_fixture = _accepted_result(analyze_cap, 1.0)
            fixture_bridge = handle_action_proposal_result(actor, accepted_fixture, emit_messages=False)
            after_obj = object_action_history(actor)
            after_res = action_resolution_history(actor)
            check(
                "callback-handler-can-enter-real-engine-but-stops-at-pending-resolution",
                fixture_bridge.get("status") == "WORLD_ENGINE_ACCEPTED"
                and fixture_bridge.get("executed") is True
                and (fixture_bridge.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(after_obj) == before_obj + 1
                and len(after_res) == before_res + 1,
                f"engine={(fixture_bridge.get('bridge') or {}).get('world_engine_status')}",
            )

            rendered = str(fixture_bridge.get("rendered_text") or "")
            check(
                "player-feedback-comes-from-deterministic-world-engine-renderer-not-model-reason",
                "PENDING_RESOLUTION" in rendered
                and "validator-model-reason-never-render" not in rendered,
                f"rendered={rendered!r}",
            )

            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            other_room = next(
                (getattr(exit_obj, "destination", None) for exit_obj in list(getattr(site, "exits", []) or []) if getattr(exit_obj, "destination", None)),
                None,
            )
            if not other_room:
                raise RuntimeError("alternate room missing")
            actor.move_to(other_room, quiet=True)
            stale = handle_action_proposal_result(actor, accepted_fixture, emit_messages=False)
            check(
                "proposal-snapshot-cannot-execute-after-player-changes-location-during-llm-delay",
                stale.get("status") == "NO_ACTION_STALE"
                and not stale.get("executed")
                and len(object_action_history(actor)) == len(original_object_history or []),
                f"bridge={(stale.get('bridge') or {}).get('status')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

            check(
                "runtime-provider-function-operates-on-prebuilt-dicts-not-evennia-actor",
                ASYNC_ACTION_PROPOSAL_BUILD.startswith("0.71.0-")
                and request.get("actor") == actor.key
                and all(not hasattr(row, "db") for row in request.get("catalog") or []),
                f"async_build={ASYNC_ACTION_PROPOSAL_BUILD}",
            )

            self.caller.msg(
                f"LIVE V071 SNAPSHOT->PROPOSAL->BRIDGE PROBE: endpoint={DEFAULT_OLLAMA_ENDPOINT} model={DEFAULT_OLLAMA_MODEL} action={paraphrase!r}"
            )
            live = call_prebuilt_action_proposal(
                request,
                endpoint=DEFAULT_OLLAMA_ENDPOINT,
                model=DEFAULT_OLLAMA_MODEL,
                timeout=60,
            )
            check(
                "live-prebuilt-snapshot-provider-selects-real-object-action",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and str((live.get("capability") or {}).get("object_action_id") or "") == ANALYZE_ACTION_ID,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_live_obj = len(object_action_history(actor))
            before_live_res = len(action_resolution_history(actor))
            live_handled = handle_action_proposal_result(actor, live, emit_messages=False)
            check(
                "live-runtime-result-revalidates-and-enters-real-engine-on-reactor-handler",
                live_handled.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (live_handled.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_live_obj + 1
                and len(action_resolution_history(actor)) == before_live_res + 1,
                f"bridge={live_handled.get('status')} engine={(live_handled.get('bridge') or {}).get('world_engine_status')}",
            )

            latest = object_action_history(actor)[-1] if object_action_history(actor) else {}
            check(
                "live-v071-path-does-not-resolve-roll-or-copy-model-reason-into-game-state",
                latest.get("resolved") is False
                and latest.get("outcome") is None
                and "reason" not in latest
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts,
                f"resolved={latest.get('resolved')} outcome={latest.get('outcome')}",
            )

            self.caller.msg("--- LIVE V071 RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "handler_status": live_handled.get("status"),
                "world_engine_status": (live_handled.get("bridge") or {}).get("world_engine_status"),
                "rendered_text": live_handled.get("rendered_text"),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V071 RESULT ---")

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
            "PERSISTENT SYSTEM RETAINED: real unknown or weak-ambiguous player actions may reach async structured proposal, but only fresh high-confidence OBJECT_ACTION capabilities can enter the existing World Engine"
        )
        self.caller.msg("========================================================")
