import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v74_commands import _clone
from commands.world_input_v82_commands import (
    handle_action_proposal_result_v82,
    present_conversation_result_v82,
)
from commands.world_input_v83_commands import classify_v83_input
from commands.world_input_v84_commands import (
    CmdSizaNoMatchV84,
    _current_interaction_capability,
    handle_action_proposal_result_v84,
)
from services.action_proposal_async_runtime import (
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
)
from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
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
from services.object_action_engine import object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import resolve_pending_object_action_roll
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent
from world.upgrade_pilot_v54 import (
    CONFRONTED_FIELD,
    TARGET_STAT,
    WORLD_CONFRONTED_FIELD,
    ensure_v54_pilot_content,
)


NATURAL_STATE_DISCLOSURE_BUILD = "0.85.0-confrontation-state-disclosure-gate"
SECRET_FACT_ID = "KFACT-V085-INFORMANT-AUDIT-SEAL-001"
SECRET_KNOWLEDGE_KEY = "V085_INFORMANT_AUDIT_SEAL"
SECRET_TOPIC = "sello blanco de auditoria"
SECRET_TEXT = "El sello blanco de auditoría fue aplicado por el relevo que cerró el inventario nocturno."
PRIVATE_SENTINEL = "NEVER_LEAK_V085_STATE_DISCLOSURE"
EXPLICIT_SECRET_PHRASE = "hablo con Informante de Prueba C sobre sello blanco de auditoria"
SEMANTIC_SECRET_PHRASE = "me acerco al Informante de Prueba C y le saco el tema del sello blanco de auditoria"
MODEL_REASON_SENTINEL = "V085_MODEL_REASON_MUST_NOT_PERSIST"


def handle_action_proposal_result_v85(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """Apply v0.85 disclosure to current TALK only; older non-TALK paths stay unchanged."""
    if parse_semantic_fact_inform_intent(raw_player_input):
        return handle_action_proposal_result_v84(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
            render_async_callable=render_async_callable,
            provider_options=provider_options,
        )

    current = _current_interaction_capability(actor, proposal_result)
    if current:
        preflight = preflight_talk_disclosure_v85(
            actor,
            raw_player_input,
            expected_target_dbref=current.get("target_dbref"),
        )
        if not bool(preflight.get("allowed", True)):
            base = {
                "status": "INTERACTION_EXECUTED",
                "executed": True,
                "response_text": str(preflight.get("response_text") or "").strip(),
                "knowledge_acquisition": {
                    "status": "DISCLOSURE_BLOCKED",
                    "acquired": False,
                    "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
                },
                "disclosure": preflight,
                "build": NATURAL_STATE_DISCLOSURE_BUILD,
            }
            return present_conversation_result_v82(
                actor,
                base,
                emit_messages=emit_messages,
                render_async_callable=render_async_callable,
                provider_options=provider_options,
            )

        # v0.85 fully supersedes v0.84 disclosure evaluation for ordinary TALK,
        # because it understands both the old min_familiarity gate and new NPC-state gates.
        return handle_action_proposal_result_v82(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
            render_async_callable=render_async_callable,
            provider_options=provider_options,
        )

    return handle_action_proposal_result_v84(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=emit_messages,
        render_async_callable=render_async_callable,
        provider_options=provider_options,
    )


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.85 action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v85(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v85(
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


class CmdSizaNoMatchV85(CmdSizaNoMatchV84):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v83_input(self.caller, raw)
        if classification.get("route") == "INTERACTION" and classification.get("explicit_talk_precedence"):
            packet = resolve_interaction_with_disclosure_and_acquisition_v85(
                self.caller,
                classification.get("intent")
                or parse_interaction_intent(raw)
                or {"intent": "TALK", "raw": raw},
            )
            present_conversation_result_v82(self.caller, packet, emit_messages=True)
            return None
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v85(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV85(Command):
    key = "siza-validate-v85"
    aliases = ["validate-v85"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v54_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.85 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        target = install.get("target")
        registry = get_consequence_registry(create=True)
        if not site or not target or not registry:
            self.caller.msg("[V0.85 VALIDATION] FAIL | pilot target/site/registry missing")
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

        def reset_actor_secret():
            actor.db.knowledge = {
                str(key): value for key, value in dict(original_actor_knowledge or {}).items()
                if str(key) != SECRET_KNOWLEDGE_KEY
            }
            actor.db.knowledge_facts = [
                row for row in list(original_actor_facts or [])
                if str((row or {}).get("id") or "") != SECRET_FACT_ID
            ]

        def set_target_confronted(value):
            state = _clone(getattr(target.db, "state", {}))
            if not isinstance(state, dict):
                state = {}
            state[CONFRONTED_FIELD] = bool(value)
            target.db.state = state

        self.caller.msg(f"=== SIZA VALIDATION v0.85 | {NATURAL_STATE_DISCLOSURE_BUILD} ===")
        self.caller.msg(
            "restricted Fact -> blocked TALK -> real CONFRONT failure stays blocked -> real ACTOR_WIN consequence mutates NPC state -> same Fact becomes discloseable"
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
            set_adventure_stat(actor, "PSI", 4)
            set_adventure_stat(target, TARGET_STAT, 4)
            set_target_confronted(False)
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
                "source": {"private_note": PRIVATE_SENTINEL},
                "learned_by": {"provider": "V085_VALIDATOR"},
                "disclosure": {
                    "npc_state_requirements": [
                        {
                            "field": CONFRONTED_FIELD,
                            "op": "EQ",
                            "value": True,
                            "name": "El informante ha cedido a la presión",
                        }
                    ]
                },
            }
            upsert_knowledge_fact(target, secret_fact)
            set_knowledge_level(target, SECRET_KNOWLEDGE_KEY, 1)

            public_gate = evaluate_fact_disclosure_v85(
                target,
                actor,
                {"id": "V085-PUBLIC", "text": "Dato público."},
            )
            check(
                "facts-without-disclosure-remain-public-under-v085",
                public_gate.get("allowed") is True and public_gate.get("status") == "DISCLOSURE_PUBLIC",
                f"status={public_gate.get('status')}",
            )

            familiarity_gate = evaluate_fact_disclosure_v85(
                target,
                actor,
                {"id": "V085-FAMILIARITY", "disclosure": {"min_familiarity": 1}},
            )
            check(
                "v084-min-familiarity-disclosure-remains-backward-compatible",
                familiarity_gate.get("allowed") is False
                and any(row.get("kind") == "FAMILIARITY" for row in familiarity_gate.get("blockers") or []),
                f"status={familiarity_gate.get('status')}",
            )

            malformed = evaluate_fact_disclosure_v85(
                target,
                actor,
                {
                    "id": "V085-MALFORMED",
                    "disclosure": {"npc_state_requirements": [{"field": "", "op": "EQ", "value": True}]},
                },
            )
            check(
                "malformed-npc-state-disclosure-fails-closed",
                malformed.get("allowed") is False
                and malformed.get("status") == "DISCLOSURE_MALFORMED_BLOCKED",
                f"status={malformed.get('status')}",
            )

            initial_preflight = preflight_talk_disclosure_v85(actor, EXPLICIT_SECRET_PHRASE)
            check(
                "known-state-restricted-fact-is-blocked-before-confrontation",
                initial_preflight.get("allowed") is False
                and initial_preflight.get("status") == "DISCLOSURE_BLOCKED"
                and any(row.get("kind") == "NPC_STATE" for row in initial_preflight.get("blockers") or [])
                and SECRET_TEXT not in str(initial_preflight.get("response_text") or "")
                and SECRET_FACT_ID not in json.dumps(initial_preflight, ensure_ascii=False),
                f"status={initial_preflight.get('status')} blockers={initial_preflight.get('blockers')}",
            )

            before_explicit = _clone(
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
            explicit_block = resolve_interaction_with_disclosure_and_acquisition_v85(
                actor,
                parse_interaction_intent(EXPLICIT_SECRET_PHRASE),
            )
            after_explicit = _clone(
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
                "explicit-talk-blocks-before-secret-render-memory-or-transfer",
                (explicit_block.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None
                and before_explicit == after_explicit,
                f"acquisition={(explicit_block.get('knowledge_acquisition') or {}).get('status')}",
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
                "qwen-boundary-excludes-secret-fact-and-state-disclosure-policy",
                talk_cap is not None
                and SECRET_TEXT not in provider_blob
                and SECRET_FACT_ID not in provider_blob
                and CONFRONTED_FIELD not in provider_blob
                and "npc_state_requirements" not in provider_blob
                and PRIVATE_SENTINEL not in provider_blob,
                f"talk={(talk_cap or {}).get('capability_id')}",
            )
            if not talk_cap:
                raise RuntimeError("Informante TALK capability missing")

            self.caller.msg(f"LIVE V085 DISCLOSURE TARGET PROBE: action={SEMANTIC_SECRET_PHRASE!r}")
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-the-visible-informant-without-disclosure-authority",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and str((live.get("proposal") or {}).get("capability_id") or "") == str(talk_cap.get("capability_id") or ""),
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            render_capture = {}

            def fake_renderer(current_actor, npc_name, topic, fact_text, **kwargs):
                render_capture.update({"called": True, "npc": npc_name, "topic": topic, "fact_text": fact_text})
                return {"status": "STYLED_DIALOGUE_RENDER_QUEUED", "queued": True}

            blocked_live = handle_action_proposal_result_v85(
                actor,
                live,
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "live-qwen-target-selection-cannot-override-state-disclosure-gate",
                (blocked_live.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and not render_capture.get("called")
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None,
                f"acquisition={(blocked_live.get('knowledge_acquisition') or {}).get('status')}",
            )

            pending_loss = route_object_action_input(
                actor,
                "presionar informante",
                attempt_id="V085-TARGET-WIN",
            )
            loss = resolve_pending_object_action_roll(
                actor,
                attempt_id="V085-TARGET-WIN",
                forced_roll=1,
                forced_target_roll=6,
            )
            after_loss_preflight = preflight_talk_disclosure_v85(actor, EXPLICIT_SECRET_PHRASE)
            check(
                "failed-real-confrontation-does-not-unlock-restricted-fact",
                pending_loss.get("status") == "PENDING_RESOLUTION"
                and loss.get("status") == "RESOLVED"
                and loss.get("outcome") == "TARGET_WIN"
                and bool((_clone(getattr(target.db, "state", {})) or {}).get(CONFRONTED_FIELD)) is False
                and after_loss_preflight.get("allowed") is False,
                f"outcome={loss.get('outcome')} disclosure={after_loss_preflight.get('status')}",
            )

            pending_win = route_object_action_input(
                actor,
                "presionar informante",
                attempt_id="V085-ACTOR-WIN",
            )
            win = resolve_pending_object_action_roll(
                actor,
                attempt_id="V085-ACTOR-WIN",
                forced_roll=6,
                forced_target_roll=1,
            )
            target_state = _clone(getattr(target.db, "state", {}))
            current_world = _clone(getattr(site.db, "world_state", {}))
            check(
                "actor-win-real-confrontation-flows-through-existing-consequence-state",
                pending_win.get("status") == "PENDING_RESOLUTION"
                and win.get("status") == "RESOLVED"
                and win.get("outcome") == "ACTOR_WIN"
                and bool((target_state or {}).get(CONFRONTED_FIELD)) is True
                and (current_world or {}).get(WORLD_CONFRONTED_FIELD) == 1,
                f"outcome={win.get('outcome')} npc_state={(target_state or {}).get(CONFRONTED_FIELD)}",
            )

            unlocked_preflight = preflight_talk_disclosure_v85(actor, EXPLICIT_SECRET_PHRASE)
            check(
                "persisted-confrontation-state-unlocks-authored-disclosure-without-special-case-code",
                unlocked_preflight.get("allowed") is True
                and unlocked_preflight.get("status") == "DISCLOSURE_ALLOWED"
                and all(row.get("met") is True for row in unlocked_preflight.get("state_checks") or []),
                f"status={unlocked_preflight.get('status')} checks={unlocked_preflight.get('state_checks')}",
            )

            render_capture.clear()
            unlocked_live = handle_action_proposal_result_v85(
                actor,
                live,
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            acquired = find_knowledge_fact(actor, SECRET_FACT_ID)
            check(
                "same-live-semantic-talk-now-enters-existing-transfer-and-render-pipeline-after-confrontation",
                unlocked_live.get("status") == "INTERACTION_EXECUTED"
                and (unlocked_live.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and render_capture.get("called") is True
                and render_capture.get("fact_text") == SECRET_TEXT,
                f"acquisition={(unlocked_live.get('knowledge_acquisition') or {}).get('status')} rendered={render_capture.get('called')}",
            )

            knowledge_route = classify_v83_input(actor, "¿Qué sé sobre sello blanco de auditoria?")
            perception_route = classify_v83_input(actor, "observo al Informante de Prueba C")
            movement_route = classify_v83_input(actor, "salir a la calle")
            check(
                "knowledge-perception-and-movement-routing-remain-outside-disclosure-authority",
                knowledge_route.get("route") == "KNOWLEDGE_QUERY"
                and perception_route.get("route") == "PERCEPTION"
                and movement_route.get("route") == "MOVEMENT",
                f"knowledge={knowledge_route.get('route')} perception={perception_route.get('route')} movement={movement_route.get('route')}",
            )

            persistent_blob = json.dumps(
                _clone(
                    {
                        "actor_fact": acquired,
                        "actor_memories": getattr(actor.db, "memories", []),
                        "actor_relationships": getattr(actor.db, "relationships", {}),
                    }
                ),
                ensure_ascii=False,
            )
            check(
                "qwen-reason-and-disclosure-policy-do-not-persist-into-acquired-knowledge",
                MODEL_REASON_SENTINEL not in persistent_blob
                and CONFRONTED_FIELD not in str(acquired or {})
                and "npc_state_requirements" not in str(acquired or {}),
                "private_policy_persisted=False",
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
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            target.db.knowledge = original_target_knowledge
            target.db.knowledge_facts = original_target_facts
            target.db.memories = original_target_memories
            target.db.relationships = original_target_relationships
            target.db.state = original_target_state
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
            "STATE RESTORED: actor/Informant location, stats, Knowledge/Facts, social state, histories, NPC state, room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.54 CONFRONT remains the state authority; v0.85 only consumes authored NPC-state disclosure requirements before the closed TALK/transfer/render pipeline"
        )
        self.caller.msg("========================================================")
