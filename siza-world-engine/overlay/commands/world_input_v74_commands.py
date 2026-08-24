import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v71_commands import classify_v71_input
from commands.world_input_v73_commands import (
    CmdSizaNoMatchV73,
    handle_action_proposal_result_v73,
)
from services.action_intent_proposal_engine import build_action_proposal_request
from services.action_proposal_async_runtime import (
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
    dispatch_action_proposal_async,
)
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.action_resolution_engine import action_resolution_history
from services.interaction_proposal_execution_bridge import (
    INTERACTION_BRIDGE_BUILD,
    execute_validated_interaction_proposal,
    extract_player_authored_topic,
)
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_TOPIC_INTERACTION_BUILD = "0.74.0-player-authored-semantic-topic-interaction"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar esa interacción."
SEMANTIC_TOPIC_PHRASE = "me acerco a Mara y le saco el tema del manifiesto duplicado"
TEST_FACT_ID = "FACT-V074-MARA-MANIFIESTO-DUPLICADO-001"
TEST_KNOWLEDGE_KEY = "V074_MARA_MANIFIESTO_DUPLICADO"
TEST_FACT_TEXT = "Mara confirma que el manifiesto duplicado corresponde al registro vinculado al relevo de cierre."
PRIVATE_SENTINEL = "NEVER_LEAK_V074_PRIVATE_FACT_SENTINEL"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def handle_action_proposal_result_v74(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
):
    """Preserve v0.73 behavior, but let INTERACTION carry only an explicitly player-authored topic into the existing engine."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return handle_action_proposal_result_v73(actor, proposal_result, emit_messages=emit_messages)

    if _proposal_kind(proposal_result) != "INTERACTION":
        return handle_action_proposal_result_v73(actor, proposal_result, emit_messages=emit_messages)

    bridge = execute_validated_interaction_proposal(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
    )
    bridge_status = str((bridge or {}).get("status") or "")

    if bridge_status == "INTERACTION_EXECUTED":
        text = str((bridge or {}).get("response_text") or "").strip()
        if emit_messages and text:
            actor.msg("\n" + text)
        return {
            "status": "INTERACTION_EXECUTED",
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
        return {"status": "NO_INTERACTION_STALE", "executed": False, "bridge": bridge}

    logger.log_err(f"SIZA topic interaction proposal rejected before interaction: status={bridge_status}")
    if emit_messages:
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return {"status": "NO_INTERACTION_REJECTED", "executed": False, "bridge": bridge}


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA topic interaction proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v74(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v74(
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


class CmdSizaNoMatchV74(CmdSizaNoMatchV73):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v71_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v74(self.caller, raw)
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


def _latest_memory(holder):
    try:
        rows = list(holder.db.memories or [])
    except Exception:
        return {}
    if not rows:
        return {}
    try:
        return {str(k): v for k, v in rows[-1].items()}
    except Exception:
        return {}


class CmdSizaValidateV74(Command):
    key = "siza-validate-v74"
    aliases = ["validate-v74"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.74 VALIDATION] FAIL | context={context}")
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
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.74 | {NATURAL_TOPIC_INTERACTION_BUILD} ===")
        self.caller.msg(
            "player-authored topic text -> qwen selects only visible TALK target -> fresh revalidation -> existing Knowledge-gated interaction engine"
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

            # Isolate one modern structured Fact so the test cannot accidentally match older persistent dialogue data.
            mara.db.knowledge = {}
            mara.db.knowledge_facts = []
            upsert_knowledge_fact(
                mara,
                {
                    "id": TEST_FACT_ID,
                    "topic": "manifiesto duplicado",
                    "aliases": ["registro duplicado"],
                    "text": TEST_FACT_TEXT,
                    "knowledge_key": TEST_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"private_validator_sentinel": PRIVATE_SENTINEL},
                },
            )

            direct = classify_v71_input(actor, "hablo con Mara sobre manifiesto duplicado")
            check(
                "explicit-deterministic-talk-with-topic-still-bypasses-action-llm",
                direct.get("route") == "INTERACTION" and direct.get("ai_allowed") is False,
                f"route={direct.get('route')}",
            )

            semantic = classify_v71_input(actor, SEMANTIC_TOPIC_PHRASE)
            topic = extract_player_authored_topic(SEMANTIC_TOPIC_PHRASE)
            check(
                "semantic-topic-social-phrase-reaches-proposal-and-topic-is-player-derived",
                semantic.get("route") == "AI_ACTION_PROPOSAL"
                and semantic.get("ai_allowed") is True
                and topic == "manifiesto duplicado",
                f"route={semantic.get('route')} topic={topic!r}",
            )

            request = build_action_proposal_request(actor, SEMANTIC_TOPIC_PHRASE)
            catalog = list(request.get("catalog") or [])
            mara_cap = next(
                (row for row in catalog if row.get("kind") == "INTERACTION" and int(row.get("target_dbref") or 0) == int(mara.id)),
                None,
            )
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            movement_cap = next((row for row in catalog if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"), None)
            request_text = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            check(
                "qwen-boundary-sees-talk-catalog-and-player-text-but-not-private-fact-state",
                mara_cap is not None
                and analyze_cap is not None
                and movement_cap is not None
                and TEST_FACT_TEXT not in request_text
                and PRIVATE_SENTINEL not in request_text
                and TEST_KNOWLEDGE_KEY not in request_text,
                f"talk={(mara_cap or {}).get('capability_id')} fact_leaked={TEST_FACT_TEXT in request_text}",
            )
            if not mara_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.74 capabilities missing")

            # Knowledge level 0: target selection may succeed, but engine must not reveal the Fact.
            mara.db.knowledge = {TEST_KNOWLEDGE_KEY: 0}
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            blocked = handle_action_proposal_result_v74(
                actor,
                _accepted_result(mara_cap, 1.0, reason="model must not authorize fact access"),
                raw_player_input=SEMANTIC_TOPIC_PHRASE,
                emit_messages=False,
            )
            blocked_memory = _latest_memory(actor)
            check(
                "knowledge-gate-remains-authoritative-after-llm-target-selection",
                blocked.get("status") == "INTERACTION_EXECUTED"
                and TEST_FACT_TEXT not in str(blocked.get("rendered_text") or "")
                and blocked_memory.get("outcome") == "no_information"
                and blocked_memory.get("topic") == "manifiesto duplicado",
                f"text={blocked.get('rendered_text')!r} outcome={blocked_memory.get('outcome')}",
            )

            # Knowledge level 1: the same existing engine may now share exactly the modern Fact.text field.
            mara.db.knowledge = {TEST_KNOWLEDGE_KEY: 1}
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            allowed = handle_action_proposal_result_v74(
                actor,
                _accepted_result(mara_cap, 1.0, reason="invented model explanation must never render"),
                raw_player_input=SEMANTIC_TOPIC_PHRASE,
                emit_messages=False,
            )
            allowed_memory = _latest_memory(actor)
            check(
                "modern-structured-fact-text-is-shared-only-through-existing-interaction-engine",
                allowed.get("status") == "INTERACTION_EXECUTED"
                and allowed.get("rendered_text") == TEST_FACT_TEXT
                and allowed_memory.get("outcome") == "knowledge_shared"
                and allowed_memory.get("fact_id") == TEST_FACT_ID
                and allowed_memory.get("fact_text") == TEST_FACT_TEXT,
                f"text={allowed.get('rendered_text')!r} fact_id={allowed_memory.get('fact_id')}",
            )

            check(
                "model-reason-cannot-rewrite-player-topic-or-become-game-state",
                (allowed.get("bridge") or {}).get("topic") == "manifiesto duplicado"
                and (allowed.get("bridge") or {}).get("topic_source") == "PLAYER_INPUT"
                and "invented model explanation" not in json.dumps(allowed_memory, ensure_ascii=False)
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts,
                f"topic={(allowed.get('bridge') or {}).get('topic')!r}",
            )

            # Freshness still matters with topic-bearing interactions.
            other_room = next(
                (getattr(exit_obj, "destination", None) for exit_obj in list(getattr(site, "exits", []) or []) if getattr(exit_obj, "destination", None)),
                None,
            )
            if not other_room:
                raise RuntimeError("alternate room missing for v0.74 stale test")
            actor.db.memories = original_memories
            mara.db.memories = original_mara_memories
            mara.move_to(other_room, quiet=True)
            stale = handle_action_proposal_result_v74(
                actor,
                _accepted_result(mara_cap, 1.0),
                raw_player_input=SEMANTIC_TOPIC_PHRASE,
                emit_messages=False,
            )
            check(
                "topic-interaction-proposal-is-rejected-if-npc-moves-before-callback",
                stale.get("status") == "NO_INTERACTION_STALE"
                and not stale.get("executed")
                and _clone(getattr(actor.db, "memories", [])) == original_memories,
                f"status={stale.get('status')} mara_location={mara.location.key if mara.location else None}",
            )
            mara.move_to(site, quiet=True)

            self.caller.msg(
                f"LIVE V074 TOPIC INTERACTION PROBE: action={SEMANTIC_TOPIC_PHRASE!r} target={mara.key!r} topic='manifiesto duplicado'"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-only-the-visible-mara-talk-capability",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "INTERACTION"
                and str((live.get("proposal") or {}).get("capability_id") or "") == str(mara_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            live_handled = handle_action_proposal_result_v74(
                actor,
                live,
                raw_player_input=SEMANTIC_TOPIC_PHRASE,
                emit_messages=False,
            )
            live_memory = _latest_memory(actor)
            check(
                "live-topic-path-revalidates-target-and-shares-only-authorized-fact-text",
                live_handled.get("status") == "INTERACTION_EXECUTED"
                and live_handled.get("rendered_text") == TEST_FACT_TEXT
                and (live_handled.get("bridge") or {}).get("topic") == "manifiesto duplicado"
                and live_memory.get("outcome") == "knowledge_shared"
                and live_memory.get("fact_id") == TEST_FACT_ID,
                f"handler={live_handled.get('status')} text={live_handled.get('rendered_text')!r}",
            )

            check(
                "live-topic-interaction-does-not-create-action-history-transfer-facts-or-persist-model-reason",
                len(object_action_history(actor)) == before_obj
                and len(action_resolution_history(actor)) == before_res
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts
                and str((live.get("proposal") or {}).get("reason") or "") not in json.dumps(live_memory, ensure_ascii=False),
                "histories_unchanged=True player_facts_unchanged=True model_reason_not_persisted=True",
            )

            self.caller.msg("--- LIVE V074 TOPIC RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "handler_status": live_handled.get("status"),
                "target": (live_handled.get("bridge") or {}).get("target_name"),
                "topic": (live_handled.get("bridge") or {}).get("topic"),
                "topic_source": (live_handled.get("bridge") or {}).get("topic_source"),
                "response_text": live_handled.get("rendered_text"),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V074 TOPIC RESULT ---")

            # Regression: no explicit topic still behaves like v0.73 greeting interaction.
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            greeting = handle_action_proposal_result_v74(
                actor,
                _accepted_result(mara_cap, 1.0),
                raw_player_input="me acerco a Mara para intercambiar unas palabras",
                emit_messages=False,
            )
            check(
                "v074-preserves-v073-topicless-greeting-interaction",
                greeting.get("status") == "INTERACTION_EXECUTED"
                and (_latest_memory(actor).get("outcome") == "greeting")
                and (greeting.get("bridge") or {}).get("topic") is None,
                f"status={greeting.get('status')} text={greeting.get('rendered_text')!r}",
            )

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_regression = handle_action_proposal_result_v74(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v074-preserves-object-action-bridge",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (object_regression.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')} engine={(object_regression.get('bridge') or {}).get('world_engine_status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement_regression = handle_action_proposal_result_v74(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v074-preserves-real-exit-movement-bridge",
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
            "STATE RESTORED: actor/Mara location, memories, relationships, Knowledge/Facts, action histories and manifest state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: qwen selects only current TALK target; explicit topic text comes from player input; existing interaction engine owns Knowledge gate and Fact text"
        )
        self.caller.msg("========================================================")
