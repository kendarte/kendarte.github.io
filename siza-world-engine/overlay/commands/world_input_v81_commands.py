import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v79_commands import INFORM_PHRASE, _accepted_result
from commands.world_input_v80_commands import handle_action_proposal_result_v80
from commands.world_input_v801_commands import CmdSizaNoMatchV801
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.consequence_engine import get_consequence_registry
from services.conversation_fact_acquisition_engine import resolve_interaction_with_fact_acquisition
from services.grounded_dialogue_renderer import (
    GROUNDED_DIALOGUE_RENDER_BUILD,
    build_grounded_dialogue_request,
    render_grounded_dialogue_async,
    render_grounded_dialogue_sync,
    validate_grounded_dialogue_text,
)
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import fact_knowledge_state, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.object_action_engine import object_action_history
from services.action_resolution_engine import action_resolution_history
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_GROUNDED_DIALOGUE_BUILD = "0.81.0-grounded-conversational-fact-render"
SEMANTIC_DIALOGUE_PHRASE = "me acerco a Mara y le pregunto por el sello del turno de madrugada"
EXPLICIT_DIALOGUE_PHRASE = "pregunto a Mara sobre sello del turno de madrugada"
TEST_FACT_ID = "KFACT-V081-MARA-SELLO-001"
TEST_KNOWLEDGE_KEY = "V081_MARA_SELLO"
TEST_TOPIC = "sello del turno de madrugada"
TEST_TEXT = "El sello del turno de madrugada fue estampado después del cierre de la dársena."
PRIVATE_SENTINEL = "NEVER_LEAK_V081_PRIVATE_PROVENANCE"


def _acquisition_can_render(acquisition):
    status = str((acquisition or {}).get("status") or "")
    return status in {"FACT_ACQUIRED", "FACT_ALREADY_ACQUIRED"} and bool(str((acquisition or {}).get("fact_text") or "").strip())


def present_conversation_result_v81(
    actor,
    packet,
    *,
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """Render only an already-authorized shared Fact; all other dialogue remains deterministic."""
    result = dict(packet or {})
    text = str(result.get("response_text") or result.get("rendered_text") or "").strip()
    acquisition = dict(result.get("knowledge_acquisition") or {})
    if not _acquisition_can_render(acquisition):
        if emit_messages and text:
            actor.msg("\n" + text)
        return {
            **result,
            "dialogue_render": {
                "status": "NOT_APPLICABLE",
                "queued": False,
                "build": GROUNDED_DIALOGUE_RENDER_BUILD,
            },
            "build": NATURAL_GROUNDED_DIALOGUE_BUILD,
        }

    renderer = render_async_callable or render_grounded_dialogue_async
    render_packet = renderer(
        actor,
        str(acquisition.get("source_name") or "NPC"),
        str(acquisition.get("topic") or ""),
        str(acquisition.get("fact_text") or text),
        fallback_text=text or str(acquisition.get("fact_text") or ""),
        **dict(provider_options or {}),
    )
    return {
        **result,
        "dialogue_render": render_packet,
        "build": NATURAL_GROUNDED_DIALOGUE_BUILD,
    }


def handle_action_proposal_result_v81(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """Preserve v0.80 authority, then optionally render only the exact Fact it transferred."""
    if parse_semantic_fact_inform_intent(raw_player_input):
        return handle_action_proposal_result_v80(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    base = handle_action_proposal_result_v80(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=False,
    )
    if str(base.get("status") or "") != "INTERACTION_EXECUTED":
        if emit_messages:
            text = str(base.get("response_text") or base.get("rendered_text") or "").strip()
            if text:
                actor.msg("\n" + text)
        return base

    return present_conversation_result_v81(
        actor,
        base,
        emit_messages=emit_messages,
        render_async_callable=render_async_callable,
        provider_options=provider_options,
    )


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.81 action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v81(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v81(
            current_actor,
            proposal_result,
            raw_player_input=raw,
            emit_messages=True,
            provider_options=provider_options,
        )

    return dispatch_active_perception_proposal_async(
        actor,
        raw,
        on_result=_handle,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV81(CmdSizaNoMatchV801):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "INTERACTION" and classification.get("explicit_talk_precedence"):
            packet = resolve_interaction_with_fact_acquisition(
                self.caller,
                classification.get("intent") or parse_interaction_intent(raw) or {"intent": "TALK", "raw": raw},
            )
            present_conversation_result_v81(self.caller, packet, emit_messages=True)
            return None
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v81(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV81(Command):
    key = "siza-validate-v81"
    aliases = ["validate-v81"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.81 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
        manifest = context.get("manifest")
        registry = get_consequence_registry(create=True)

        original_location = actor.location
        original_mara_location = mara.location
        original_actor_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_actor_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_actor_memories = _clone(getattr(actor.db, "memories", []))
        original_actor_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.81 | {NATURAL_GROUNDED_DIALOGUE_BUILD} ===")
        self.caller.msg("authoritative conversation/transfer first -> exact shared Fact only -> read-only qwen dialogue render -> lexical grounding guard -> authored fallback")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            actor.db.knowledge = {str(k): v for k, v in dict(original_actor_knowledge or {}).items() if str(k) != TEST_KNOWLEDGE_KEY}
            actor.db.knowledge_facts = [row for row in list(original_actor_facts or []) if str((row or {}).get("id") or "") != TEST_FACT_ID]
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara.db.knowledge = {TEST_KNOWLEDGE_KEY: 1}
            mara.db.knowledge_facts = []
            mara.db.memories = _clone(original_mara_memories)
            mara.db.relationships = _clone(original_mara_relationships)
            upsert_knowledge_fact(
                mara,
                {
                    "id": TEST_FACT_ID,
                    "topic": TEST_TOPIC,
                    "aliases": ["sello de madrugada", "turno de madrugada"],
                    "text": TEST_TEXT,
                    "knowledge_key": TEST_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"validator_private_sentinel": PRIVATE_SENTINEL},
                    "learned_by": {"provider": "V081_VALIDATOR"},
                },
            )
            set_knowledge_level(mara, TEST_KNOWLEDGE_KEY, 1)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            explicit = classify_v741_input(actor, EXPLICIT_DIALOGUE_PHRASE)
            semantic = classify_v741_input(actor, SEMANTIC_DIALOGUE_PHRASE)
            check(
                "explicit-and-semantic-talk-routing-remains-authoritative-before-rendering",
                explicit.get("route") == "INTERACTION"
                and explicit.get("ai_allowed") is False
                and semantic.get("route") == "AI_ACTION_PROPOSAL"
                and semantic.get("ai_allowed") is True,
                f"explicit={explicit.get('route')} semantic={semantic.get('route')}",
            )

            request = build_active_perception_proposal_request(actor, SEMANTIC_DIALOGUE_PHRASE)
            catalog = list(request.get("catalog") or [])
            talk_cap = next((row for row in catalog if row.get("kind") == "INTERACTION" and int(row.get("target_dbref") or 0) == int(mara.id)), None)
            analyze_cap = next((row for row in catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID), None)
            movement_cap = next((row for row in catalog if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"), None)
            if not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.81 capabilities missing")

            captured = {}

            def fake_async(current_actor, npc_name, topic, fact_text, *, fallback_text="", **kwargs):
                captured.update({
                    "actor": current_actor,
                    "npc_name": npc_name,
                    "topic": topic,
                    "fact_text": fact_text,
                    "fallback_text": fallback_text,
                })
                return {"status": "DIALOGUE_RENDER_QUEUED", "queued": True, "build": GROUNDED_DIALOGUE_RENDER_BUILD}

            semantic_packet = handle_action_proposal_result_v81(
                actor,
                _accepted_result(talk_cap, 1.0, reason="V081_TARGET_ONLY_REASON"),
                raw_player_input=SEMANTIC_DIALOGUE_PHRASE,
                emit_messages=False,
                render_async_callable=fake_async,
            )
            acquired = find_knowledge_fact(actor, TEST_FACT_ID)
            check(
                "semantic-talk-transfers-exact-fact-before-queuing-renderer",
                semantic_packet.get("status") == "INTERACTION_EXECUTED"
                and (semantic_packet.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and fact_knowledge_state(actor, acquired).get("known") is True
                and captured.get("fact_text") == TEST_TEXT
                and captured.get("topic") == TEST_TOPIC
                and captured.get("npc_name") == mara.key,
                f"acquisition={(semantic_packet.get('knowledge_acquisition') or {}).get('status')} queued={(semantic_packet.get('dialogue_render') or {}).get('queued')}",
            )

            render_request = build_grounded_dialogue_request(mara.key, TEST_TOPIC, TEST_TEXT)
            render_boundary = json.dumps(render_request.get("provider_payload") or {}, ensure_ascii=False)
            check(
                "dialogue-provider-boundary-contains-exact-shared-text-but-no-private-provenance-or-fact-id",
                TEST_TEXT in render_boundary
                and TEST_TOPIC in render_boundary
                and TEST_FACT_ID not in render_boundary
                and TEST_KNOWLEDGE_KEY not in render_boundary
                and PRIVATE_SENTINEL not in render_boundary,
                f"private_leaked={PRIVATE_SENTINEL in render_boundary}",
            )

            unsafe = validate_grounded_dialogue_text(
                "El capitán Rojas confirma que ocurrió a las 23:45.",
                npc_name=mara.key,
                topic=TEST_TOPIC,
                fact_text=TEST_TEXT,
            )
            check(
                "grounding-guard-rejects-new-names-and-numbers",
                unsafe.get("valid") is False and unsafe.get("status") in {"NEW_NUMBER", "NEW_PROPER_NAME"},
                f"status={unsafe.get('status')}",
            )

            def unsafe_provider(payload, **kwargs):
                return {"status": "OK", "text": "El capitán Rojas confirma que ocurrió a las 23:45."}

            unsafe_render = render_grounded_dialogue_sync(
                mara.key,
                TEST_TOPIC,
                TEST_TEXT,
                fallback_text=TEST_TEXT,
                provider_callable=unsafe_provider,
            )
            check(
                "ungrounded-provider-output-falls-back-to-authored-fact-text",
                unsafe_render.get("status") == "FALLBACK_UNGROUNDED_RENDER"
                and unsafe_render.get("rendered") is False
                and unsafe_render.get("display_text") == TEST_TEXT,
                f"status={unsafe_render.get('status')}",
            )

            def failed_provider(payload, **kwargs):
                return {"status": "TRANSPORT_ERROR", "text": "", "error": "validator transport failure"}

            failed_render = render_grounded_dialogue_sync(
                mara.key,
                TEST_TOPIC,
                TEST_TEXT,
                fallback_text=TEST_TEXT,
                provider_callable=failed_provider,
            )
            check(
                "provider-failure-also-falls-back-without-changing-fact-authority",
                failed_render.get("status") == "FALLBACK_PROVIDER_FAILURE"
                and failed_render.get("display_text") == TEST_TEXT,
                f"status={failed_render.get('status')}",
            )

            before_render_state = _clone({
                "actor_knowledge": getattr(actor.db, "knowledge", {}),
                "actor_facts": getattr(actor.db, "knowledge_facts", []),
                "actor_memories": getattr(actor.db, "memories", []),
                "actor_relationships": getattr(actor.db, "relationships", {}),
                "mara_knowledge": getattr(mara.db, "knowledge", {}),
                "mara_facts": getattr(mara.db, "knowledge_facts", []),
                "registry_processed": getattr(registry.db, "processed_action_ids", []),
                "registry_log": getattr(registry.db, "action_log", []),
            })
            self.caller.msg(f"LIVE V081 GROUNDED DIALOGUE PROBE: fact={TEST_TEXT!r}")
            live_render = render_grounded_dialogue_sync(
                mara.key,
                TEST_TOPIC,
                TEST_TEXT,
                fallback_text=TEST_TEXT,
                timeout=60,
            )
            after_render_state = _clone({
                "actor_knowledge": getattr(actor.db, "knowledge", {}),
                "actor_facts": getattr(actor.db, "knowledge_facts", []),
                "actor_memories": getattr(actor.db, "memories", []),
                "actor_relationships": getattr(actor.db, "relationships", {}),
                "mara_knowledge": getattr(mara.db, "knowledge", {}),
                "mara_facts": getattr(mara.db, "knowledge_facts", []),
                "registry_processed": getattr(registry.db, "processed_action_ids", []),
                "registry_log": getattr(registry.db, "action_log", []),
            })
            check(
                "live-qwen-dialogue-render-is-grounded-and-read-only",
                live_render.get("status") == "GROUNDED_DIALOGUE_RENDERED"
                and live_render.get("rendered") is True
                and bool(str(live_render.get("display_text") or "").strip())
                and before_render_state == after_render_state,
                f"status={live_render.get('status')} text={live_render.get('display_text')!r}",
            )

            actor.db.knowledge = {str(k): v for k, v in dict(original_actor_knowledge or {}).items() if str(k) != TEST_KNOWLEDGE_KEY}
            actor.db.knowledge_facts = [row for row in list(original_actor_facts or []) if str((row or {}).get("id") or "") != TEST_FACT_ID]
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara_levels = dict(getattr(mara.db, "knowledge", {}) or {})
            mara_levels[TEST_KNOWLEDGE_KEY] = 0
            mara.db.knowledge = mara_levels
            no_info_capture = {}

            def should_not_render(*args, **kwargs):
                no_info_capture["called"] = True
                return {"status": "SHOULD_NOT_RUN"}

            no_info = handle_action_proposal_result_v81(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=SEMANTIC_DIALOGUE_PHRASE,
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "no-information-conversation-never-invokes-qwen-dialogue-renderer",
                no_info.get("status") == "INTERACTION_EXECUTED"
                and (no_info.get("knowledge_acquisition") or {}).get("status") == "NO_SHARED_FACT_IN_NEW_CONVERSATION"
                and not no_info_capture.get("called"),
                f"acquisition={(no_info.get('knowledge_acquisition') or {}).get('status')}",
            )
            mara_levels[TEST_KNOWLEDGE_KEY] = 1
            mara.db.knowledge = mara_levels

            inform = handle_action_proposal_result_v81(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "player-to-npc-inform-remains-owned-by-v079-and-does-not-enter-dialogue-renderer",
                str(inform.get("build") or "") != NATURAL_GROUNDED_DIALOGUE_BUILD,
                f"status={inform.get('status')} build={inform.get('build')}",
            )

            # Non-interaction bridge regression: valid authored OBJECT_ACTION still delegates to v0.80 unchanged.
            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state
            fresh_request = build_active_perception_proposal_request(actor, SEMANTIC_DIALOGUE_PHRASE)
            fresh_catalog = list(fresh_request.get("catalog") or [])
            fresh_analyze = next((row for row in fresh_catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID), None)
            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_result = handle_action_proposal_result_v81(actor, _accepted_result(fresh_analyze, 1.0), emit_messages=False, render_async_callable=should_not_render)
            check(
                "v081-preserves-noninteraction-object-action-bridge",
                object_result.get("status") == "WORLD_ENGINE_ACCEPTED"
                and object_result.get("executed") is True
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1
                and not no_info_capture.get("called"),
                f"status={object_result.get('status')}",
            )
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)

            movement_result = handle_action_proposal_result_v81(actor, _accepted_result(movement_cap, 1.0), emit_messages=False, render_async_callable=should_not_render)
            check(
                "v081-preserves-real-exit-movement-bridge",
                movement_result.get("status") == "MOVEMENT_EXECUTED" and movement_result.get("executed") is True and actor.location != site,
                f"status={movement_result.get('status')} location={actor.location.key if actor.location else None}",
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
            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.memories = original_actor_memories
            actor.db.relationships = original_actor_relationships
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            manifest.db.state = original_manifest_state
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor/Mara location, Knowledge/Facts, social state, object histories, manifest and consequence registry restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: interaction/transfer engines decide and persist the Fact first; qwen is presentation-only and guarded by authored fallback")
        self.caller.msg("========================================================")
