import json

from evennia import Command

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v79_commands import (
    CmdSizaNoMatchV79,
    INFORM_PHRASE,
    _accepted_result,
    handle_action_proposal_result_v79,
)
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.active_perception_proposal_runtime import build_active_perception_proposal_request
from services.consequence_engine import get_consequence_registry
from services.conversation_fact_acquisition_engine import (
    CONVERSATION_FACT_ACQUISITION_BUILD,
    acquire_fact_from_new_conversation,
    resolve_interaction_with_fact_acquisition,
)
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import fact_knowledge_state, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.object_action_engine import object_action_history
from services.action_resolution_engine import action_resolution_history
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_CONVERSATION_ACQUISITION_BUILD = "0.80.0-conversation-fact-to-player-knowledge"
SEMANTIC_ASK_PHRASE = "me acerco a Mara y le saco el tema del registro del relevo nocturno"
EXPLICIT_ASK_PHRASE = "pregunto a Mara sobre registro del relevo nocturno"
TEST_FACT_ID = "KFACT-V080-MARA-RELEVO-001"
TEST_KNOWLEDGE_KEY = "V080_MARA_RELEVO"
TEST_TOPIC = "registro del relevo nocturno"
TEST_TEXT = "Mara sabe que el registro del relevo nocturno fue firmado después del cierre de la dársena."
PRIVATE_SENTINEL = "NEVER_LEAK_V080_PRIVATE_NPC_FACT"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def handle_action_proposal_result_v80(actor, proposal_result, *, raw_player_input="", emit_messages=True):
    """Preserve v0.79 INFORM; for ordinary semantic TALK, persist only the Fact the existing interaction engine actually shared."""
    if parse_semantic_fact_inform_intent(raw_player_input):
        return handle_action_proposal_result_v79(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    if (
        isinstance(proposal_result, dict)
        and proposal_result.get("status") == "ACCEPTED"
        and proposal_result.get("accepted") is True
        and _proposal_kind(proposal_result) == "INTERACTION"
    ):
        before_count = len(_plain_list(getattr(actor.db, "memories", [])))
        base = handle_action_proposal_result_v79(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=False,
        )
        if base.get("status") == "INTERACTION_EXECUTED" and base.get("executed") is True:
            acquisition = acquire_fact_from_new_conversation(
                actor,
                before_count,
                expected_target_dbref=base.get("target_dbref"),
            )
            result = {
                **base,
                "knowledge_acquisition": acquisition,
                "build": NATURAL_CONVERSATION_ACQUISITION_BUILD,
            }
            text = str(base.get("response_text") or "").strip()
            if emit_messages and text:
                actor.msg("\n" + text)
            return result
        return base

    return handle_action_proposal_result_v79(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=emit_messages,
    )


class CmdSizaNoMatchV80(CmdSizaNoMatchV79):
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
            text = str(packet.get("response_text") or "").strip()
            if text:
                self.caller.msg("\n" + text)
            return None
        return super().func()


class CmdSizaValidateV80(Command):
    key = "siza-validate-v80"
    aliases = ["validate-v80"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.80 VALIDATION] FAIL | context={context}")
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
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.80 | {NATURAL_CONVERSATION_ACQUISITION_BUILD} ===")
        self.caller.msg("NPC shares authorized Fact -> existing conversation memory identifies exact fact_id -> authoritative NPC-to-player transfer")

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
                    "aliases": ["relevo nocturno", "registro del relevo"],
                    "text": TEST_TEXT,
                    "knowledge_key": TEST_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"validator_private_sentinel": PRIVATE_SENTINEL, "site_room_id": str(getattr(site.db, "room_id", "") or "")},
                    "learned_by": {"provider": "V080_VALIDATOR"},
                },
            )
            set_knowledge_level(mara, TEST_KNOWLEDGE_KEY, 1)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            explicit_class = classify_v741_input(actor, EXPLICIT_ASK_PHRASE)
            check(
                "explicit-topic-talk-remains-deterministic-and-off-llm",
                explicit_class.get("route") == "INTERACTION" and explicit_class.get("ai_allowed") is False,
                f"route={explicit_class.get('route')}",
            )

            cmd = CmdSizaNoMatchV80()
            cmd.caller = actor
            cmd.args = EXPLICIT_ASK_PHRASE
            cmd.raw_string = EXPLICIT_ASK_PHRASE
            cmd.cmdstring = cmd.key
            cmd.func()
            actor_fact = find_knowledge_fact(actor, TEST_FACT_ID)
            actor_state = fact_knowledge_state(actor, actor_fact or {})
            transfers = list((actor_fact or {}).get("transfer_history") or [])
            check(
                "real-explicit-talk-now-persists-authorized-npc-fact-on-player",
                actor_fact is not None
                and actor_state.get("known") is True
                and actor_fact.get("text") == TEST_TEXT
                and len(transfers) == 1
                and int((transfers[0] or {}).get("source_dbref") or 0) == int(mara.id)
                and int((transfers[0] or {}).get("target_dbref") or 0) == int(actor.id),
                f"known={actor_state.get('known')} transfers={len(transfers)}",
            )

            source_fact = find_knowledge_fact(mara, TEST_FACT_ID)
            check(
                "npc-to-player-transfer-preserves-original-source-and-learning-provenance",
                dict((actor_fact or {}).get("source") or {}) == dict((source_fact or {}).get("source") or {})
                and dict((actor_fact or {}).get("learned_by") or {}) == dict((source_fact or {}).get("learned_by") or {}),
                f"fact={TEST_FACT_ID}",
            )

            retrieval = retrieve_known_facts(actor, query="relevo nocturno")
            check(
                "conversation-acquired-fact-enters-normal-player-retrieval",
                TEST_FACT_ID in list(retrieval.get("selected_fact_ids") or []) and TEST_TEXT in str(retrieval.get("context_text") or ""),
                f"selected={retrieval.get('selected_fact_ids')}",
            )

            fact_before_repeat = _clone(find_knowledge_fact(actor, TEST_FACT_ID))
            processed_before_repeat = _clone(getattr(registry.db, "processed_action_ids", []))
            cmd2 = CmdSizaNoMatchV80()
            cmd2.caller = actor
            cmd2.args = EXPLICIT_ASK_PHRASE
            cmd2.raw_string = EXPLICIT_ASK_PHRASE
            cmd2.cmdstring = cmd2.key
            cmd2.func()
            check(
                "repeat-explicit-conversation-acquisition-is-idempotent",
                _clone(find_knowledge_fact(actor, TEST_FACT_ID)) == fact_before_repeat
                and _clone(getattr(registry.db, "processed_action_ids", [])) == processed_before_repeat,
                "fact_unchanged=True",
            )

            actor.db.knowledge = {str(k): v for k, v in dict(original_actor_knowledge or {}).items() if str(k) != TEST_KNOWLEDGE_KEY}
            actor.db.knowledge_facts = [row for row in list(original_actor_facts or []) if str((row or {}).get("id") or "") != TEST_FACT_ID]
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara.db.memories = _clone(original_mara_memories)
            mara.db.relationships = _clone(original_mara_relationships)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            request = build_active_perception_proposal_request(actor, SEMANTIC_ASK_PHRASE)
            catalog = list(request.get("catalog") or [])
            talk_cap = next((row for row in catalog if row.get("kind") == "INTERACTION" and int(row.get("target_dbref") or 0) == int(mara.id)), None)
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            movement_cap = next((row for row in catalog if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"), None)
            payload = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            check(
                "semantic-talk-provider-boundary-still-exposes-only-target-capability-not-npc-facts",
                talk_cap is not None and analyze_cap is not None and movement_cap is not None
                and TEST_FACT_ID not in payload and TEST_TEXT not in payload and TEST_KNOWLEDGE_KEY not in payload and PRIVATE_SENTINEL not in payload,
                f"talk={(talk_cap or {}).get('capability_id')} leaked={PRIVATE_SENTINEL in payload}",
            )
            if not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.80 capabilities missing")

            semantic = handle_action_proposal_result_v80(
                actor,
                _accepted_result(talk_cap, 1.0, reason="V080_REASON_MUST_NOT_PERSIST"),
                raw_player_input=SEMANTIC_ASK_PHRASE,
                emit_messages=False,
            )
            semantic_fact = find_knowledge_fact(actor, TEST_FACT_ID)
            check(
                "semantic-talk-also-acquires-only-the-fact-existing-engine-shared",
                semantic.get("status") == "INTERACTION_EXECUTED"
                and (semantic.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and semantic_fact is not None
                and fact_knowledge_state(actor, semantic_fact).get("known") is True,
                f"handler={semantic.get('status')} acquisition={(semantic.get('knowledge_acquisition') or {}).get('status')}",
            )

            persistent_blob = json.dumps(_clone({
                "actor_fact": semantic_fact,
                "actor_memories": getattr(actor.db, "memories", []),
                "actor_relationships": getattr(actor.db, "relationships", {}),
            }), ensure_ascii=False)
            check(
                "model-reason-never-enters-player-knowledge-or-social-state",
                "V080_REASON_MUST_NOT_PERSIST" not in persistent_blob,
                "reason_persisted=False",
            )

            actor.db.knowledge = {str(k): v for k, v in dict(original_actor_knowledge or {}).items() if str(k) != TEST_KNOWLEDGE_KEY}
            actor.db.knowledge_facts = [row for row in list(original_actor_facts or []) if str((row or {}).get("id") or "") != TEST_FACT_ID]
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara.db.memories = _clone(original_mara_memories)
            mara.db.relationships = _clone(original_mara_relationships)
            mara_levels = dict(getattr(mara.db, "knowledge", {}) or {})
            mara_levels[TEST_KNOWLEDGE_KEY] = 0
            mara.db.knowledge = mara_levels
            no_info = handle_action_proposal_result_v80(actor, _accepted_result(talk_cap, 1.0), raw_player_input=SEMANTIC_ASK_PHRASE, emit_messages=False)
            check(
                "npc-that-does-not-know-fact-cannot-create-player-knowledge",
                no_info.get("status") == "INTERACTION_EXECUTED"
                and (no_info.get("knowledge_acquisition") or {}).get("status") == "NO_SHARED_FACT_IN_NEW_CONVERSATION"
                and find_knowledge_fact(actor, TEST_FACT_ID) is None,
                f"acquisition={(no_info.get('knowledge_acquisition') or {}).get('status')}",
            )
            mara_levels[TEST_KNOWLEDGE_KEY] = 1
            mara.db.knowledge = mara_levels

            greeting = handle_action_proposal_result_v80(actor, _accepted_result(talk_cap, 1.0), raw_player_input="me acerco a Mara para intercambiar unas palabras", emit_messages=False)
            check(
                "topicless-greeting-does-not-create-player-fact",
                greeting.get("status") == "INTERACTION_EXECUTED"
                and (greeting.get("knowledge_acquisition") or {}).get("status") == "NO_SHARED_FACT_IN_NEW_CONVERSATION",
                f"acquisition={(greeting.get('knowledge_acquisition') or {}).get('status')}",
            )

            inform_route = handle_action_proposal_result_v80(actor, _accepted_result(talk_cap, 1.0), raw_player_input=INFORM_PHRASE, emit_messages=False)
            check(
                "v080-keeps-player-to-npc-inform-owned-by-v079",
                str(inform_route.get("build") or "") != NATURAL_CONVERSATION_ACQUISITION_BUILD,
                f"status={inform_route.get('status')} build={inform_route.get('build')}",
            )

            semantic_search = classify_v741_input(actor, "me pongo a escudriñar detrás del mostrador por si hay algo escondido")
            check("v080-preserves-perception-routing", semantic_search.get("route") == "AI_ACTION_PROPOSAL", f"route={semantic_search.get('route')}")

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_result = handle_action_proposal_result_v80(actor, _accepted_result(analyze_cap, 1.0), emit_messages=False)
            check(
                "v080-preserves-object-action-execution",
                object_result.get("status") == "WORLD_ENGINE_ACCEPTED"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_result.get('status')}",
            )
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)

            movement = handle_action_proposal_result_v80(actor, _accepted_result(movement_cap, 1.0), emit_messages=False)
            check(
                "v080-preserves-real-exit-movement",
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
            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.memories = original_actor_memories
            actor.db.relationships = original_actor_relationships
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            manifest.db.state = original_manifest_state
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor/Mara location, Knowledge/Facts, social state, action histories, manifest and consequence registry restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: interaction engine decides what was said; transfer engine alone persists the exact shared Fact; qwen never receives or authors Knowledge")
        self.caller.msg("========================================================")
