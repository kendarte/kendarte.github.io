import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v79_commands import INFORM_PHRASE, _accepted_result
from commands.world_input_v80_commands import handle_action_proposal_result_v80
from commands.world_input_v81_commands import CmdSizaNoMatchV81, handle_action_proposal_result_v81
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT
from services.action_resolution_engine import action_resolution_history
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.consequence_engine import get_consequence_registry
from services.conversation_fact_acquisition_engine import resolve_interaction_with_fact_acquisition
from services.dialogue_style_context_engine import (
    DIALOGUE_STYLE_CONTEXT_BUILD,
    build_dialogue_style_context,
)
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import fact_knowledge_state, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.object_action_engine import object_action_history
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent
from services.styled_grounded_dialogue_renderer import (
    STYLED_GROUNDED_DIALOGUE_BUILD,
    build_styled_grounded_dialogue_request,
    render_styled_grounded_dialogue_async,
    render_styled_grounded_dialogue_sync,
)
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_STYLED_DIALOGUE_BUILD = "0.82.0-explicit-style-grounded-dialogue"
SEMANTIC_DIALOGUE_PHRASE = "me acerco a Mara y le saco el tema del sello del turno de ceniza"
TEST_FACT_ID = "KFACT-V082-MARA-SELLO-001"
TEST_KNOWLEDGE_KEY = "V082_MARA_SELLO"
TEST_TOPIC = "sello del turno de ceniza"
TEST_TEXT = "El sello del turno de ceniza fue estampado después del cierre de la dársena."
PRIVATE_STYLE_SENTINEL = "NEVER_LEAK_V082_PRIVATE_STYLE_SENTINEL"
TEST_TRAIT_ID = "TRAIT-V082-DIALOGUE-STYLE-001"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def _acquisition_can_render(acquisition):
    status = str((acquisition or {}).get("status") or "")
    return status in {"FACT_ACQUIRED", "FACT_ALREADY_ACQUIRED"} and bool(
        str((acquisition or {}).get("fact_text") or "").strip()
    )


def _visible_local_npc_by_dbref(actor, dbref):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    for obj in list(getattr(location, "contents", []) or []):
        if getattr(obj, "id", None) != wanted:
            continue
        if bool(getattr(obj.db, "hidden", False)):
            return None
        if not bool(getattr(obj.db, "is_npc", False)):
            return None
        return obj
    return None


def present_conversation_result_v82(
    actor,
    packet,
    *,
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """Apply only explicit non-factual style metadata after the Fact is already authoritative."""
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
                "build": STYLED_GROUNDED_DIALOGUE_BUILD,
            },
            "build": NATURAL_STYLED_DIALOGUE_BUILD,
        }

    npc = _visible_local_npc_by_dbref(actor, acquisition.get("source_dbref"))
    style_packet = build_dialogue_style_context(npc, actor)
    safe_style = dict(style_packet.get("safe_style") or {})
    renderer = render_async_callable or render_styled_grounded_dialogue_async
    render_packet = renderer(
        actor,
        str(acquisition.get("source_name") or getattr(npc, "key", None) or "NPC"),
        str(acquisition.get("topic") or ""),
        str(acquisition.get("fact_text") or text),
        style_context=safe_style,
        fallback_text=text or str(acquisition.get("fact_text") or ""),
        **dict(provider_options or {}),
    )
    return {
        **result,
        "dialogue_style": style_packet,
        "dialogue_render": render_packet,
        "build": NATURAL_STYLED_DIALOGUE_BUILD,
    }


def handle_action_proposal_result_v82(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """Intercept only accepted ordinary TALK; all other v0.81 routes remain untouched."""
    proposal = proposal_result if isinstance(proposal_result, dict) else {}
    accepted_interaction = (
        proposal.get("status") == "ACCEPTED"
        and proposal.get("accepted") is True
        and _proposal_kind(proposal) == "INTERACTION"
    )
    if parse_semantic_fact_inform_intent(raw_player_input) or not accepted_interaction:
        return handle_action_proposal_result_v81(
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

    return present_conversation_result_v82(
        actor,
        base,
        emit_messages=emit_messages,
        render_async_callable=render_async_callable,
        provider_options=provider_options,
    )


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.82 action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v82(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v82(
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


class CmdSizaNoMatchV82(CmdSizaNoMatchV81):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "INTERACTION" and classification.get("explicit_talk_precedence"):
            packet = resolve_interaction_with_fact_acquisition(
                self.caller,
                classification.get("intent")
                or parse_interaction_intent(raw)
                or {"intent": "TALK", "raw": raw},
            )
            present_conversation_result_v82(self.caller, packet, emit_messages=True)
            return None
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v82(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV82(Command):
    key = "siza-validate-v82"
    aliases = ["validate-v82"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.82 VALIDATION] FAIL | context={context}")
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
        original_mara_style = _clone(getattr(mara.db, "dialogue_style", {}))
        original_mara_traits = _clone(getattr(mara.db, "traits", []))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.82 | {NATURAL_STYLED_DIALOGUE_BUILD} ===")
        self.caller.msg(
            "authoritative Fact transfer -> explicit NPC/trait style enums + familiarity band -> grounded presentation-only qwen render"
        )

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
            mara.db.relationships = {
                "V082_VALIDATOR_ACTOR": {
                    "target_type": "CHARACTER",
                    "target_dbref": int(actor.id),
                    "target_name": actor.key,
                    "familiarity": 4,
                    "last_interaction": PRIVATE_STYLE_SENTINEL,
                }
            }
            mara.db.dialogue_style = {
                "register": "FORMAL",
                "warmth": "RESERVED",
                "directness": "BALANCED",
                "verbosity": "NORMAL",
                "cadence": "MEASURED",
                "private_note": PRIVATE_STYLE_SENTINEL,
            }
            mara.db.traits = list(original_mara_traits or []) + [
                {
                    "id": TEST_TRAIT_ID,
                    "name": PRIVATE_STYLE_SENTINEL,
                    "kind": "VIRTUE",
                    "enabled": True,
                    "dialogue_effects": [
                        {"id": "V082-DIRECT", "enabled": True, "dimension": "directness", "value": "DIRECT"},
                        {"id": "V082-TERSE", "enabled": True, "dimension": "verbosity", "value": "TERSE"},
                        {"id": "V082-CLIPPED", "enabled": True, "dimension": "cadence", "value": "CLIPPED"},
                        {"id": PRIVATE_STYLE_SENTINEL, "enabled": True, "dimension": "warmth", "value": "HOSTILE"},
                    ],
                }
            ]
            upsert_knowledge_fact(
                mara,
                {
                    "id": TEST_FACT_ID,
                    "topic": TEST_TOPIC,
                    "aliases": ["sello de ceniza", "turno de ceniza"],
                    "text": TEST_TEXT,
                    "knowledge_key": TEST_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"validator": "v0.82"},
                    "learned_by": {"provider": "V082_VALIDATOR"},
                },
            )
            set_knowledge_level(mara, TEST_KNOWLEDGE_KEY, 1)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            style_packet = build_dialogue_style_context(mara, actor)
            safe_style = dict(style_packet.get("safe_style") or {})
            check(
                "explicit-style-context-applies-npc-profile-trait-overrides-and-neutral-familiarity-band",
                safe_style == {
                    "register": "FORMAL",
                    "warmth": "RESERVED",
                    "directness": "DIRECT",
                    "verbosity": "TERSE",
                    "cadence": "CLIPPED",
                    "familiarity_band": "FAMILIAR",
                },
                f"style={safe_style}",
            )

            ignored = list((style_packet.get("diagnostics") or {}).get("ignored") or [])
            check(
                "invalid-freeform-style-values-are-ignored-instead-of-becoming-model-instructions",
                any(str(row.get("value") or "") == "HOSTILE" for row in ignored)
                and "HOSTILE" not in json.dumps(safe_style),
                f"ignored={len(ignored)}",
            )

            render_request = build_styled_grounded_dialogue_request(
                mara.key,
                TEST_TOPIC,
                TEST_TEXT,
                style_context=safe_style,
            )
            boundary = json.dumps(render_request.get("provider_payload") or {}, ensure_ascii=False)
            check(
                "style-provider-boundary-exposes-only-enums-and-exact-fact-not-trait-relationship-private-state",
                TEST_TEXT in boundary
                and "FORMAL" in boundary
                and "DIRECT" in boundary
                and "FAMILIAR" in boundary
                and TEST_TRAIT_ID not in boundary
                and PRIVATE_STYLE_SENTINEL not in boundary
                and str(actor.id) not in boundary,
                f"private_leaked={PRIVATE_STYLE_SENTINEL in boundary}",
            )

            classification = classify_v741_input(actor, SEMANTIC_DIALOGUE_PHRASE)
            request = build_active_perception_proposal_request(actor, SEMANTIC_DIALOGUE_PHRASE)
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
                "semantic-style-dialogue-still-uses-v081-authoritative-target-selection-boundary",
                classification.get("route") == "AI_ACTION_PROPOSAL"
                and talk_cap is not None
                and observe_cap is not None
                and movement_cap is not None,
                f"route={classification.get('route')} talk={(talk_cap or {}).get('capability_id')}",
            )
            if not talk_cap or not observe_cap or not movement_cap:
                raise RuntimeError("required v0.82 capabilities missing")

            captured = {}

            def fake_renderer(current_actor, npc_name, topic, fact_text, *, style_context=None, fallback_text="", **kwargs):
                captured.update(
                    {
                        "actor": current_actor,
                        "npc_name": npc_name,
                        "topic": topic,
                        "fact_text": fact_text,
                        "style_context": dict(style_context or {}),
                        "fallback_text": fallback_text,
                    }
                )
                return {
                    "status": "STYLED_DIALOGUE_RENDER_QUEUED",
                    "queued": True,
                    "safe_style": dict(style_context or {}),
                    "build": STYLED_GROUNDED_DIALOGUE_BUILD,
                }

            handled = handle_action_proposal_result_v82(
                actor,
                _accepted_result(talk_cap, 1.0, reason="V082_TARGET_ONLY_REASON"),
                raw_player_input=SEMANTIC_DIALOGUE_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            )
            acquired = find_knowledge_fact(actor, TEST_FACT_ID)
            check(
                "fact-transfer-remains-authoritative-and-completes-before-styled-renderer-is-queued",
                handled.get("status") == "INTERACTION_EXECUTED"
                and (handled.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and fact_knowledge_state(actor, acquired).get("known") is True
                and captured.get("fact_text") == TEST_TEXT
                and captured.get("style_context") == safe_style,
                f"acquisition={(handled.get('knowledge_acquisition') or {}).get('status')} queued={(handled.get('dialogue_render') or {}).get('queued')}",
            )

            persistent_blob = json.dumps(
                _clone(
                    {
                        "actor_fact": acquired,
                        "actor_memories": getattr(actor.db, "memories", []),
                        "actor_relationships": getattr(actor.db, "relationships", {}),
                        "registry_processed": getattr(registry.db, "processed_action_ids", []),
                        "registry_log": getattr(registry.db, "action_log", []),
                    }
                ),
                ensure_ascii=False,
            )
            check(
                "style-metadata-and-model-target-reason-never-become-player-knowledge-or-world-state",
                "V082_TARGET_ONLY_REASON" not in persistent_blob
                and PRIVATE_STYLE_SENTINEL not in str(acquired or {}),
                "reason_persisted=False",
            )

            before_live_state = _clone(
                {
                    "actor_knowledge": getattr(actor.db, "knowledge", {}),
                    "actor_facts": getattr(actor.db, "knowledge_facts", []),
                    "actor_memories": getattr(actor.db, "memories", []),
                    "actor_relationships": getattr(actor.db, "relationships", {}),
                    "mara_knowledge": getattr(mara.db, "knowledge", {}),
                    "mara_facts": getattr(mara.db, "knowledge_facts", []),
                    "mara_relationships": getattr(mara.db, "relationships", {}),
                    "registry_processed": getattr(registry.db, "processed_action_ids", []),
                    "registry_log": getattr(registry.db, "action_log", []),
                }
            )
            style_a = {
                "register": "FORMAL",
                "warmth": "RESERVED",
                "directness": "DIRECT",
                "verbosity": "TERSE",
                "cadence": "CLIPPED",
                "familiarity_band": "FAMILIAR",
            }
            style_b = {
                "register": "CASUAL",
                "warmth": "WARM",
                "directness": "BALANCED",
                "verbosity": "NORMAL",
                "cadence": "MEASURED",
                "familiarity_band": "ESTABLISHED",
            }
            self.caller.msg(f"LIVE V082 STYLE A: {style_a}")
            live_a = render_styled_grounded_dialogue_sync(
                mara.key,
                TEST_TOPIC,
                TEST_TEXT,
                style_context=style_a,
                fallback_text=TEST_TEXT,
                timeout=60,
            )
            self.caller.msg(f"LIVE V082 STYLE A RESULT: {live_a.get('display_text')}")
            self.caller.msg(f"LIVE V082 STYLE B: {style_b}")
            live_b = render_styled_grounded_dialogue_sync(
                mara.key,
                TEST_TOPIC,
                TEST_TEXT,
                style_context=style_b,
                fallback_text=TEST_TEXT,
                timeout=60,
            )
            self.caller.msg(f"LIVE V082 STYLE B RESULT: {live_b.get('display_text')}")
            after_live_state = _clone(
                {
                    "actor_knowledge": getattr(actor.db, "knowledge", {}),
                    "actor_facts": getattr(actor.db, "knowledge_facts", []),
                    "actor_memories": getattr(actor.db, "memories", []),
                    "actor_relationships": getattr(actor.db, "relationships", {}),
                    "mara_knowledge": getattr(mara.db, "knowledge", {}),
                    "mara_facts": getattr(mara.db, "knowledge_facts", []),
                    "mara_relationships": getattr(mara.db, "relationships", {}),
                    "registry_processed": getattr(registry.db, "processed_action_ids", []),
                    "registry_log": getattr(registry.db, "action_log", []),
                }
            )
            check(
                "live-style-rendering-remains-grounded-and-exactly-read-only",
                live_a.get("status") == "STYLED_GROUNDED_DIALOGUE_RENDERED"
                and live_b.get("status") == "STYLED_GROUNDED_DIALOGUE_RENDERED"
                and before_live_state == after_live_state,
                f"A={live_a.get('status')} B={live_b.get('status')}",
            )

            no_info_capture = {}
            mara_levels = dict(getattr(mara.db, "knowledge", {}) or {})
            mara_levels[TEST_KNOWLEDGE_KEY] = 0
            mara.db.knowledge = mara_levels

            def should_not_render(*args, **kwargs):
                no_info_capture["called"] = True
                return {"status": "SHOULD_NOT_RUN"}

            no_info = handle_action_proposal_result_v82(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=SEMANTIC_DIALOGUE_PHRASE,
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "no-information-dialogue-never-consumes-style-or-calls-qwen-renderer",
                no_info.get("status") == "INTERACTION_EXECUTED"
                and (no_info.get("knowledge_acquisition") or {}).get("status") == "NO_SHARED_FACT_IN_NEW_CONVERSATION"
                and not no_info_capture.get("called"),
                f"acquisition={(no_info.get('knowledge_acquisition') or {}).get('status')}",
            )
            mara_levels[TEST_KNOWLEDGE_KEY] = 1
            mara.db.knowledge = mara_levels

            inform = handle_action_proposal_result_v82(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input=INFORM_PHRASE,
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "player-to-npc-inform-remains-owned-by-v079-without-style-rendering",
                str(inform.get("build") or "") != NATURAL_STYLED_DIALOGUE_BUILD
                and not no_info_capture.get("called"),
                f"status={inform.get('status')} build={inform.get('build')}",
            )

            observe = handle_action_proposal_result_v82(
                actor,
                _accepted_result(observe_cap, 1.0),
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "v082-preserves-visible-perception-bridge-without-dialogue-style-interception",
                observe.get("status") == "PERCEPTION_EXECUTED"
                and observe.get("executed") is True
                and not no_info_capture.get("called"),
                f"status={observe.get('status')}",
            )

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state
            fresh_catalog = list(build_active_perception_proposal_request(actor, SEMANTIC_DIALOGUE_PHRASE).get("catalog") or [])
            analyze_cap = next(
                (row for row in fresh_catalog if str(row.get("object_action_id") or "") == ANALYZE_ACTION_ID),
                None,
            )
            if not analyze_cap:
                raise RuntimeError("analyze capability missing")
            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_result = handle_action_proposal_result_v82(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "v082-preserves-object-action-bridge",
                object_result.get("status") == "WORLD_ENGINE_ACCEPTED"
                and object_result.get("executed") is True
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1
                and not no_info_capture.get("called"),
                f"status={object_result.get('status')}",
            )
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)

            movement = handle_action_proposal_result_v82(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
                render_async_callable=should_not_render,
            )
            check(
                "v082-preserves-real-exit-movement-bridge",
                movement.get("status") == "MOVEMENT_EXECUTED"
                and movement.get("executed") is True
                and actor.location != site
                and not no_info_capture.get("called"),
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
            mara.db.dialogue_style = original_mara_style
            mara.db.traits = original_mara_traits
            manifest.db.state = original_manifest_state
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Mara location, Knowledge/Facts, social state, dialogue style/traits, object histories, manifest and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: Facts remain authoritative before rendering; qwen receives only exact Fact text plus closed non-factual style enums"
        )
        self.caller.msg("MANUAL ACCEPTANCE: compare LIVE V082 STYLE A RESULT vs STYLE B RESULT for a meaningful voice difference without factual drift")
        self.caller.msg("========================================================")
