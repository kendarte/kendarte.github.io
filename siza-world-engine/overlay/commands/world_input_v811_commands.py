import json

from evennia import Command

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v81_commands import (
    TEST_FACT_ID,
    TEST_KNOWLEDGE_KEY,
    TEST_TEXT,
    TEST_TOPIC,
    handle_action_proposal_result_v81,
)
from services.action_proposal_async_runtime import call_prebuilt_action_proposal
from services.active_perception_proposal_runtime import build_active_perception_proposal_request
from services.consequence_engine import get_consequence_registry
from services.interaction_proposal_execution_bridge import extract_player_authored_topic
from services.knowledge_context_engine import fact_knowledge_state, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V0811_VALIDATION_BUILD = "0.81.1-targeted-semantic-dialogue-fixture"
SEMANTIC_DIALOGUE_FIXTURE = "me acerco a Mara y le saco el tema del sello del turno de madrugada"
MODEL_REASON_SENTINEL = "V0811_TARGET_SELECTION_REASON_MUST_NOT_PERSIST"


class CmdSizaValidateV811(Command):
    key = "siza-validate-v811"
    aliases = ["validate-v811"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.81.1 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
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
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.81.1 | {V0811_VALIDATION_BUILD} ===")
        self.caller.msg("targeted rerun: real semantic fallback phrase -> qwen chooses TALK target -> player-authored topic -> authoritative transfer -> presentation renderer")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            actor.db.knowledge = {
                str(k): v for k, v in dict(original_actor_knowledge or {}).items()
                if str(k) != TEST_KNOWLEDGE_KEY
            }
            actor.db.knowledge_facts = [
                row for row in list(original_actor_facts or [])
                if str((row or {}).get("id") or "") != TEST_FACT_ID
            ]
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
                    "source": {"validator": "v0.81.1"},
                    "learned_by": {"provider": "V0811_VALIDATOR"},
                },
            )
            set_knowledge_level(mara, TEST_KNOWLEDGE_KEY, 1)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            classification = classify_v741_input(actor, SEMANTIC_DIALOGUE_FIXTURE)
            extracted_topic = extract_player_authored_topic(SEMANTIC_DIALOGUE_FIXTURE)
            check(
                "semantic-dialogue-fixture-really-enters-ai-fallback-with-player-authored-topic",
                classification.get("route") == "AI_ACTION_PROPOSAL"
                and classification.get("ai_allowed") is True
                and extracted_topic == TEST_TOPIC,
                f"route={classification.get('route')} topic={extracted_topic!r}",
            )

            request = build_active_perception_proposal_request(actor, SEMANTIC_DIALOGUE_FIXTURE)
            request_text = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            check(
                "semantic-target-selection-provider-boundary-still-excludes-npc-fact-state",
                TEST_FACT_ID not in request_text
                and TEST_KNOWLEDGE_KEY not in request_text
                and TEST_TEXT not in request_text,
                f"fact_leaked={TEST_TEXT in request_text}",
            )

            self.caller.msg(f"LIVE V0811 SEMANTIC DIALOGUE TARGET PROBE: action={SEMANTIC_DIALOGUE_FIXTURE!r}")
            live = call_prebuilt_action_proposal(request, timeout=60)
            proposal = dict(live.get("proposal") or {})
            check(
                "live-qwen-selects-visible-mara-interaction-for-true-semantic-fixture",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and proposal.get("kind") == "INTERACTION"
                and str(proposal.get("capability_id") or "").startswith("TALK:")
                and str((live.get("capability") or {}).get("target_name") or "") == str(mara.key),
                f"status={live.get('status')} proposal={proposal}",
            )
            if not (live.get("status") == "ACCEPTED" and proposal.get("kind") == "INTERACTION"):
                raise RuntimeError("live semantic target selection did not produce INTERACTION")

            captured = {}

            def fake_renderer(current_actor, npc_name, topic, fact_text, *, fallback_text="", **kwargs):
                captured.update({
                    "actor": current_actor,
                    "npc_name": npc_name,
                    "topic": topic,
                    "fact_text": fact_text,
                    "fallback_text": fallback_text,
                })
                return {"status": "DIALOGUE_RENDER_QUEUED", "queued": True}

            live["proposal"] = {**proposal, "reason": MODEL_REASON_SENTINEL}
            handled = handle_action_proposal_result_v81(
                actor,
                live,
                raw_player_input=SEMANTIC_DIALOGUE_FIXTURE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            acquired = find_knowledge_fact(actor, TEST_FACT_ID)
            persistent_blob = json.dumps(
                _clone({
                    "fact": acquired,
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "registry_processed": getattr(registry.db, "processed_action_ids", []),
                    "registry_log": getattr(registry.db, "action_log", []),
                }),
                ensure_ascii=False,
            )
            check(
                "semantic-dialogue-transfers-exact-fact-before-render-and-never-persists-model-reason",
                handled.get("status") == "INTERACTION_EXECUTED"
                and (handled.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and fact_knowledge_state(actor, acquired).get("known") is True
                and acquired.get("text") == TEST_TEXT
                and captured.get("npc_name") == mara.key
                and captured.get("topic") == TEST_TOPIC
                and captured.get("fact_text") == TEST_TEXT
                and MODEL_REASON_SENTINEL not in persistent_blob,
                f"handler={handled.get('status')} acquisition={(handled.get('knowledge_acquisition') or {}).get('status')} queued={(handled.get('dialogue_render') or {}).get('queued')}",
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
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor/Mara location, Knowledge/Facts, social state and consequence registry restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: v0.81 production code unchanged; this validator only corrects the semantic test phrase used by v0.81 QA")
        self.caller.msg("========================================================")
