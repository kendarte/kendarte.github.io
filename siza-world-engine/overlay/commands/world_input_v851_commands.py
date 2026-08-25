import json

from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v83_commands import classify_v83_input
from commands.world_input_v85_commands import (
    EXPLICIT_SECRET_PHRASE,
    NATURAL_STATE_DISCLOSURE_BUILD,
    SECRET_FACT_ID,
    SECRET_KNOWLEDGE_KEY,
    SECRET_TEXT,
    SECRET_TOPIC,
    SEMANTIC_SECRET_PHRASE,
    handle_action_proposal_result_v85,
)
from services.action_proposal_async_runtime import call_prebuilt_action_proposal
from services.action_resolution_engine import set_adventure_stat
from services.active_perception_proposal_runtime import build_active_perception_proposal_request
from services.consequence_engine import get_consequence_registry
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.npc_fact_disclosure_state_engine import (
    NPC_FACT_DISCLOSURE_STATE_BUILD,
    evaluate_fact_disclosure_v85,
    preflight_talk_disclosure_v85,
    resolve_interaction_with_disclosure_and_acquisition_v85,
)
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import resolve_pending_object_action_roll
from world.upgrade_pilot_v54 import (
    CONFRONTED_FIELD,
    TARGET_STAT,
    WORLD_CONFRONTED_FIELD,
    ensure_v54_pilot_content,
)


V0851_VALIDATION_BUILD = "0.85.1-holder-local-disclosure-confrontation-regression"
POLICY_SENTINEL = "V0851_POLICY_MUST_NEVER_TRANSFER_OR_REACH_QWEN"
BAD_FACT_ID = "KFACT-V0851-MALFORMED-POLICY"


class CmdSizaValidateV851(Command):
    key = "siza-validate-v851"
    aliases = ["validate-v851"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v54_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.85.1 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        target = install.get("target")
        registry = get_consequence_registry(create=True)
        if not site or not target or not registry:
            self.caller.msg("[V0.85.1 VALIDATION] FAIL | target/site/registry missing")
            return

        original_actor_location = actor.location
        original_target_location = target.location
        original_actor_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_target_stats = _clone(getattr(target.db, "adventure_stats", {}))
        original_actor_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_actor_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_actor_memories = _clone(getattr(actor.db, "memories", []))
        original_actor_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_target_knowledge = _clone(getattr(target.db, "knowledge", {}))
        original_target_facts = _clone(getattr(target.db, "knowledge_facts", []))
        original_target_memories = _clone(getattr(target.db, "memories", []))
        original_target_relationships = _clone(getattr(target.db, "relationships", {}))
        original_target_state = _clone(getattr(target.db, "state", {}))
        original_target_policies = _clone(getattr(target.db, "fact_disclosure_policies", {}))
        original_actor_policies = _clone(getattr(actor.db, "fact_disclosure_policies", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        def set_confronted(value):
            state = _clone(getattr(target.db, "state", {}))
            if not isinstance(state, dict):
                state = {}
            state[CONFRONTED_FIELD] = bool(value)
            target.db.state = state

        def reset_actor_secret():
            actor.db.knowledge = {
                str(key): value for key, value in dict(original_actor_knowledge or {}).items()
                if str(key) != SECRET_KNOWLEDGE_KEY
            }
            actor.db.knowledge_facts = [
                row for row in list(original_actor_facts or [])
                if str((row or {}).get("id") or "") != SECRET_FACT_ID
            ]

        self.caller.msg(f"=== SIZA VALIDATION v0.85.1 | {V0851_VALIDATION_BUILD} ===")
        self.caller.msg(
            "holder-local disclosure policy -> blocked TALK -> real CONFRONT failure remains blocked -> real ACTOR_WIN state unlock -> clean transferable Fact"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if target.location != site:
                target.move_to(site, quiet=True)

            reset_actor_secret()
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            actor.db.object_action_history = []
            actor.db.action_resolution_history = []
            actor.db.fact_disclosure_policies = _clone(original_actor_policies)

            target.db.knowledge = {SECRET_KNOWLEDGE_KEY: 1}
            target.db.knowledge_facts = []
            target.db.memories = _clone(original_target_memories)
            target.db.relationships = {
                f"DBREF:{int(actor.id)}": {
                    "target_type": "CHARACTER",
                    "target_dbref": int(actor.id),
                    "target_name": actor.key,
                    "familiarity": 0,
                }
            }
            target.db.fact_disclosure_policies = {
                SECRET_FACT_ID: {
                    "npc_state_requirements": [
                        {
                            "field": CONFRONTED_FIELD,
                            "op": "EQ",
                            "value": True,
                            "name": "Informante cedió a la presión",
                        }
                    ]
                },
                POLICY_SENTINEL: {"min_familiarity": 999},
            }
            set_adventure_stat(actor, "PSI", 4)
            set_adventure_stat(target, TARGET_STAT, 4)
            set_confronted(False)

            world_state = _clone(getattr(site.db, "world_state", {}))
            if not isinstance(world_state, dict):
                world_state = {}
            world_state.pop(WORLD_CONFRONTED_FIELD, None)
            site.db.world_state = world_state
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            secret_fact = {
                "id": SECRET_FACT_ID,
                "topic": SECRET_TOPIC,
                "aliases": ["sello blanco", "auditoria", "inventario nocturno"],
                "text": SECRET_TEXT,
                "knowledge_key": SECRET_KNOWLEDGE_KEY,
                "required_level": 1,
                "canon_status": "prototype",
                "source": {"kind": "V0851_VALIDATOR_EVIDENCE"},
                "learned_by": {"provider": "V0851_VALIDATOR"},
            }
            upsert_knowledge_fact(target, secret_fact)
            set_knowledge_level(target, SECRET_KNOWLEDGE_KEY, 1)

            stored_source = find_knowledge_fact(target, SECRET_FACT_ID)
            check(
                "disclosure-policy-is-holder-local-and-not-part-of-transferable-fact",
                stored_source is not None
                and "disclosure" not in stored_source
                and SECRET_FACT_ID in dict(getattr(target.db, "fact_disclosure_policies", {}) or {})
                and evaluate_fact_disclosure_v85(target, actor, stored_source).get("policy_source") == "NPC_LOCAL_POLICY",
                f"fact_has_disclosure={'disclosure' in (stored_source or {})}",
            )

            public_gate = evaluate_fact_disclosure_v85(target, actor, {"id": "V0851-PUBLIC", "text": "Dato público."})
            inline_compat = evaluate_fact_disclosure_v85(
                target,
                actor,
                {"id": "V0851-INLINE", "disclosure": {"min_familiarity": 1}},
            )
            check(
                "public-default-and-v084-inline-familiarity-compatibility-are-preserved",
                public_gate.get("status") == "DISCLOSURE_PUBLIC"
                and public_gate.get("allowed") is True
                and inline_compat.get("allowed") is False
                and inline_compat.get("policy_source") == "LEGACY_INLINE_FACT"
                and any(row.get("kind") == "FAMILIARITY" for row in inline_compat.get("blockers") or []),
                f"public={public_gate.get('status')} legacy={inline_compat.get('status')}",
            )

            policies = dict(getattr(target.db, "fact_disclosure_policies", {}) or {})
            policies[BAD_FACT_ID] = {"npc_state_requirements": [{"field": "", "op": "EQ", "value": True}]}
            target.db.fact_disclosure_policies = policies
            malformed = evaluate_fact_disclosure_v85(target, actor, {"id": BAD_FACT_ID, "text": "No debe salir."})
            check(
                "malformed-holder-local-state-policy-fails-closed",
                malformed.get("allowed") is False
                and malformed.get("status") == "DISCLOSURE_MALFORMED_BLOCKED",
                f"status={malformed.get('status')}",
            )

            before_block = _clone(
                {
                    "actor_knowledge": getattr(actor.db, "knowledge", {}),
                    "actor_facts": getattr(actor.db, "knowledge_facts", []),
                    "actor_memories": getattr(actor.db, "memories", []),
                    "actor_relationships": getattr(actor.db, "relationships", {}),
                    "target_memories": getattr(target.db, "memories", []),
                    "target_relationships": getattr(target.db, "relationships", {}),
                    "processed": getattr(registry.db, "processed_action_ids", []),
                    "log": getattr(registry.db, "action_log", []),
                }
            )
            initial_preflight = preflight_talk_disclosure_v85(actor, EXPLICIT_SECRET_PHRASE)
            blocked_explicit = resolve_interaction_with_disclosure_and_acquisition_v85(
                actor,
                parse_interaction_intent(EXPLICIT_SECRET_PHRASE),
            )
            after_block = _clone(
                {
                    "actor_knowledge": getattr(actor.db, "knowledge", {}),
                    "actor_facts": getattr(actor.db, "knowledge_facts", []),
                    "actor_memories": getattr(actor.db, "memories", []),
                    "actor_relationships": getattr(actor.db, "relationships", {}),
                    "target_memories": getattr(target.db, "memories", []),
                    "target_relationships": getattr(target.db, "relationships", {}),
                    "processed": getattr(registry.db, "processed_action_ids", []),
                    "log": getattr(registry.db, "action_log", []),
                }
            )
            check(
                "explicit-talk-is-blocked-by-holder-state-before-memory-transfer-or-secret-text",
                initial_preflight.get("allowed") is False
                and any(row.get("kind") == "NPC_STATE" for row in initial_preflight.get("blockers") or [])
                and SECRET_TEXT not in str(initial_preflight.get("response_text") or "")
                and (blocked_explicit.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None
                and before_block == after_block,
                f"status={initial_preflight.get('status')}",
            )

            request = build_active_perception_proposal_request(actor, SEMANTIC_SECRET_PHRASE)
            provider_blob = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            catalog = list(request.get("catalog") or [])
            talk_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "INTERACTION"
                    and int(row.get("target_dbref") or 0) == int(target.id)
                ),
                None,
            )
            check(
                "qwen-boundary-excludes-holder-policy-secret-fact-and-confront-state",
                talk_cap is not None
                and SECRET_TEXT not in provider_blob
                and SECRET_FACT_ID not in provider_blob
                and CONFRONTED_FIELD not in provider_blob
                and "fact_disclosure_policies" not in provider_blob
                and POLICY_SENTINEL not in provider_blob,
                f"talk={(talk_cap or {}).get('capability_id')}",
            )
            if not talk_cap:
                raise RuntimeError("Informante TALK capability missing")

            self.caller.msg(f"LIVE V0851 TARGET PROBE: action={SEMANTIC_SECRET_PHRASE!r}")
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-visible-informant-without-policy-authority",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and str((live.get("proposal") or {}).get("capability_id") or "") == str(talk_cap.get("capability_id") or ""),
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            rendered = {}

            def fake_renderer(current_actor, npc_name, topic, fact_text, **kwargs):
                rendered.update({"called": True, "npc": npc_name, "topic": topic, "fact_text": fact_text})
                return {"status": "STYLED_DIALOGUE_RENDER_QUEUED", "queued": True}

            blocked_live = handle_action_proposal_result_v85(
                actor,
                live,
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "live-qwen-target-selection-cannot-override-holder-local-state-gate",
                (blocked_live.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and not rendered.get("called")
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None,
                f"acquisition={(blocked_live.get('knowledge_acquisition') or {}).get('status')}",
            )

            pending_loss = route_object_action_input(actor, "presionar informante", attempt_id="V0851-TARGET-WIN")
            loss = resolve_pending_object_action_roll(
                actor,
                attempt_id="V0851-TARGET-WIN",
                forced_roll=1,
                forced_target_roll=6,
            )
            after_loss = preflight_talk_disclosure_v85(actor, EXPLICIT_SECRET_PHRASE)
            check(
                "failed-real-confrontation-leaves-holder-policy-blocked",
                pending_loss.get("status") == "PENDING_RESOLUTION"
                and loss.get("status") == "RESOLVED"
                and loss.get("outcome") == "TARGET_WIN"
                and bool((_clone(getattr(target.db, "state", {})) or {}).get(CONFRONTED_FIELD)) is False
                and after_loss.get("allowed") is False,
                f"outcome={loss.get('outcome')} disclosure={after_loss.get('status')}",
            )

            pending_win = route_object_action_input(actor, "presionar informante", attempt_id="V0851-ACTOR-WIN")
            win = resolve_pending_object_action_roll(
                actor,
                attempt_id="V0851-ACTOR-WIN",
                forced_roll=6,
                forced_target_roll=1,
            )
            target_state = _clone(getattr(target.db, "state", {}))
            world_state = _clone(getattr(site.db, "world_state", {}))
            check(
                "actor-win-real-confrontation-mutates-the-existing-authoritative-state",
                pending_win.get("status") == "PENDING_RESOLUTION"
                and win.get("status") == "RESOLVED"
                and win.get("outcome") == "ACTOR_WIN"
                and bool((target_state or {}).get(CONFRONTED_FIELD)) is True
                and (world_state or {}).get(WORLD_CONFRONTED_FIELD) == 1,
                f"outcome={win.get('outcome')} npc_state={(target_state or {}).get(CONFRONTED_FIELD)}",
            )

            unlocked = preflight_talk_disclosure_v85(actor, EXPLICIT_SECRET_PHRASE)
            check(
                "existing-consequence-state-now-satisfies-the-holder-local-disclosure-requirement",
                unlocked.get("allowed") is True
                and unlocked.get("status") == "DISCLOSURE_ALLOWED"
                and unlocked.get("policy_source") == "NPC_LOCAL_POLICY"
                and all(row.get("met") is True for row in unlocked.get("state_checks") or []),
                f"status={unlocked.get('status')} checks={unlocked.get('state_checks')}",
            )

            rendered.clear()
            unlocked_live = handle_action_proposal_result_v85(
                actor,
                live,
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            acquired = find_knowledge_fact(actor, SECRET_FACT_ID)
            acquired_blob = json.dumps(_clone(acquired or {}), ensure_ascii=False)
            actor_policy_blob = json.dumps(_clone(getattr(actor.db, "fact_disclosure_policies", {})), ensure_ascii=False)
            check(
                "unlocked-semantic-talk-transfers-clean-fact-and-renders-without-transferring-holder-policy",
                unlocked_live.get("status") == "INTERACTION_EXECUTED"
                and (unlocked_live.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and rendered.get("called") is True
                and rendered.get("fact_text") == SECRET_TEXT
                and "disclosure" not in (acquired or {})
                and CONFRONTED_FIELD not in acquired_blob
                and "npc_state_requirements" not in acquired_blob
                and POLICY_SENTINEL not in acquired_blob
                and POLICY_SENTINEL not in actor_policy_blob,
                f"acquisition={(unlocked_live.get('knowledge_acquisition') or {}).get('status')} clean={'disclosure' not in (acquired or {})}",
            )

            knowledge_route = classify_v83_input(actor, "¿Qué sé sobre sello blanco de auditoria?")
            perception_route = classify_v83_input(actor, "observo al Informante de Prueba C")
            movement_route = classify_v83_input(actor, "salir a la calle")
            check(
                "knowledge-perception-and-movement-routing-remain-outside-v085-disclosure-authority",
                knowledge_route.get("route") == "KNOWLEDGE_QUERY"
                and perception_route.get("route") == "PERCEPTION"
                and movement_route.get("route") == "MOVEMENT",
                f"knowledge={knowledge_route.get('route')} perception={perception_route.get('route')} movement={movement_route.get('route')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_actor_location:
                    actor.move_to(original_actor_location, quiet=True)
            except Exception:
                pass
            try:
                if target.location != original_target_location:
                    target.move_to(original_target_location, quiet=True)
            except Exception:
                pass
            actor.db.adventure_stats = original_actor_stats
            target.db.adventure_stats = original_target_stats
            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.memories = original_actor_memories
            actor.db.relationships = original_actor_relationships
            actor.db.fact_disclosure_policies = original_actor_policies
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            target.db.knowledge = original_target_knowledge
            target.db.knowledge_facts = original_target_facts
            target.db.memories = original_target_memories
            target.db.relationships = original_target_relationships
            target.db.state = original_target_state
            target.db.fact_disclosure_policies = original_target_policies
            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    site.db.world_state = None
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Informant location, stats, Knowledge/Facts, holder policies, social state, histories, NPC/room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.54 CONFRONT owns the state mutation; v0.85 holder-local disclosure consumes that state; the transferable Fact carries no disclosure policy"
        )
        self.caller.msg("========================================================")
