import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import CmdSizaNoMatchV741, classify_v741_input
from commands.world_input_v74_commands import (
    SEMANTIC_TOPIC_PHRASE,
    _clone,
    handle_action_proposal_result_v74,
)
from services.action_intent_proposal_engine import build_action_proposal_request
from services.action_proposal_async_runtime import (
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
    dispatch_action_proposal_async,
)
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.action_resolution_engine import action_resolution_history
from services.object_action_engine import object_action_history
from services.perception_proposal_execution_bridge import (
    PERCEPTION_BRIDGE_BUILD,
    execute_validated_visible_perception_proposal,
)
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_PERCEPTION_INPUT_BUILD = "0.75.0-async-revalidated-visible-perception-proposal"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar esa observación."
SEMANTIC_PERCEPTION_PHRASE = "me fijo detenidamente en el aspecto de Mara"
PRIVATE_SENTINEL = "NEVER_LEAK_V075_MARA_PRIVATE_SENTINEL"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def handle_action_proposal_result_v75(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
):
    """Add safe visible PERCEPTION while preserving v0.74/v0.73/v0.72/v0.71 execution branches."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return handle_action_proposal_result_v74(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    if _proposal_kind(proposal_result) != "PERCEPTION":
        return handle_action_proposal_result_v74(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    bridge = execute_validated_visible_perception_proposal(actor, proposal_result)
    bridge_status = str((bridge or {}).get("status") or "")

    if bridge_status == "PERCEPTION_EXECUTED":
        text = str((bridge or {}).get("response_text") or "").strip()
        if emit_messages and text:
            actor.msg("\n" + text)
        return {
            "status": "PERCEPTION_EXECUTED",
            "executed": True,
            "bridge": bridge,
            "rendered_text": text,
        }

    if bridge_status in {
        "STALE_OR_MISSING_CAPABILITY",
        "CURRENT_KIND_MISMATCH",
        "CURRENT_TARGET_NOT_LOCAL",
    }:
        if emit_messages:
            actor.msg("\n" + SITUATION_CHANGED_TEXT)
        return {"status": "NO_PERCEPTION_STALE", "executed": False, "bridge": bridge}

    logger.log_err(f"SIZA visible perception proposal rejected before observation: status={bridge_status}")
    if emit_messages:
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return {"status": "NO_PERCEPTION_REJECTED", "executed": False, "bridge": bridge}


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA perception/interaction/movement/action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v75(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v75(
            current_actor,
            proposal_result,
            raw_player_input=raw,
            emit_messages=True,
        )

    return dispatch_action_proposal_async(
        actor,
        raw,
        on_result=_handle,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV75(CmdSizaNoMatchV741):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v75(self.caller, raw)
            return None
        return super().func()


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


class CmdSizaValidateV75(Command):
    key = "siza-validate-v75"
    aliases = ["validate-v75"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.75 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
        manifest = context.get("manifest")
        original_location = actor.location
        original_mara_location = mara.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_memories = _clone(getattr(actor.db, "memories", []))
        original_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_discovered = _clone(getattr(actor.db, "discovered_facts", []))
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.75 | {NATURAL_PERCEPTION_INPUT_BUILD} ===")
        self.caller.msg(
            "semantic visible observation -> qwen selects exact OBSERVE capability -> fresh visibility revalidation -> existing perception engine AUTO_SUCCESS only"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

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
            actor.db.discovered_facts = list(original_discovered or [])

            direct = classify_v741_input(actor, "observo a Mara")
            check(
                "known-deterministic-perception-still-bypasses-action-llm",
                direct.get("route") == "PERCEPTION" and direct.get("ai_allowed") is False,
                f"route={direct.get('route')}",
            )

            semantic = classify_v741_input(actor, SEMANTIC_PERCEPTION_PHRASE)
            check(
                "semantic-visible-observation-reaches-structured-proposal-route",
                semantic.get("route") == "AI_ACTION_PROPOSAL" and semantic.get("ai_allowed") is True,
                f"route={semantic.get('route')} phrase={SEMANTIC_PERCEPTION_PHRASE!r}",
            )

            private_facts = _clone(getattr(mara.db, "knowledge_facts", []))
            private_facts = list(private_facts or []) + [{
                "id": "FACT-V075-PRIVATE-SENTINEL",
                "topic": "private",
                "text": PRIVATE_SENTINEL,
                "knowledge_key": "V075_PRIVATE",
                "required_level": 1,
            }]
            mara.db.knowledge_facts = private_facts

            request = build_action_proposal_request(actor, SEMANTIC_PERCEPTION_PHRASE)
            catalog = list(request.get("catalog") or [])
            observe_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "PERCEPTION"
                    and int(row.get("target_dbref") or 0) == int(mara.id)
                ),
                None,
            )
            talk_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "INTERACTION"
                    and int(row.get("target_dbref") or 0) == int(mara.id)
                ),
                None,
            )
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            movement_cap = next(
                (row for row in catalog if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"),
                None,
            )
            request_text = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            check(
                "snapshot-exposes-visible-observe-capability-without-private-fact-state",
                observe_cap is not None
                and talk_cap is not None
                and analyze_cap is not None
                and movement_cap is not None
                and PRIVATE_SENTINEL not in request_text
                and "V075_PRIVATE" not in request_text,
                f"observe={(observe_cap or {}).get('capability_id')} private_leaked={PRIVATE_SENTINEL in request_text}",
            )
            if not observe_cap or not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.75 capabilities missing")

            before_low_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            low = execute_validated_visible_perception_proposal(
                actor,
                _accepted_result(observe_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
            )
            check(
                "perception-bridge-rejects-low-confidence-without-discovery-mutation",
                low.get("status") == "LOW_CONFIDENCE"
                and not low.get("executed")
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_low_discovered,
                f"status={low.get('status')}",
            )

            other_room = next(
                (getattr(exit_obj, "destination", None) for exit_obj in list(getattr(site, "exits", []) or []) if getattr(exit_obj, "destination", None)),
                None,
            )
            if not other_room:
                raise RuntimeError("alternate room missing for v0.75 stale test")
            mara.move_to(other_room, quiet=True)
            stale = handle_action_proposal_result_v75(
                actor,
                _accepted_result(observe_cap, 1.0),
                raw_player_input=SEMANTIC_PERCEPTION_PHRASE,
                emit_messages=False,
            )
            check(
                "observation-proposal-is-rejected-if-target-moves-before-callback",
                stale.get("status") == "NO_PERCEPTION_STALE"
                and not stale.get("executed")
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_low_discovered,
                f"status={stale.get('status')} mara_location={mara.location.key if mara.location else None}",
            )
            mara.move_to(site, quiet=True)

            before_fixture_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            fixture = handle_action_proposal_result_v75(
                actor,
                _accepted_result(observe_cap, 1.0),
                raw_player_input=SEMANTIC_PERCEPTION_PHRASE,
                emit_messages=False,
            )
            check(
                "fresh-visible-perception-uses-existing-engine-auto-success-without-roll-or-discovery",
                fixture.get("status") == "PERCEPTION_EXECUTED"
                and fixture.get("executed") is True
                and (fixture.get("bridge") or {}).get("engine_status") == "AUTO_SUCCESS"
                and (fixture.get("bridge") or {}).get("roll") is None
                and not (fixture.get("bridge") or {}).get("discovered")
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_fixture_discovered,
                f"status={fixture.get('status')} engine={(fixture.get('bridge') or {}).get('engine_status')}",
            )

            fixture_text = str(fixture.get("rendered_text") or "")
            check(
                "visible-perception-feedback-is-target-description-not-model-reason-or-private-fact",
                bool(fixture_text)
                and "validator-model-reason-never-render" not in fixture_text
                and PRIVATE_SENTINEL not in fixture_text,
                f"text={fixture_text!r}",
            )

            self.caller.msg(
                f"LIVE V075 PERCEPTION PROBE: action={SEMANTIC_PERCEPTION_PHRASE!r} target={mara.key!r}"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-exact-visible-mara-observation-capability",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "PERCEPTION"
                and str((live.get("proposal") or {}).get("capability_id") or "") == str(observe_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_live_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            before_live_obj = len(object_action_history(actor))
            before_live_res = len(action_resolution_history(actor))
            before_live_memories = _clone(getattr(actor.db, "memories", []))
            before_live_relationships = _clone(getattr(actor.db, "relationships", {}))
            live_handled = handle_action_proposal_result_v75(
                actor,
                live,
                raw_player_input=SEMANTIC_PERCEPTION_PHRASE,
                emit_messages=False,
            )
            check(
                "live-visible-perception-revalidates-and-executes-without-world-mutation",
                live_handled.get("status") == "PERCEPTION_EXECUTED"
                and (live_handled.get("bridge") or {}).get("engine_status") == "AUTO_SUCCESS"
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_live_discovered
                and len(object_action_history(actor)) == before_live_obj
                and len(action_resolution_history(actor)) == before_live_res
                and _clone(getattr(actor.db, "memories", [])) == before_live_memories
                and _clone(getattr(actor.db, "relationships", {})) == before_live_relationships,
                f"handler={live_handled.get('status')} text={live_handled.get('rendered_text')!r}",
            )

            check(
                "live-perception-does-not-copy-model-reason-or-private-facts",
                str((live.get("proposal") or {}).get("reason") or "") not in json.dumps(live_handled, ensure_ascii=False)
                and PRIVATE_SENTINEL not in json.dumps(live_handled, ensure_ascii=False)
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts,
                "model_reason_not_forwarded=True private_fact_not_forwarded=True",
            )

            self.caller.msg("--- LIVE V075 PERCEPTION RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "handler_status": live_handled.get("status"),
                "target": (live_handled.get("bridge") or {}).get("target_name"),
                "engine_status": (live_handled.get("bridge") or {}).get("engine_status"),
                "response_text": live_handled.get("rendered_text"),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V075 PERCEPTION RESULT ---")

            # Regression: explicit TALK precedence from v0.74.1 remains deterministic.
            explicit_talk = classify_v741_input(actor, "hablo con Mara sobre manifiesto duplicado")
            check(
                "v075-preserves-v0741-explicit-talk-precedence",
                explicit_talk.get("route") == "INTERACTION"
                and explicit_talk.get("ai_allowed") is False
                and explicit_talk.get("explicit_talk_precedence") is True,
                f"route={explicit_talk.get('route')}",
            )

            # Regression: structured INTERACTION still delegates to v0.74 without becoming perception.
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            interaction_regression = handle_action_proposal_result_v75(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input="me acerco a Mara para intercambiar unas palabras",
                emit_messages=False,
            )
            check(
                "v075-preserves-v073-v074-interaction-bridge",
                interaction_regression.get("status") == "INTERACTION_EXECUTED"
                and interaction_regression.get("executed") is True,
                f"status={interaction_regression.get('status')}",
            )
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_regression = handle_action_proposal_result_v75(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v075-preserves-object-action-bridge",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (object_regression.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')} engine={(object_regression.get('bridge') or {}).get('world_engine_status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement_regression = handle_action_proposal_result_v75(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v075-preserves-real-exit-movement-bridge",
                movement_regression.get("status") == "MOVEMENT_EXECUTED"
                and movement_regression.get("executed") is True
                and actor.location != site,
                f"status={movement_regression.get('status')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            try:
                if mara.location != original_mara_location:
                    mara.move_to(original_mara_location, quiet=True)
            except Exception:
                pass
            actor.db.adventure_stats = original_stats
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            actor.db.discovered_facts = original_discovered
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            manifest.db.state = original_manifest_state

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Mara location, discovered facts, social state, Knowledge/Facts, action histories and manifest state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: structured PERCEPTION may observe only a fresh visible target and must resolve AUTO_SUCCESS without roll/discovery; older execution bridges remain authoritative"
        )
        self.caller.msg("========================================================")
