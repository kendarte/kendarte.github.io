import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v75_commands import SEMANTIC_PERCEPTION_PHRASE
from commands.world_input_v76_commands import (
    CmdSizaNoMatchV76,
    SEMANTIC_ACTIVE_SEARCH_PHRASE,
    handle_action_proposal_result_v76,
)
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT, call_prebuilt_action_proposal
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.action_resolution_engine import action_resolution_history
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.object_action_engine import object_action_history
from services.perception_knowledge_projection_engine import (
    PERCEPTION_KNOWLEDGE_PROJECTION_BUILD,
    project_discovered_perception_facts,
)
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_PERCEPTION_KNOWLEDGE_BUILD = "0.77.0-perception-discovery-to-knowledge"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar esa búsqueda."
TEST_PERCEPTION_FACT_ID = "FACT-V077-PESCADERIA-ARRASTRE-001"
TEST_KNOWLEDGE_FACT_ID = "KFACT-V077-PESCADERIA-ARRASTRE-001"
TEST_KNOWLEDGE_KEY = "V077_PESCADERIA_ARRASTRE"
TEST_TOPIC = "marca de arrastre bajo mostrador"
TEST_DISCOVERY_TEXT = "Debajo del mostrador descubres una marca de arrastre reciente que termina junto al zócalo."
TEST_KNOWLEDGE_TEXT = "Hay una marca de arrastre reciente bajo el mostrador de la pescadería que termina junto al zócalo."
LEGACY_PERCEPTION_FACT_ID = "FACT-V077-LEGACY-ONLY-001"
MALFORMED_PERCEPTION_FACT_ID = "FACT-V077-MALFORMED-PROJECTION-001"
PRIVATE_SENTINEL = "NEVER_LEAK_V077_PERCEPTION_KNOWLEDGE_SENTINEL"


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


def _is_room_search_proposal(proposal_result):
    return _proposal_kind(proposal_result) == "PERCEPTION" and _capability_id(proposal_result).startswith("SEARCH:ROOM:")


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


def _projectable_fact(perception_fact_id=TEST_PERCEPTION_FACT_ID):
    return {
        "id": perception_fact_id,
        "sense": "sight",
        "target": "mostrador",
        "keywords": ["mostrador", "debajo", "zócalo", "arrastre"],
        "fact": TEST_DISCOVERY_TEXT,
        "difficulty": 1,
        "knowledge_fact": {
            "id": TEST_KNOWLEDGE_FACT_ID,
            "topic": TEST_TOPIC,
            "text": TEST_KNOWLEDGE_TEXT,
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "required_level": 1,
            "canon_status": "prototype",
            "source": {"validator_private_sentinel": PRIVATE_SENTINEL},
        },
        "knowledge": {
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "mode": "MAX",
            "value": 1,
        },
    }


def _legacy_fact():
    return {
        "id": LEGACY_PERCEPTION_FACT_ID,
        "sense": "sight",
        "target": "mostrador",
        "keywords": ["mostrador"],
        "fact": "Encuentras una mota de pintura vieja bajo el mostrador.",
        "difficulty": 1,
    }


def _malformed_fact():
    item = _projectable_fact(MALFORMED_PERCEPTION_FACT_ID)
    item["knowledge_fact"] = dict(item["knowledge_fact"])
    item["knowledge_fact"]["id"] = "KFACT-V077-MALFORMED-001"
    item["knowledge_fact"]["knowledge_key"] = "V077_WRONG_KEY"
    return item


def _emit_base_active_result(actor, packet):
    roll_line = str((packet or {}).get("roll_text") or "").strip()
    text = str((packet or {}).get("rendered_text") or "").strip()
    if roll_line:
        actor.msg(roll_line)
    if text:
        actor.msg("\n" + text)


def handle_action_proposal_result_v77(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
):
    """Project newly discovered authored perception facts into Knowledge atomically."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    if not (
        proposal_result.get("status") == "ACCEPTED"
        and proposal_result.get("accepted") is True
        and _is_room_search_proposal(proposal_result)
    ):
        return handle_action_proposal_result_v76(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
        )

    before_discovered = _clone(getattr(actor.db, "discovered_facts", []))
    before_knowledge = _clone(getattr(actor.db, "knowledge", {}))
    before_facts = _clone(getattr(actor.db, "knowledge_facts", []))

    base = handle_action_proposal_result_v76(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=False,
    )
    if base.get("status") != "ACTIVE_PERCEPTION_EXECUTED" or base.get("executed") is not True:
        if emit_messages:
            if base.get("status") == "NO_ACTIVE_PERCEPTION_STALE":
                actor.msg("\n" + SITUATION_CHANGED_TEXT)
            else:
                actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
        return base

    bridge = dict(base.get("bridge") or {})
    added_ids = list(bridge.get("discovered_fact_ids_added") or [])
    room = getattr(actor, "location", None)
    projection = project_discovered_perception_facts(actor, room, added_ids)

    if not bool(projection.get("success")):
        actor.db.discovered_facts = before_discovered
        actor.db.knowledge = before_knowledge
        actor.db.knowledge_facts = before_facts
        logger.log_err(
            f"SIZA perception Knowledge projection failed; discovery rolled back: status={projection.get('status')} error={projection.get('error')}"
        )
        if emit_messages:
            actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
        return {
            "status": "NO_ACTIVE_PERCEPTION_PROJECTION_FAILED",
            "executed": False,
            "base": base,
            "knowledge_projection": projection,
            "restored": True,
        }

    result = {
        **base,
        "knowledge_projection": projection,
        "build": NATURAL_PERCEPTION_KNOWLEDGE_BUILD,
    }
    if emit_messages:
        _emit_base_active_result(actor, base)
    return result


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.77 active perception proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v77(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v77(
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


class CmdSizaNoMatchV77(CmdSizaNoMatchV76):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v77(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV77(Command):
    key = "siza-validate-v77"
    aliases = ["validate-v77"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.77 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
        manifest = context.get("manifest")
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
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_perception_facts = _clone(getattr(site.db, "perception_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.77 | {NATURAL_PERCEPTION_KNOWLEDGE_BUILD} ===")
        self.caller.msg(
            "perception discovery -> exact authored projection -> Knowledge level + structured Fact -> normal known-Fact retrieval"
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
                if str(item) not in {TEST_PERCEPTION_FACT_ID, LEGACY_PERCEPTION_FACT_ID, MALFORMED_PERCEPTION_FACT_ID}
            ]
            actor.db.knowledge = {
                key: value for key, value in dict(original_knowledge or {}).items()
                if str(key) not in {TEST_KNOWLEDGE_KEY, "V077_WRONG_KEY"}
            }
            actor.db.knowledge_facts = [
                row for row in list(original_facts or [])
                if str((row or {}).get("id") or "") not in {TEST_KNOWLEDGE_FACT_ID, "KFACT-V077-MALFORMED-001"}
            ]
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state

            semantic = classify_v741_input(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            check(
                "v077-preserves-semantic-active-search-route",
                semantic.get("route") == "AI_ACTION_PROPOSAL" and semantic.get("ai_allowed") is True,
                f"route={semantic.get('route')}",
            )

            site.db.perception_facts = [_projectable_fact()]
            request = build_active_perception_proposal_request(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            catalog = list(request.get("catalog") or [])
            search_cap = dict(request.get("room_search_capability") or {})
            observe_cap = next(
                (row for row in catalog if row.get("kind") == "PERCEPTION" and str(row.get("capability_id") or "").startswith("OBSERVE:") and int(row.get("target_dbref") or 0) == int(mara.id)),
                None,
            )
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
                "qwen-boundary-still-excludes-authored-knowledge-projection",
                bool(search_cap)
                and observe_cap is not None
                and talk_cap is not None
                and analyze_cap is not None
                and movement_cap is not None
                and TEST_KNOWLEDGE_FACT_ID not in request_text
                and TEST_KNOWLEDGE_TEXT not in request_text
                and TEST_KNOWLEDGE_KEY not in request_text
                and PRIVATE_SENTINEL not in request_text,
                f"search={search_cap.get('capability_id')} leaked={PRIVATE_SENTINEL in request_text}",
            )
            if not search_cap or not observe_cap or not talk_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.77 capabilities missing")

            before_low_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            before_low_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            before_low_facts = _clone(getattr(actor.db, "knowledge_facts", []))
            low = handle_action_proposal_result_v77(
                actor,
                _accepted_result(search_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "low-confidence-search-cannot-project-or-mutate-knowledge",
                not low.get("executed")
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_low_discovered
                and _clone(getattr(actor.db, "knowledge", {})) == before_low_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == before_low_facts,
                f"status={low.get('status')}",
            )

            actor.db.discovered_facts = list(before_low_discovered or [])
            actor.db.knowledge = before_low_knowledge
            actor.db.knowledge_facts = before_low_facts
            projected = handle_action_proposal_result_v77(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            projection = dict(projected.get("knowledge_projection") or {})
            projected_rows = list(projection.get("projected") or [])
            check(
                "successful-perception-discovery-projects-explicit-knowledge-atomically",
                projected.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (projected.get("bridge") or {}).get("engine_status") == "DISCOVERY"
                and TEST_PERCEPTION_FACT_ID in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and int(dict(getattr(actor.db, "knowledge", {}) or {}).get(TEST_KNOWLEDGE_KEY, 0) or 0) >= 1
                and len(projected_rows) == 1
                and projected_rows[0].get("knowledge_fact_id") == TEST_KNOWLEDGE_FACT_ID
                and projected_rows[0].get("knowledge_key") == TEST_KNOWLEDGE_KEY
                and projected_rows[0].get("text") == TEST_KNOWLEDGE_TEXT,
                f"engine={(projected.get('bridge') or {}).get('engine_status')} projection={projection.get('status')}",
            )

            retrieval = retrieve_known_facts(actor, query="marca arrastre mostrador")
            check(
                "projected-perception-fact-enters-normal-known-fact-retrieval",
                TEST_KNOWLEDGE_FACT_ID in list(retrieval.get("selected_fact_ids") or [])
                and TEST_KNOWLEDGE_TEXT in str(retrieval.get("context_text") or ""),
                f"selected={retrieval.get('selected_fact_ids')}",
            )

            after_first_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            after_first_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            after_first_facts = _clone(getattr(actor.db, "knowledge_facts", []))
            repeat = handle_action_proposal_result_v77(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            fact_count = sum(
                1 for row in list(getattr(actor.db, "knowledge_facts", []) or [])
                if str((row or {}).get("id") or "") == TEST_KNOWLEDGE_FACT_ID
            )
            check(
                "repeat-search-is-idempotent-across-discovered-and-knowledge-facts",
                repeat.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (repeat.get("bridge") or {}).get("engine_status") == "NO_AUTHORIZED_DISCOVERY"
                and _clone(getattr(actor.db, "discovered_facts", [])) == after_first_discovered
                and _clone(getattr(actor.db, "knowledge", {})) == after_first_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == after_first_facts
                and fact_count == 1,
                f"engine={(repeat.get('bridge') or {}).get('engine_status')} fact_count={fact_count}",
            )

            actor.db.discovered_facts = list(before_low_discovered or [])
            actor.db.knowledge = before_low_knowledge
            actor.db.knowledge_facts = before_low_facts
            site.db.perception_facts = [_legacy_fact()]
            legacy = handle_action_proposal_result_v77(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "perception-fact-without-projection-preserves-v076-discovered-only-behavior",
                legacy.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (legacy.get("bridge") or {}).get("engine_status") == "DISCOVERY"
                and LEGACY_PERCEPTION_FACT_ID in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and _clone(getattr(actor.db, "knowledge", {})) == before_low_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == before_low_facts
                and (legacy.get("knowledge_projection") or {}).get("status") == "NO_PROJECTION",
                f"projection={(legacy.get('knowledge_projection') or {}).get('status')}",
            )

            actor.db.discovered_facts = list(before_low_discovered or [])
            actor.db.knowledge = before_low_knowledge
            actor.db.knowledge_facts = before_low_facts
            site.db.perception_facts = [_malformed_fact()]
            malformed_before_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            malformed_before_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            malformed_before_facts = _clone(getattr(actor.db, "knowledge_facts", []))
            malformed = handle_action_proposal_result_v77(
                actor,
                _accepted_result(search_cap, 1.0),
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            check(
                "malformed-authored-projection-rolls-back-discovery-and-knowledge-as-one-transaction",
                malformed.get("status") == "NO_ACTIVE_PERCEPTION_PROJECTION_FAILED"
                and malformed.get("restored") is True
                and _clone(getattr(actor.db, "discovered_facts", [])) == malformed_before_discovered
                and _clone(getattr(actor.db, "knowledge", {})) == malformed_before_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == malformed_before_facts,
                f"status={malformed.get('status')} error={(malformed.get('knowledge_projection') or {}).get('error')}",
            )

            actor.db.discovered_facts = list(before_low_discovered or [])
            actor.db.knowledge = before_low_knowledge
            actor.db.knowledge_facts = before_low_facts
            site.db.perception_facts = [_projectable_fact()]
            request = build_active_perception_proposal_request(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            self.caller.msg(
                f"LIVE V077 PERCEPTION KNOWLEDGE PROBE: action={SEMANTIC_ACTIVE_SEARCH_PHRASE!r} room={site.key!r}"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-still-selects-only-generic-room-search-without-knowledge-access",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "PERCEPTION"
                and _capability_id(live) == str(search_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_live_obj = len(object_action_history(actor))
            before_live_res = len(action_resolution_history(actor))
            before_live_memories = _clone(getattr(actor.db, "memories", []))
            before_live_relationships = _clone(getattr(actor.db, "relationships", {}))
            live_handled = handle_action_proposal_result_v77(
                actor,
                live,
                raw_player_input=SEMANTIC_ACTIVE_SEARCH_PHRASE,
                emit_messages=False,
            )
            live_projection = dict(live_handled.get("knowledge_projection") or {})
            live_retrieval = retrieve_known_facts(actor, query="marca arrastre mostrador")
            check(
                "live-search-rolls-discovers-projects-and-is-immediately-retrievable",
                live_handled.get("status") == "ACTIVE_PERCEPTION_EXECUTED"
                and (live_handled.get("bridge") or {}).get("engine_status") == "DISCOVERY"
                and live_projection.get("status") == "PROJECTED"
                and TEST_KNOWLEDGE_FACT_ID in list(live_retrieval.get("selected_fact_ids") or [])
                and len(object_action_history(actor)) == before_live_obj
                and len(action_resolution_history(actor)) == before_live_res
                and _clone(getattr(actor.db, "memories", [])) == before_live_memories
                and _clone(getattr(actor.db, "relationships", {})) == before_live_relationships,
                f"engine={(live_handled.get('bridge') or {}).get('engine_status')} projection={live_projection.get('status')}",
            )

            live_reason = str((live.get("proposal") or {}).get("reason") or "")
            persistent_blob = json.dumps(
                {
                    "discovered": _clone(getattr(actor.db, "discovered_facts", [])),
                    "knowledge": _clone(getattr(actor.db, "knowledge", {})),
                    "facts": _clone(getattr(actor.db, "knowledge_facts", [])),
                },
                ensure_ascii=False,
            )
            check(
                "live-model-reason-never-enters-perception-or-knowledge-state",
                live_reason not in persistent_blob
                and PRIVATE_SENTINEL not in json.dumps(request.get("ollama_payload") or {}, ensure_ascii=False),
                "model_reason_not_persisted=True private_projection_not_sent=True",
            )

            self.caller.msg("--- LIVE V077 PERCEPTION KNOWLEDGE RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "engine_status": (live_handled.get("bridge") or {}).get("engine_status"),
                "roll": (live_handled.get("bridge") or {}).get("roll"),
                "discovered": (live_handled.get("bridge") or {}).get("discovered"),
                "projection_status": live_projection.get("status"),
                "projected": live_projection.get("projected"),
                "retrieved_fact_ids": live_retrieval.get("selected_fact_ids"),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V077 PERCEPTION KNOWLEDGE RESULT ---")

            before_visible = _clone(getattr(actor.db, "discovered_facts", []))
            visible = handle_action_proposal_result_v77(
                actor,
                _accepted_result(observe_cap, 1.0),
                raw_player_input=SEMANTIC_PERCEPTION_PHRASE,
                emit_messages=False,
            )
            check(
                "v077-preserves-v075-visible-observe-route",
                visible.get("status") == "PERCEPTION_EXECUTED"
                and (visible.get("bridge") or {}).get("engine_status") == "AUTO_SUCCESS"
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_visible,
                f"status={visible.get('status')}",
            )

            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            interaction = handle_action_proposal_result_v77(
                actor,
                _accepted_result(talk_cap, 1.0),
                raw_player_input="me acerco a Mara para intercambiar unas palabras",
                emit_messages=False,
            )
            check(
                "v077-preserves-structured-interaction-route",
                interaction.get("status") == "INTERACTION_EXECUTED" and interaction.get("executed") is True,
                f"status={interaction.get('status')}",
            )
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_regression = handle_action_proposal_result_v77(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v077-preserves-object-action-route",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (object_regression.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement = handle_action_proposal_result_v77(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v077-preserves-real-exit-movement-route",
                movement.get("status") == "MOVEMENT_EXECUTED" and movement.get("executed") is True and actor.location != site,
                f"status={movement.get('status')} location={actor.location.key if actor.location else None}",
            )
            actor.move_to(site, quiet=True)

            explicit_talk = classify_v741_input(actor, "hablo con Mara sobre manifiesto duplicado")
            check(
                "v077-preserves-explicit-talk-precedence",
                explicit_talk.get("route") == "INTERACTION" and explicit_talk.get("ai_allowed") is False,
                f"route={explicit_talk.get('route')}",
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
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            manifest.db.state = original_manifest_state
            site.db.perception_facts = original_perception_facts

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Mara location, stats, discovered facts, Knowledge/Facts, social state, action histories, manifest and room perception facts restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: qwen selects only SEARCH; perception engine owns discovery; authored projection alone may convert a new discovery into retrievable Knowledge"
        )
        self.caller.msg("========================================================")
