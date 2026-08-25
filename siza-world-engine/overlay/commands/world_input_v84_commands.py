import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v74_commands import _clone
from commands.world_input_v79_commands import INFORM_PHRASE, _accepted_result
from commands.world_input_v82_commands import (
    handle_action_proposal_result_v82,
    present_conversation_result_v82,
)
from commands.world_input_v83_commands import CmdSizaNoMatchV83, classify_v83_input
from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_proposal_async_runtime import (
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
)
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.action_resolution_engine import action_resolution_history
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.consequence_engine import get_consequence_registry
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import fact_knowledge_state, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.npc_fact_disclosure_engine import (
    NPC_FACT_DISCLOSURE_BUILD,
    evaluate_fact_disclosure,
    preflight_talk_disclosure,
    resolve_interaction_with_disclosure_and_acquisition,
)
from services.object_action_engine import object_action_history
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_FACT_DISCLOSURE_BUILD = "0.84.0-authored-npc-fact-disclosure-gate"
SEMANTIC_SECRET_PHRASE = "me acerco a Mara y le saco el tema del sello negro de inventario"
EXPLICIT_SECRET_PHRASE = "hablo con Mara sobre sello negro de inventario"
SECRET_FACT_ID = "KFACT-V084-MARA-SELLO-NEGRO-001"
SECRET_KNOWLEDGE_KEY = "V084_MARA_SELLO_NEGRO"
SECRET_TOPIC = "sello negro de inventario"
SECRET_TEXT = "El sello negro de inventario corresponde al cierre reservado del turno nocturno."
PRIVATE_SENTINEL = "NEVER_LEAK_V084_DISCLOSURE_PRIVATE_STATE"
MALFORMED_TOPIC = "sello opaco de inventario"
MALFORMED_FACT_ID = "KFACT-V084-MARA-MALFORMED-001"
MALFORMED_KNOWLEDGE_KEY = "V084_MARA_MALFORMED"
MODEL_REASON_SENTINEL = "V084_MODEL_REASON_MUST_NOT_PERSIST"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def _current_interaction_capability(actor, proposal_result):
    """Revalidate enough to decide whether disclosure preflight is applicable; execution stays in the old bridge."""
    packet = proposal_result if isinstance(proposal_result, dict) else {}
    if packet.get("status") != "ACCEPTED" or packet.get("accepted") is not True:
        return None
    proposal = dict(packet.get("proposal") or {})
    if str(proposal.get("kind") or "") != "INTERACTION":
        return None
    try:
        confidence = float(proposal.get("confidence"))
    except (TypeError, ValueError):
        return None
    if confidence < float(MIN_EXECUTION_CONFIDENCE):
        return None
    capability_id = str(proposal.get("capability_id") or "").strip()
    current = next(
        (
            row for row in build_local_capability_catalog(actor)
            if str(row.get("capability_id") or "") == capability_id
        ),
        None,
    )
    if not current or str(current.get("kind") or "") != "INTERACTION":
        return None
    return dict(current)


def handle_action_proposal_result_v84(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """Preflight only current ordinary TALK. INFORM and non-interaction routes remain owned by closed handlers."""
    if parse_semantic_fact_inform_intent(raw_player_input):
        return handle_action_proposal_result_v82(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
            render_async_callable=render_async_callable,
            provider_options=provider_options,
        )

    current = _current_interaction_capability(actor, proposal_result)
    if current:
        preflight = preflight_talk_disclosure(
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
                    "build": NPC_FACT_DISCLOSURE_BUILD,
                },
                "disclosure": preflight,
                "build": NATURAL_FACT_DISCLOSURE_BUILD,
            }
            return present_conversation_result_v82(
                actor,
                base,
                emit_messages=emit_messages,
                render_async_callable=render_async_callable,
                provider_options=provider_options,
            )

    return handle_action_proposal_result_v82(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=emit_messages,
        render_async_callable=render_async_callable,
        provider_options=provider_options,
    )


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.84 action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v84(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v84(
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


class CmdSizaNoMatchV84(CmdSizaNoMatchV83):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v83_input(self.caller, raw)
        if classification.get("route") == "INTERACTION" and classification.get("explicit_talk_precedence"):
            packet = resolve_interaction_with_disclosure_and_acquisition(
                self.caller,
                classification.get("intent")
                or parse_interaction_intent(raw)
                or {"intent": "TALK", "raw": raw},
            )
            present_conversation_result_v82(self.caller, packet, emit_messages=True)
            return None
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v84(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV84(Command):
    key = "siza-validate-v84"
    aliases = ["validate-v84"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.84 VALIDATION] FAIL | context={context}")
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

        def set_familiarity(value):
            mara.db.relationships = {
                f"DBREF:{int(actor.id)}": {
                    "target_type": "CHARACTER",
                    "target_dbref": int(actor.id),
                    "target_name": actor.key,
                    "familiarity": int(value),
                    "private_note": PRIVATE_SENTINEL,
                }
            }

        def reset_actor_secret_state():
            levels = {
                str(key): value for key, value in dict(original_actor_knowledge or {}).items()
                if str(key) != SECRET_KNOWLEDGE_KEY
            }
            actor.db.knowledge = levels
            actor.db.knowledge_facts = [
                row for row in list(original_actor_facts or [])
                if str((row or {}).get("id") or "") != SECRET_FACT_ID
            ]

        self.caller.msg(f"=== SIZA VALIDATION v0.84 | {NATURAL_FACT_DISCLOSURE_BUILD} ===")
        self.caller.msg(
            "NPC knows Fact != NPC will disclose Fact: authored min_familiarity preflight blocks before closed TALK/render/transfer"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            reset_actor_secret_state()
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara.db.knowledge = {SECRET_KNOWLEDGE_KEY: 1}
            mara.db.knowledge_facts = []
            mara.db.memories = _clone(original_mara_memories)
            set_familiarity(0)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            secret_fact = {
                "id": SECRET_FACT_ID,
                "topic": SECRET_TOPIC,
                "aliases": ["sello negro", "inventario negro"],
                "text": SECRET_TEXT,
                "knowledge_key": SECRET_KNOWLEDGE_KEY,
                "required_level": 1,
                "canon_status": "prototype",
                "source": {"private_note": PRIVATE_SENTINEL},
                "learned_by": {"provider": "V084_VALIDATOR"},
                "disclosure": {"min_familiarity": 3},
            }
            upsert_knowledge_fact(mara, secret_fact)
            set_knowledge_level(mara, SECRET_KNOWLEDGE_KEY, 1)

            public_gate = evaluate_fact_disclosure(
                mara,
                actor,
                {
                    "id": "V084-PUBLIC-FIXTURE",
                    "topic": "dato público",
                    "text": "Dato público.",
                    "knowledge_key": "V084_PUBLIC",
                    "required_level": 1,
                },
            )
            check(
                "facts-without-disclosure-block-remain-public-by-default",
                public_gate.get("allowed") is True
                and public_gate.get("status") == "DISCLOSURE_PUBLIC",
                f"status={public_gate.get('status')}",
            )

            low_preflight = preflight_talk_disclosure(actor, EXPLICIT_SECRET_PHRASE)
            check(
                "known-restricted-fact-is-withheld-when-familiarity-is-below-authored-minimum",
                low_preflight.get("allowed") is False
                and low_preflight.get("status") == "DISCLOSURE_BLOCKED"
                and low_preflight.get("familiarity") == 0
                and low_preflight.get("required_familiarity") == 3
                and SECRET_TEXT not in str(low_preflight.get("response_text") or "")
                and SECRET_FACT_ID not in json.dumps(low_preflight, ensure_ascii=False),
                f"status={low_preflight.get('status')} familiarity={low_preflight.get('familiarity')}",
            )

            before_blocked = _clone(
                {
                    "actor_knowledge": getattr(actor.db, "knowledge", {}),
                    "actor_facts": getattr(actor.db, "knowledge_facts", []),
                    "actor_memories": getattr(actor.db, "memories", []),
                    "actor_relationships": getattr(actor.db, "relationships", {}),
                    "mara_memories": getattr(mara.db, "memories", []),
                    "mara_relationships": getattr(mara.db, "relationships", {}),
                    "processed": getattr(registry.db, "processed_action_ids", []),
                    "log": getattr(registry.db, "action_log", []),
                }
            )
            blocked_explicit = resolve_interaction_with_disclosure_and_acquisition(
                actor,
                parse_interaction_intent(EXPLICIT_SECRET_PHRASE),
            )
            after_blocked = _clone(
                {
                    "actor_knowledge": getattr(actor.db, "knowledge", {}),
                    "actor_facts": getattr(actor.db, "knowledge_facts", []),
                    "actor_memories": getattr(actor.db, "memories", []),
                    "actor_relationships": getattr(actor.db, "relationships", {}),
                    "mara_memories": getattr(mara.db, "memories", []),
                    "mara_relationships": getattr(mara.db, "relationships", {}),
                    "processed": getattr(registry.db, "processed_action_ids", []),
                    "log": getattr(registry.db, "action_log", []),
                }
            )
            check(
                "explicit-talk-is-blocked-before-memory-relationship-transfer-or-secret-rendering",
                blocked_explicit.get("status") == "INTERACTION_EXECUTED"
                and (blocked_explicit.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and SECRET_TEXT not in str(blocked_explicit.get("response_text") or "")
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None
                and before_blocked == after_blocked,
                f"acquisition={(blocked_explicit.get('knowledge_acquisition') or {}).get('status')}",
            )

            request = build_active_perception_proposal_request(actor, SEMANTIC_SECRET_PHRASE)
            request_blob = json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False)
            catalog = list(request.get("catalog") or [])
            talk_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "INTERACTION"
                    and int(row.get("target_dbref") or 0) == int(mara.id)
                ),
                None,
            )
            observe_cap = next(
                (
                    row for row in catalog
                    if row.get("kind") == "PERCEPTION"
                    and str(row.get("capability_id") or "").startswith("OBSERVE:")
                    and int(row.get("target_dbref") or 0) == int(mara.id)
                ),
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
            check(
                "qwen-target-selection-boundary-does-not-receive-fact-or-disclosure-private-state",
                talk_cap is not None
                and SECRET_TEXT not in request_blob
                and SECRET_FACT_ID not in request_blob
                and SECRET_KNOWLEDGE_KEY not in request_blob
                and "min_familiarity" not in request_blob
                and PRIVATE_SENTINEL not in request_blob,
                f"talk={(talk_cap or {}).get('capability_id')} secret_leaked={SECRET_TEXT in request_blob}",
            )
            if not talk_cap or not observe_cap or not movement_cap:
                raise RuntimeError("required v0.84 capabilities missing")

            render_capture = {}

            def fake_renderer(*args, **kwargs):
                render_capture["called"] = True
                render_capture["fact_text"] = args[3] if len(args) > 3 else kwargs.get("fact_text")
                return {"status": "V084_FAKE_RENDER", "queued": True}

            blocked_semantic = handle_action_proposal_result_v84(
                actor,
                _accepted_result(talk_cap, 1.0, reason=MODEL_REASON_SENTINEL),
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "semantic-talk-blocks-before-closed-interaction-transfer-and-dialogue-renderer",
                blocked_semantic.get("status") == "INTERACTION_EXECUTED"
                and (blocked_semantic.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and not render_capture.get("called")
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None
                and SECRET_TEXT not in str(blocked_semantic.get("response_text") or ""),
                f"acquisition={(blocked_semantic.get('knowledge_acquisition') or {}).get('status')}",
            )

            set_familiarity(3)
            render_capture.clear()
            allowed_semantic = handle_action_proposal_result_v84(
                actor,
                _accepted_result(talk_cap, 1.0, reason=MODEL_REASON_SENTINEL),
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            acquired = find_knowledge_fact(actor, SECRET_FACT_ID)
            persistent_blob = json.dumps(
                _clone(
                    {
                        "actor_fact": acquired,
                        "actor_memories": getattr(actor.db, "memories", []),
                        "actor_relationships": getattr(actor.db, "relationships", {}),
                        "processed": getattr(registry.db, "processed_action_ids", []),
                        "log": getattr(registry.db, "action_log", []),
                    }
                ),
                ensure_ascii=False,
            )
            check(
                "meeting-authored-familiarity-unlocks-normal-authoritative-transfer-before-render",
                allowed_semantic.get("status") == "INTERACTION_EXECUTED"
                and (allowed_semantic.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and fact_knowledge_state(actor, acquired).get("known") is True
                and render_capture.get("called") is True
                and render_capture.get("fact_text") == SECRET_TEXT
                and MODEL_REASON_SENTINEL not in persistent_blob,
                f"acquisition={(allowed_semantic.get('knowledge_acquisition') or {}).get('status')} rendered={render_capture.get('called')}",
            )

            malformed_gate = evaluate_fact_disclosure(
                mara,
                actor,
                {
                    "id": MALFORMED_FACT_ID,
                    "topic": MALFORMED_TOPIC,
                    "text": "Dato que no debe salir con disclosure malformado.",
                    "knowledge_key": MALFORMED_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "disclosure": {"min_familiarity": "muchísimo"},
                },
            )
            check(
                "malformed-authored-disclosure-fails-closed-instead-of-becoming-public",
                malformed_gate.get("allowed") is False
                and malformed_gate.get("status") == "DISCLOSURE_MALFORMED_BLOCKED",
                f"status={malformed_gate.get('status')}",
            )

            reset_actor_secret_state()
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara.db.memories = _clone(original_mara_memories)
            set_familiarity(0)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            self.caller.msg(f"LIVE V084 DISCLOSURE TARGET PROBE: action={SEMANTIC_SECRET_PHRASE!r}")
            live = call_prebuilt_action_proposal(request, timeout=60)
            live_proposal = dict(live.get("proposal") or {})
            check(
                "live-qwen-selects-visible-mara-without-seeing-secret-disclosure-state",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and live_proposal.get("kind") == "INTERACTION"
                and str(live_proposal.get("capability_id") or "") == str(talk_cap.get("capability_id") or ""),
                f"status={live.get('status')} proposal={live_proposal}",
            )
            if not (live.get("status") == "ACCEPTED" and live_proposal.get("kind") == "INTERACTION"):
                raise RuntimeError("live semantic target selection did not produce Mara INTERACTION")

            live_blocked = handle_action_proposal_result_v84(
                actor,
                live,
                raw_player_input=SEMANTIC_SECRET_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "live-qwen-target-selection-still-cannot-override-authored-disclosure-gate",
                (live_blocked.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and find_knowledge_fact(actor, SECRET_FACT_ID) is None
                and SECRET_TEXT not in str(live_blocked.get("response_text") or ""),
                f"acquisition={(live_blocked.get('knowledge_acquisition') or {}).get('status')}",
            )

            inform = handle_action_proposal_result_v84(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "player-to-npc-inform-remains-owned-by-v079-not-disclosure-preflight",
                str(inform.get("build") or "") != NATURAL_FACT_DISCLOSURE_BUILD
                and str(inform.get("status") or "") in {"NO_KNOWN_FACT_FOR_TOPIC", "FACT_INFORM_EXECUTED"},
                f"status={inform.get('status')} build={inform.get('build')}",
            )

            knowledge_route = classify_v83_input(actor, "¿Qué sé sobre el sello negro de inventario?")
            check(
                "v083-first-person-knowledge-query-remains-deterministic-and-separate",
                knowledge_route.get("route") == "KNOWLEDGE_QUERY"
                and knowledge_route.get("ai_allowed") is False,
                f"route={knowledge_route.get('route')}",
            )

            render_capture.clear()
            observe = handle_action_proposal_result_v84(
                actor,
                _accepted_result(observe_cap, 1.0),
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "noninteraction-visible-perception-still-delegates-to-existing-bridge",
                observe.get("status") == "PERCEPTION_EXECUTED"
                and observe.get("executed") is True
                and not render_capture.get("called"),
                f"status={observe.get('status')}",
            )

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state
            fresh_catalog = list(build_active_perception_proposal_request(actor, SEMANTIC_SECRET_PHRASE).get("catalog") or [])
            analyze_cap = next(
                (row for row in fresh_catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID),
                None,
            )
            if not analyze_cap:
                raise RuntimeError("analyze capability missing")
            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_result = handle_action_proposal_result_v84(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "noninteraction-object-action-still-delegates-to-existing-world-engine",
                object_result.get("status") == "WORLD_ENGINE_ACCEPTED"
                and object_result.get("executed") is True
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_result.get('status')}",
            )
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)

            movement = handle_action_proposal_result_v84(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            check(
                "noninteraction-real-movement-still-delegates-to-existing-exit-bridge",
                movement.get("status") == "MOVEMENT_EXECUTED"
                and movement.get("executed") is True
                and actor.location != site,
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
        self.caller.msg(
            "STATE RESTORED: actor/Mara location, Knowledge/Facts, social state, object histories, manifest and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: the closed interaction/transfer/render engines remain authoritative after disclosure preflight; qwen still selects only a visible target"
        )
        self.caller.msg("========================================================")
