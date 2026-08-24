import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v77_commands import handle_action_proposal_result_v77
from commands.world_input_v78_commands import CmdSizaNoMatchV78, DETERMINISTIC_SEARCH_PHRASE
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT, call_prebuilt_action_proposal
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.consequence_engine import get_consequence_registry
from services.deterministic_active_perception_engine import execute_deterministic_active_perception
from services.knowledge_context_engine import fact_knowledge_state
from services.knowledge_fact_engine import find_knowledge_fact
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.object_action_engine import object_action_history
from services.action_resolution_engine import action_resolution_history
from services.semantic_fact_inform_engine import (
    SEMANTIC_FACT_INFORM_BUILD,
    execute_validated_fact_inform_proposal,
    parse_semantic_fact_inform_intent,
)
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_FACT_INFORM_BUILD = "0.79.1-semantic-known-fact-inform-precise-topic"
INFORM_PHRASE = "me acerco a Mara y le cuento sobre la rozadura bajo el mostrador"
UNKNOWN_INFORM_PHRASE = "me acerco a Mara y le cuento sobre una caja fuerte secreta en el techo"
TEST_PERCEPTION_FACT_ID = "FACT-V079-PESCADERIA-ROZADURA-001"
TEST_KNOWLEDGE_FACT_ID = "KFACT-V079-PESCADERIA-ROZADURA-001"
TEST_KNOWLEDGE_KEY = "V079_PESCADERIA_ROZADURA"
TEST_DISCOVERY_TEXT = "Debajo del mostrador detectas una rozadura fresca que se prolonga hasta el zócalo."
TEST_KNOWLEDGE_TEXT = "Una rozadura fresca bajo el mostrador de la pescadería se prolonga hasta el zócalo."


def _projectable_fact():
    return {
        "id": TEST_PERCEPTION_FACT_ID,
        "sense": "sight",
        "target": "mostrador",
        "keywords": ["mostrador", "debajo", "zócalo", "rozadura"],
        "fact": TEST_DISCOVERY_TEXT,
        "difficulty": 1,
        "knowledge_fact": {
            "id": TEST_KNOWLEDGE_FACT_ID,
            "topic": "rozadura bajo mostrador",
            "aliases": ["rozadura", "marca bajo mostrador"],
            "text": TEST_KNOWLEDGE_TEXT,
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "required_level": 1,
            "canon_status": "prototype",
        },
        "knowledge": {
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "mode": "MAX",
            "value": 1,
        },
    }


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


def _accepted_result(capability, confidence=1.0, reason="validator-model-reason-never-persist"):
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


def handle_action_proposal_result_v79(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
):
    intent = parse_semantic_fact_inform_intent(raw_player_input)
    if intent and proposal_result.get("status") == "ACCEPTED" and proposal_result.get("accepted") is True:
        if _proposal_kind(proposal_result) == "INTERACTION":
            packet = execute_validated_fact_inform_proposal(
                actor,
                proposal_result,
                raw_player_input=raw_player_input,
            )
            status = str(packet.get("status") or "")
            if status == "FACT_INFORM_EXECUTED":
                text = str(packet.get("response_text") or "").strip()
                if emit_messages and text:
                    actor.msg("\n" + text)
                return packet
            if status in {"STALE_OR_MISSING_CAPABILITY", "CURRENT_TARGET_NOT_LOCAL"}:
                if emit_messages:
                    actor.msg("\nLa situación cambió antes de que pudieras contar ese hecho.")
                return packet
            if status in {"NO_KNOWN_FACT_FOR_TOPIC", "AMBIGUOUS_KNOWN_FACT_FOR_TOPIC"}:
                if emit_messages:
                    actor.msg("\nNo tienes un hecho conocido y suficientemente preciso que corresponda a ese tema.")
                return packet
            logger.log_err(f"SIZA semantic fact inform rejected: status={status}")
            if emit_messages:
                actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
            return packet

    return handle_action_proposal_result_v77(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=emit_messages,
    )


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.79 fact inform proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v79(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v79(
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


class CmdSizaNoMatchV79(CmdSizaNoMatchV78):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        intent = parse_semantic_fact_inform_intent(raw)
        classification = classify_v741_input(self.caller, raw)
        if intent and classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v79(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV79(Command):
    key = "siza-validate-v79"
    aliases = ["validate-v79"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.79 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
        manifest = context.get("manifest")
        registry = get_consequence_registry(create=True)

        original_location = actor.location
        original_mara_location = mara.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_discovered = _clone(getattr(actor.db, "discovered_facts", []))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_memories = _clone(getattr(actor.db, "memories", []))
        original_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_perception_facts = _clone(getattr(site.db, "perception_facts", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.79 | {NATURAL_FACT_INFORM_BUILD} ===")
        self.caller.msg(
            "real discovery -> player Known Fact -> qwen selects visible recipient only -> deterministic retrieval -> authoritative Fact transfer"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            stats = _clone(getattr(actor.db, "adventure_stats", {}))
            if not isinstance(stats, dict):
                stats = {}
            stats["PER"] = 7
            actor.db.adventure_stats = stats
            actor.db.discovered_facts = [
                item for item in list(original_discovered or []) if str(item) != TEST_PERCEPTION_FACT_ID
            ]
            actor.db.knowledge = {
                str(key): value for key, value in dict(original_knowledge or {}).items()
                if str(key) != TEST_KNOWLEDGE_KEY
            }
            actor.db.knowledge_facts = [
                row for row in list(original_facts or [])
                if str((row or {}).get("id") or "") != TEST_KNOWLEDGE_FACT_ID
            ]
            mara.db.knowledge = {
                str(key): value for key, value in dict(original_mara_knowledge or {}).items()
                if str(key) != TEST_KNOWLEDGE_KEY
            }
            mara.db.knowledge_facts = [
                row for row in list(original_mara_facts or [])
                if str((row or {}).get("id") or "") != TEST_KNOWLEDGE_FACT_ID
            ]
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state

            intent = parse_semantic_fact_inform_intent(INFORM_PHRASE)
            classification = classify_v741_input(actor, INFORM_PHRASE)
            check(
                "semantic-inform-intent-is-player-authored-and-reaches-proposal-route",
                bool(intent)
                and intent.get("intent") == "INFORM_FACT"
                and intent.get("topic") == "la rozadura bajo el mostrador"
                and intent.get("topic_source") == "PLAYER_INPUT"
                and intent.get("retrieval_query") == "rozadura mostrador"
                and intent.get("retrieval_query_source") == "PLAYER_INPUT_FILTERED"
                and classification.get("route") == "AI_ACTION_PROPOSAL",
                f"route={classification.get('route')} topic={(intent or {}).get('topic')!r} query={(intent or {}).get('retrieval_query')!r}",
            )

            site.db.perception_facts = [_projectable_fact()]
            discovery = execute_deterministic_active_perception(actor, DETERMINISTIC_SEARCH_PHRASE)
            source_fact = find_knowledge_fact(actor, TEST_KNOWLEDGE_FACT_ID)
            check(
                "source-fact-is-created-by-real-perception-before-informing",
                discovery.get("status") == "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED"
                and discovery.get("engine_status") == "DISCOVERY"
                and source_fact is not None
                and fact_knowledge_state(actor, source_fact).get("known") is True,
                f"engine={discovery.get('engine_status')} known={None if source_fact is None else fact_knowledge_state(actor, source_fact).get('known')}",
            )

            retrieval = retrieve_known_facts(actor, query=(intent or {}).get("retrieval_query") or "", max_facts=3)
            check(
                "player-topic-retrieval-selects-exactly-one-known-fact",
                list(retrieval.get("selected_fact_ids") or []) == [TEST_KNOWLEDGE_FACT_ID],
                f"query={retrieval.get('query')!r} selected={retrieval.get('selected_fact_ids')}",
            )

            request = build_active_perception_proposal_request(actor, INFORM_PHRASE)
            catalog = list(request.get("catalog") or [])
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
                "qwen-boundary-sees-recipient-capability-and-player-text-but-not-known-fact-state",
                talk_cap is not None
                and analyze_cap is not None
                and movement_cap is not None
                and TEST_KNOWLEDGE_FACT_ID not in request_text
                and TEST_KNOWLEDGE_TEXT not in request_text
                and TEST_KNOWLEDGE_KEY not in request_text,
                f"talk={(talk_cap or {}).get('capability_id')} fact_leaked={TEST_KNOWLEDGE_TEXT in request_text}",
            )
            if not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.79 capabilities missing")

            before_low_knowledge = _clone(getattr(mara.db, "knowledge", {}))
            before_low_facts = _clone(getattr(mara.db, "knowledge_facts", []))
            low = execute_validated_fact_inform_proposal(
                actor,
                _accepted_result(talk_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
                raw_player_input=INFORM_PHRASE,
            )
            check(
                "low-confidence-recipient-selection-cannot-transfer-fact",
                low.get("status") == "LOW_CONFIDENCE"
                and _clone(getattr(mara.db, "knowledge", {})) == before_low_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == before_low_facts,
                f"status={low.get('status')}",
            )

            known_level = int(dict(getattr(actor.db, "knowledge", {}) or {}).get(TEST_KNOWLEDGE_KEY, 0) or 0)
            actor_levels = dict(getattr(actor.db, "knowledge", {}) or {})
            actor_levels[TEST_KNOWLEDGE_KEY] = 0
            actor.db.knowledge = actor_levels
            unknown_source = execute_validated_fact_inform_proposal(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=INFORM_PHRASE,
            )
            check(
                "fact-record-without-known-level-cannot-be-shared-by-natural-language",
                unknown_source.get("status") == "NO_KNOWN_FACT_FOR_TOPIC"
                and find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID) is None,
                f"status={unknown_source.get('status')}",
            )
            actor_levels[TEST_KNOWLEDGE_KEY] = known_level
            actor.db.knowledge = actor_levels

            mara.move_to(next(exit_obj.destination for exit_obj in site.exits if exit_obj.destination), quiet=True)
            stale = execute_validated_fact_inform_proposal(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=INFORM_PHRASE,
            )
            check(
                "recipient-is-revalidated-and-transfer-is-blocked-if-npc-moves",
                stale.get("status") == "STALE_OR_MISSING_CAPABILITY"
                and find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID) is None,
                f"status={stale.get('status')} mara_location={mara.location.key if mara.location else None}",
            )
            mara.move_to(site, quiet=True)

            unknown_topic = execute_validated_fact_inform_proposal(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=UNKNOWN_INFORM_PHRASE,
            )
            check(
                "unsupported-player-topic-cannot-cause-fabricated-fact-transfer",
                unknown_topic.get("status") == "NO_KNOWN_FACT_FOR_TOPIC"
                and find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID) is None,
                f"status={unknown_topic.get('status')}",
            )

            self.caller.msg(
                f"LIVE V079 KNOWN-FACT INFORM PROBE: action={INFORM_PHRASE!r} target={mara.key!r}"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-only-visible-mara-talk-capability",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "INTERACTION"
                and _capability_id(live) == str(talk_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_actor_fact = _clone(find_knowledge_fact(actor, TEST_KNOWLEDGE_FACT_ID))
            before_actor_memories = _clone(getattr(actor.db, "memories", []))
            before_actor_relationships = _clone(getattr(actor.db, "relationships", {}))
            live_handled = handle_action_proposal_result_v79(
                actor,
                live,
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
            )
            target_fact = find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID)
            target_state = fact_knowledge_state(mara, target_fact or {})
            transfers = list((target_fact or {}).get("transfer_history") or [])
            check(
                "live-known-fact-inform-preserves-source-and-adds-transfer-provenance",
                live_handled.get("status") == "FACT_INFORM_EXECUTED"
                and live_handled.get("executed") is True
                and (live_handled.get("transfer") or {}).get("reason") == "FACT_TRANSFERRED"
                and target_fact is not None
                and target_state.get("known") is True
                and target_fact.get("text") == TEST_KNOWLEDGE_TEXT
                and dict(target_fact.get("source") or {}) == dict((before_actor_fact or {}).get("source") or {})
                and dict(target_fact.get("learned_by") or {}) == dict((before_actor_fact or {}).get("learned_by") or {})
                and len(transfers) == 1
                and int((transfers[0] or {}).get("source_dbref") or 0) == int(actor.id),
                f"handler={live_handled.get('status')} transfer={(live_handled.get('transfer') or {}).get('reason')} known={target_state.get('known')}",
            )

            live_reason = str((live.get("proposal") or {}).get("reason") or "")
            persistent_blob = json.dumps(
                {
                    "actor_fact": find_knowledge_fact(actor, TEST_KNOWLEDGE_FACT_ID),
                    "target_fact": target_fact,
                    "target_knowledge": _clone(getattr(mara.db, "knowledge", {})),
                },
                ensure_ascii=False,
            )
            check(
                "model-reason-never-becomes-fact-provenance-or-social-state",
                live_reason not in persistent_blob
                and _clone(find_knowledge_fact(actor, TEST_KNOWLEDGE_FACT_ID)) == before_actor_fact
                and _clone(getattr(actor.db, "memories", [])) == before_actor_memories
                and _clone(getattr(actor.db, "relationships", {})) == before_actor_relationships,
                "model_reason_not_persisted=True source_fact_unchanged=True",
            )

            target_before_repeat = _clone(find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID))
            processed_before_repeat = _clone(getattr(registry.db, "processed_action_ids", []))
            repeated = handle_action_proposal_result_v79(
                actor,
                live,
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
            )
            target_after_repeat = find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID)
            check(
                "repeat-natural-inform-is-idempotent-and-does-not-emit-second-transfer-action",
                repeated.get("status") == "FACT_INFORM_EXECUTED"
                and (repeated.get("transfer") or {}).get("reason") == "ALREADY_TRANSFERRED"
                and _clone(target_after_repeat) == target_before_repeat
                and _clone(getattr(registry.db, "processed_action_ids", [])) == processed_before_repeat,
                f"reason={(repeated.get('transfer') or {}).get('reason')}",
            )

            self.caller.msg("--- LIVE V079 KNOWN-FACT INFORM RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "handler_status": live_handled.get("status"),
                "topic": live_handled.get("topic"),
                "retrieval_query": live_handled.get("retrieval_query"),
                "fact_id": live_handled.get("fact_id"),
                "target": live_handled.get("target_name"),
                "transfer_reason": (live_handled.get("transfer") or {}).get("reason"),
                "target_known": target_state.get("known"),
                "transfer_history_count": len(transfers),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V079 KNOWN-FACT INFORM RESULT ---")

            semantic_search = classify_v741_input(actor, "me pongo a escudriñar detrás del mostrador por si hay algo escondido")
            deterministic_search = classify_v741_input(actor, DETERMINISTIC_SEARCH_PHRASE)
            check(
                "v079-preserves-semantic-and-deterministic-perception-routing",
                semantic_search.get("route") == "AI_ACTION_PROPOSAL"
                and deterministic_search.get("route") == "PERCEPTION",
                f"semantic={semantic_search.get('route')} deterministic={deterministic_search.get('route')}",
            )

            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            greeting = handle_action_proposal_result_v79(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input="me acerco a Mara para intercambiar unas palabras",
                emit_messages=False,
            )
            check(
                "v079-preserves-normal-structured-interaction",
                greeting.get("status") == "INTERACTION_EXECUTED" and greeting.get("executed") is True,
                f"status={greeting.get('status')}",
            )
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_regression = handle_action_proposal_result_v79(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v079-preserves-object-action-execution",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement = handle_action_proposal_result_v79(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v079-preserves-real-exit-movement",
                movement.get("status") == "MOVEMENT_EXECUTED" and movement.get("executed") is True and actor.location != site,
                f"status={movement.get('status')} location={actor.location.key if actor.location else None}",
            )

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
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            manifest.db.state = original_manifest_state
            site.db.perception_facts = original_perception_facts
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Mara location, stats, discovery, Knowledge/Facts, social state, action histories, manifest, perception fixtures and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: qwen selects only the visible recipient; player-authored topic selects only known Facts; authoritative transfer engine owns recipient Knowledge and provenance"
        )
        self.caller.msg("========================================================")
