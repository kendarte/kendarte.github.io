import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v75_commands import (
    CmdSizaNoMatchV75,
    SEMANTIC_PERCEPTION_PHRASE,
    handle_action_proposal_result_v75,
)
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT, call_prebuilt_action_proposal
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.action_resolution_engine import action_resolution_history
from services.active_perception_proposal_execution_bridge import (
    ACTIVE_PERCEPTION_BRIDGE_BUILD,
    execute_validated_active_perception_proposal,
    extract_active_search_target,
)
from services.active_perception_proposal_runtime import (
    ACTIVE_PERCEPTION_PROPOSAL_BUILD,
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_ACTIVE_PERCEPTION_BUILD = "0.76.0-semantic-active-perception-roll-discovery"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar esa búsqueda."
SEMANTIC_ACTIVE_SEARCH_PHRASE = "me pongo a escudriñar detrás del mostrador por si hay algo escondido"
TEST_FACT_ID = "FACT-V076-PESCADERIA-MOSTRADOR-001"
TEST_HARD_FACT_ID = "FACT-V076-PESCADERIA-MOSTRADOR-HARD-001"
TEST_FACT_TEXT = "Debajo del mostrador descubres una marca de arrastre reciente que termina junto al zócalo."
TEST_HARD_FACT_TEXT = "Una señal casi imperceptible permanece oculta bajo el mostrador."
PRIVATE_SENTINEL = "NEVER_LEAK_V076_HIDDEN_PERCEPTION_SENTINEL"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def _capability_id(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("capability_id") or "")
    except Exception:
        return ""


def _is_room_search_proposal(proposal_result):
    return _proposal_kind(proposal_result) == "PERCEPTION" and _capability_id(proposal_result).startswith("SEARCH:ROOM:")


def _roll_text(roll):
    if not isinstance(roll, dict):
        return ""
    try:
        return f"[PER TEST] {int(roll.get('stat_value', 0))} + d{int(roll.get('die_sides', 0))}({int(roll.get('die', 0))}) = {int(roll.get('total', 0))}"
    except Exception:
        return ""


def handle_action_proposal_result_v76(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
):
    """Add active room-search PERCEPTION while preserving the v0.75 visible OBSERVE and all older branches."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return handle_action_proposal_result_v75(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    if not _is_room_search_proposal(proposal_result):
        return handle_action_proposal_result_v75(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    bridge = execute_validated_active_perception_proposal(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
    )
    bridge_status = str((bridge or {}).get("status") or "")

    if bridge_status == "ACTIVE_PERCEPTION_EXECUTED":
        text = str((bridge or {}).get("response_text") or "").strip()
        roll_line = _roll_text((bridge or {}).get("roll"))
        if emit_messages:
            if roll_line:
                actor.msg(roll_line)
            if text:
                actor.msg("\n" + text)
        return {
            "status": "ACTIVE_PERCEPTION_EXECUTED",
            "executed": True,
            "bridge": bridge,
            "rendered_text": text,
            "roll_text": roll_line,
        }

    if bridge_status == "STALE_OR_MISSING_CAPABILITY":
        if emit_messages:
            actor.msg("\n" + SITUATION_CHANGED_TEXT)
        return {"status": "NO_ACTIVE_PERCEPTION_STALE", "executed": False, "bridge": bridge}

    logger.log_err(f"SIZA active perception proposal rejected before search: status={bridge_status}")
    if emit_messages:
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return {"status": "NO_ACTIVE_PERCEPTION_REJECTED", "executed": False, "bridge": bridge}


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA active perception proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v76(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v76(
            current_actor,
            proposal_result,
            raw_player_input=raw,
            emit_messages=True,
        )

    return dispatch_active_perception_proposal_async(
        actor,
        raw,
        on_result=_handle,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV76(CmdSizaNoMatchV75):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v76(self.caller, raw)
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


def _fact(fact_id, text, difficulty):
    return {
        "id": fact_id,
        "sense": "sight",
        "target": "mostrador",
        "keywords": ["mostrador", "debajo", "zócalo"],
        "fact": text,
        "difficulty": int(difficulty),
        "private_validator_sentinel": PRIVATE_SENTINEL,
    }


class CmdSizaValidateV76(Command):
    key = "siza-validate-v76"
    aliases = ["validate-v76"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.76 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
        manifest = context.get("manifest")
        original_location = actor.location
        original_mara_location = mara.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_discovered = _clone(getattr(actor.db, "discovered_facts", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_memories = _clone(getattr(actor.db, "memories", []))
        original_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_perception_facts = _clone(getattr(site.db, "perception_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.76 | {NATURAL_ACTIVE_PERCEPTION_BUILD} ===")
        self.caller.msg(
            "semantic active search -> qwen selects generic current-room SEARCH capability -> fresh room revalidation -> existing PER roll/discovery persistence"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])
            actor.db.discovered_facts = [item for item in list(original_discovered or []) if str(item) not in {TEST_FACT_ID, TEST_HARD_FACT_ID}]

            deterministic = classify_v741_input(actor, "reviso detrás del mostrador")
            check(
                "known-deterministic-active-perception-still-bypasses-action-llm",
                deterministic.get("route") == "PERCEPTION" and deterministic.get("ai_allowed") is False,
                f"route={deterministic.get('route')}",
            )

            semantic = classify_v741_input(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            check(
                "semantic-active-search-phrase-reaches-structured-proposal-route",
                semantic.get("route") == "AI_ACTION_PROPOSAL" and semantic.get("ai_allowed") is True,
                f"route={semantic.get('route')} phrase={SEMANTIC_ACTIVE_SEARCH_PHRASE!r}",
            )

            site.db.perception_facts = [_fact(TEST_FACT_ID, TEST_FACT_TEXT, 1)]
            request = build_active_perception_proposal_request(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            catalog = list(request.get("catalog") or [])
            search_cap = dict(request.get("room_search_capability") or {})
            observe_cap = next(
                (row for row in catalog if row.get("kind") == "PERCEPTION" and str(row.get("capability_id") or "").startswith("OBSERVE:") and int(row.get("target_dbref") or 0) == int(mara.id)),
                None,
            )
            talk_cap = next(
                (row for row in catalog if row.get("kind") == "INTERACTION" and int(row.get("target_dbref") or 0) == int(mara.id)),
                None,
            )
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            movement_cap = next(
                (row for row in catalog if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"),
                None,
            )
            request_text = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            check(
                "extended-provider-snapshot-adds-room-search-without-exposing-hidden-perception-facts",
                bool(search_cap)
                and str(search_cap.get("capability_id") or "").startswith("SEARCH:ROOM:")
                and observe_cap is not None
                and talk_cap is not None
                and analyze_cap is not None
                and movement_cap is not None
                and TEST_FACT_ID not in request_text
                and TEST_FACT_TEXT not in request_text
                and PRIVATE_SENTINEL not in request_text,
                f"search={search_cap.get('capability_id')} hidden_fact_leaked={TEST_FACT_TEXT in request_text}",
            )
            if not search_cap or not observe_cap or not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.76 capabilities missing")

            target = extract_active_search_target(SEMANTIC_ACTIVE_SEARCH_PHRASE)
            check(
                "active-search-target-is-derived-only-from-player-text",
                target == "mostrador",
                f"target={target!r}",
            )

            before_low = _clone(getattr(actor.db, "discovered_facts", []))
            low = execute_validated_active_perception_proposal(
                actor,
                _accepted_result(search_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
            )
            check(
                "active-perception-bridge-rejects-low-confidence-before-roll-or-discovery",
                low.get("status") == "LOW_CONFIDENCE"
                and not low.get("executed")
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_low,
                f"status={low.get('status')}",
            )

            other_room = next(
                (getattr(exit_obj, "destination", None) for exit_obj in list(getattr(site, "exits", []) or []) if getattr(exit_obj, "destination", None)),
                None,
            )
            if not other_room:
                raise RuntimeError("alternate room missing for v0.76 stale test")
            actor.move_to(other_room, quiet=True)
            stale = handle_action_proposal_result_v76(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "room-search-proposal-is-revalidated-and-rejected-if-player-moves-before-callback",
                stale.get("status") == "NO_ACTIVE_PERCEPTION_STALE"
                and not stale.get("executed")
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_low,
                f"status={stale.get('status')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

            hard_stats = _clone(getattr(actor.db, "adventure_stats", {}))
            if not isinstance(hard_stats, dict):
                hard_stats = {}
            hard_stats["PER"] = 0
            actor.db.adventure_stats = hard_stats
            actor.db.discovered_facts = [item for item in list(before_low or []) if str(item) != TEST_HARD_FACT_ID]
            site.db.perception_facts = [_fact(TEST_HARD_FACT_ID, TEST_HARD_FACT_TEXT, 99)]
            miss = handle_action_proposal_result_v76(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "active-search-failure-still-uses-real-per-roll-without-fabricating-discovery",
                miss.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (miss.get("bridge") or {}).get("engine_status") == "NO_DISCOVERY"
                and isinstance((miss.get("bridge") or {}).get("roll"), dict)
                and TEST_HARD_FACT_ID not in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and TEST_HARD_FACT_TEXT not in str(miss.get("rendered_text") or ""),
                f"engine={(miss.get('bridge') or {}).get('engine_status')} roll={(miss.get('bridge') or {}).get('roll')}",
            )

            success_stats = _clone(getattr(actor.db, "adventure_stats", {}))
            if not isinstance(success_stats, dict):
                success_stats = {}
            success_stats["PER"] = 7
            actor.db.adventure_stats = success_stats
            actor.db.discovered_facts = [item for item in list(before_low or []) if str(item) != TEST_FACT_ID]
            site.db.perception_facts = [_fact(TEST_FACT_ID, TEST_FACT_TEXT, 1)]
            success = handle_action_proposal_result_v76(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "active-search-success-uses-real-per-roll-and-persists-world-engine-discovery",
                success.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (success.get("bridge") or {}).get("engine_status") == "DISCOVERY"
                and isinstance((success.get("bridge") or {}).get("roll"), dict)
                and TEST_FACT_TEXT in list((success.get("bridge") or {}).get("discovered") or [])
                and TEST_FACT_ID in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and TEST_FACT_ID in [str(item) for item in list((success.get("bridge") or {}).get("discovered_fact_ids_added") or [])],
                f"engine={(success.get('bridge') or {}).get('engine_status')} roll={(success.get('bridge') or {}).get('roll')}",
            )

            after_first_discovery = _clone(getattr(actor.db, "discovered_facts", []))
            repeat = handle_action_proposal_result_v76(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "already-discovered-perception-fact-is-idempotent-and-does-not-roll-again",
                repeat.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (repeat.get("bridge") or {}).get("engine_status") == "NO_AUTHORIZED_DISCOVERY"
                and (repeat.get("bridge") or {}).get("roll") is None
                and _clone(getattr(actor.db, "discovered_facts", [])) == after_first_discovery
                and [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])].count(TEST_FACT_ID) == 1,
                f"engine={(repeat.get('bridge') or {}).get('engine_status')}",
            )

            check(
                "active-search-result-text-and-target-come-from-world-engine-and-player-input-not-model-reason",
                success.get("rendered_text") == TEST_FACT_TEXT
                and (success.get("bridge") or {}).get("search_target") == "mostrador"
                and (success.get("bridge") or {}).get("target_source") == "PLAYER_INPUT"
                and "validator-model-reason-never-render" not in json.dumps(success, ensure_ascii=False),
                f"text={success.get('rendered_text')!r} target={(success.get('bridge') or {}).get('search_target')!r}",
            )

            actor.db.discovered_facts = [item for item in list(before_low or []) if str(item) != TEST_FACT_ID]
            self.caller.msg(
                f"LIVE V076 ACTIVE PERCEPTION PROBE: action={SEMANTIC_ACTIVE_SEARCH_PHRASE!r} target='mostrador' room={site.key!r}"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-generic-current-room-search-capability-without-hidden-fact-access",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "PERCEPTION"
                and _capability_id(live) == str(search_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_live_obj = len(object_action_history(actor))
            before_live_res = len(action_resolution_history(actor))
            before_live_memories = _clone(getattr(actor.db, "memories", []))
            before_live_relationships = _clone(getattr(actor.db, "relationships", {}))
            before_live_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            before_live_facts = _clone(getattr(actor.db, "knowledge_facts", []))
            live_handled = handle_action_proposal_result_v76(
                actor,
                live,
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "live-active-search-revalidates-rolls-and-persists-exact-world-engine-discovery",
                live_handled.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (live_handled.get("bridge") or {}).get("engine_status") == "DISCOVERY"
                and isinstance((live_handled.get("bridge") or {}).get("roll"), dict)
                and TEST_FACT_ID in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and live_handled.get("rendered_text") == TEST_FACT_TEXT,
                f"handler={live_handled.get('status')} engine={(live_handled.get('bridge') or {}).get('engine_status')}",
            )

            live_reason = str((live.get("proposal") or {}).get("reason") or "")
            check(
                "live-active-search-mutates-only-discovered-facts-and-never-persists-model-reason",
                len(object_action_history(actor)) == before_live_obj
                and len(action_resolution_history(actor)) == before_live_res
                and _clone(getattr(actor.db, "memories", [])) == before_live_memories
                and _clone(getattr(actor.db, "relationships", {})) == before_live_relationships
                and _clone(getattr(actor.db, "knowledge", {})) == before_live_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == before_live_facts
                and live_reason not in json.dumps(_clone(getattr(actor.db, "discovered_facts", [])), ensure_ascii=False)
                and live_reason not in json.dumps(live_handled.get("bridge") or {}, ensure_ascii=False),
                "only_discovered_facts_changed=True model_reason_not_persisted=True",
            )

            self.caller.msg("--- LIVE V076 ACTIVE PERCEPTION RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "handler_status": live_handled.get("status"),
                "engine_status": (live_handled.get("bridge") or {}).get("engine_status"),
                "roll": (live_handled.get("bridge") or {}).get("roll"),
                "search_target": (live_handled.get("bridge") or {}).get("search_target"),
                "discovered": (live_handled.get("bridge") or {}).get("discovered"),
                "response_text": live_handled.get("rendered_text"),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V076 ACTIVE PERCEPTION RESULT ---")

            before_visible = _clone(getattr(actor.db, "discovered_facts", []))
            visible_regression = handle_action_proposal_result_v76(
                actor,
                _accepted_result(observe_cap, 1.0),
                raw_player_input=SEMANTIC_PERCEPTION_PHRASE,
                emit_messages=False,
            )
            check(
                "v076-preserves-v075-visible-observe-auto-success-without-discovery",
                visible_regression.get("status") == "PERCEPTION_EXECUTED"
                and (visible_regression.get("bridge") or {}).get("engine_status") == "AUTO_SUCCESS"
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_visible,
                f"status={visible_regression.get('status')} engine={(visible_regression.get('bridge') or {}).get('engine_status')}",
            )

            explicit_talk = classify_v741_input(actor, "hablo con Mara sobre manifiesto duplicado")
            check(
                "v076-preserves-v0741-explicit-talk-precedence",
                explicit_talk.get("route") == "INTERACTION"
                and explicit_talk.get("ai_allowed") is False
                and explicit_talk.get("explicit_talk_precedence") is True,
                f"route={explicit_talk.get('route')}",
            )

            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            interaction_regression = handle_action_proposal_result_v76(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input="me acerco a Mara para intercambiar unas palabras",
                emit_messages=False,
            )
            check(
                "v076-preserves-structured-interaction-bridge",
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
            object_regression = handle_action_proposal_result_v76(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v076-preserves-object-action-bridge",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (object_regression.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')} engine={(object_regression.get('bridge') or {}).get('world_engine_status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement_regression = handle_action_proposal_result_v76(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v076-preserves-real-exit-movement-bridge",
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
            actor.db.discovered_facts = original_discovered
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            manifest.db.state = original_manifest_state
            site.db.perception_facts = original_perception_facts

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Mara location, stats, discovered facts, social state, Knowledge/Facts, action histories, manifest and room perception facts restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: qwen may select only a generic current-room SEARCH capability; the existing perception engine owns PER roll, difficulty, discovery and discovered_facts persistence"
        )
        self.caller.msg("========================================================")
