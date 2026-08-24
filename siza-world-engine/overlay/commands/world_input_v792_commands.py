import json

from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v78_commands import DETERMINISTIC_SEARCH_PHRASE
from commands.world_input_v79_commands import (
    INFORM_PHRASE,
    TEST_KNOWLEDGE_FACT_ID,
    TEST_KNOWLEDGE_KEY,
    _accepted_result,
    _projectable_fact,
    handle_action_proposal_result_v79,
)
from services.action_resolution_engine import action_resolution_history
from services.active_perception_proposal_runtime import build_active_perception_proposal_request
from services.consequence_engine import get_consequence_registry
from services.deterministic_active_perception_engine import execute_deterministic_active_perception
from services.knowledge_context_engine import fact_knowledge_state
from services.knowledge_fact_engine import find_knowledge_fact
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V0792_VALIDATION_BUILD = "0.79.2-targeted-saver-serialization-regression"
MODEL_REASON_SENTINEL = "V0792_MODEL_REASON_MUST_NEVER_PERSIST"


class CmdSizaValidateV792(Command):
    key = "siza-validate-v792"
    aliases = ["validate-v792"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.79.2 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.79.2 | {V0792_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted rerun after v0.79.1 production transfer passed: plain-state serialization, reason isolation, idempotency and pending regressions"
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
                item for item in list(original_discovered or [])
                if "V079-PESCADERIA-ROZADURA" not in str(item)
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

            registry.db.processed_action_ids = [
                row for row in list(original_processed or [])
                if TEST_KNOWLEDGE_FACT_ID not in str(row)
            ]
            registry.db.action_log = [
                row for row in list(original_log or [])
                if TEST_KNOWLEDGE_FACT_ID not in str((row or {}).get("action_id") if hasattr(row, "get") else row)
            ]

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state
            site.db.perception_facts = [_projectable_fact()]

            discovery = execute_deterministic_active_perception(actor, DETERMINISTIC_SEARCH_PHRASE)
            source_fact = find_knowledge_fact(actor, TEST_KNOWLEDGE_FACT_ID)
            check(
                "targeted-fixture-uses-real-perception-to-create-known-source-fact",
                discovery.get("status") == "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED"
                and discovery.get("engine_status") == "DISCOVERY"
                and source_fact is not None
                and fact_knowledge_state(actor, source_fact).get("known") is True,
                f"engine={discovery.get('engine_status')}",
            )

            request = build_active_perception_proposal_request(actor, INFORM_PHRASE)
            catalog = list(request.get("catalog") or [])
            talk_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "INTERACTION"
                    and int(row.get("target_dbref") or 0) == int(mara.id)
                ),
                None,
            )
            analyze_cap = next(
                (row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID),
                None,
            )
            movement_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "MOVEMENT"
                    and str(row.get("label") or "") == "salir a la calle"
                ),
                None,
            )
            if not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required targeted v0.79.2 capabilities missing")

            transfer = handle_action_proposal_result_v79(
                actor,
                _accepted_result(talk_cap, 1.0, MODEL_REASON_SENTINEL),
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
            )
            target_fact = find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID)
            target_state = fact_knowledge_state(mara, target_fact or {})
            check(
                "targeted-transfer-recreates-authoritative-known-fact-state",
                transfer.get("status") == "FACT_INFORM_EXECUTED"
                and (transfer.get("transfer") or {}).get("reason") == "FACT_TRANSFERRED"
                and target_fact is not None
                and target_state.get("known") is True,
                f"handler={transfer.get('status')} reason={(transfer.get('transfer') or {}).get('reason')}",
            )

            plain_snapshot = _clone(
                {
                    "actor_fact": find_knowledge_fact(actor, TEST_KNOWLEDGE_FACT_ID),
                    "target_fact": target_fact,
                    "target_knowledge": getattr(mara.db, "knowledge", {}),
                }
            )
            serialized = json.dumps(plain_snapshot, ensure_ascii=False, sort_keys=True)
            check(
                "evennia-saver-state-is-cloned-before-json-serialization-and-model-reason-is-absent",
                bool(serialized)
                and MODEL_REASON_SENTINEL not in serialized
                and TEST_KNOWLEDGE_FACT_ID in serialized,
                f"bytes={len(serialized.encode('utf-8'))} reason_persisted={MODEL_REASON_SENTINEL in serialized}",
            )

            target_before_repeat = _clone(find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID))
            processed_before_repeat = _clone(getattr(registry.db, "processed_action_ids", []))
            repeated = handle_action_proposal_result_v79(
                actor,
                _accepted_result(talk_cap, 1.0, MODEL_REASON_SENTINEL),
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
            )
            check(
                "repeat-natural-inform-remains-idempotent-without-second-world-action",
                repeated.get("status") == "FACT_INFORM_EXECUTED"
                and (repeated.get("transfer") or {}).get("reason") == "ALREADY_TRANSFERRED"
                and _clone(find_knowledge_fact(mara, TEST_KNOWLEDGE_FACT_ID)) == target_before_repeat
                and _clone(getattr(registry.db, "processed_action_ids", [])) == processed_before_repeat,
                f"reason={(repeated.get('transfer') or {}).get('reason')}",
            )

            semantic_search = classify_v741_input(
                actor,
                "me pongo a escudriñar detrás del mostrador por si hay algo escondido",
            )
            deterministic_search = classify_v741_input(actor, DETERMINISTIC_SEARCH_PHRASE)
            check(
                "v0792-preserves-semantic-and-deterministic-perception-routing",
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
                "v0792-preserves-normal-structured-interaction",
                greeting.get("status") == "INTERACTION_EXECUTED"
                and greeting.get("executed") is True,
                f"status={greeting.get('status')}",
            )
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_result = handle_action_proposal_result_v79(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v0792-preserves-object-action-execution",
                object_result.get("status") == "WORLD_ENGINE_ACCEPTED"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_result.get('status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement = handle_action_proposal_result_v79(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v0792-preserves-real-exit-movement",
                movement.get("status") == "MOVEMENT_EXECUTED"
                and movement.get("executed") is True
                and actor.location != site,
                f"status={movement.get('status')} location={actor.location.key if actor.location else None}",
            )

        except Exception as exc:
            check("targeted-validator-runtime", False, f"error={exc}")
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
            "PERSISTENT SYSTEM RETAINED: v0.79.1 production INFORM remains unchanged; targeted QA only verifies serializer-safe inspection plus remaining regressions"
        )
        self.caller.msg("========================================================")
