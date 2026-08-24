import json

from evennia import Command
from evennia.utils import logger

from commands.world_input_v71_commands import classify_v71_input
from commands.world_input_v72_commands import (
    CmdSizaNoMatchV72,
    handle_action_proposal_result_v72,
)
from services.action_intent_proposal_engine import build_action_proposal_request, build_local_capability_catalog
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
)
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_INTERACTION_INPUT_BUILD = "0.73.0-async-revalidated-interaction-proposal"
SITUATION_CHANGED_TEXT = "La situación cambió antes de completar esa interacción."
SEMANTIC_INTERACTION_PHRASE = "me acerco a Mara para intercambiar unas palabras"


def _proposal_kind(proposal_result):
    try:
        return str((proposal_result.get("proposal") or {}).get("kind") or "")
    except Exception:
        return ""


def handle_action_proposal_result_v73(actor, proposal_result, *, emit_messages=True):
    """Add INTERACTION execution while preserving v0.72 MOVEMENT and v0.71 OBJECT_ACTION behavior."""
    proposal_result = proposal_result if isinstance(proposal_result, dict) else {}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return handle_action_proposal_result_v72(actor, proposal_result, emit_messages=emit_messages)

    if _proposal_kind(proposal_result) != "INTERACTION":
        return handle_action_proposal_result_v72(actor, proposal_result, emit_messages=emit_messages)

    bridge = execute_validated_interaction_proposal(actor, proposal_result)
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

    logger.log_err(f"SIZA interaction proposal rejected before interaction: status={bridge_status}")
    if emit_messages:
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return {"status": "NO_INTERACTION_REJECTED", "executed": False, "bridge": bridge}


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA interaction/movement/action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v73(actor, raw, **provider_options):
    return dispatch_action_proposal_async(
        actor,
        raw,
        on_result=handle_action_proposal_result_v73,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV73(CmdSizaNoMatchV72):
    """Preserve v0.72 routing; allow fresh high-confidence TALK capabilities to invoke the existing interaction engine."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v71_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v73(self.caller, raw)
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


def _relationship_familiarity(holder, key):
    try:
        rels = {str(k): v for k, v in (holder.db.relationships or {}).items()}
        row = rels.get(str(key), {}) or {}
        return int(row.get("familiarity", 0) or 0)
    except Exception:
        return 0


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


class CmdSizaValidateV73(Command):
    key = "siza-validate-v73"
    aliases = ["validate-v73"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.73 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.73 | {NATURAL_INTERACTION_INPUT_BUILD} ===")
        self.caller.msg(
            "unknown semantic social intent -> structured TALK capability -> fresh visible NPC revalidation -> existing interaction engine"
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

            direct = classify_v71_input(actor, "hablo con Mara")
            check(
                "known-deterministic-talk-still-bypasses-action-llm",
                direct.get("route") == "INTERACTION" and direct.get("ai_allowed") is False,
                f"route={direct.get('route')}",
            )

            semantic = classify_v71_input(actor, SEMANTIC_INTERACTION_PHRASE)
            check(
                "semantic-social-phrase-reaches-structured-proposal-route",
                semantic.get("route") == "AI_ACTION_PROPOSAL" and semantic.get("ai_allowed") is True,
                f"route={semantic.get('route')} phrase={SEMANTIC_INTERACTION_PHRASE!r}",
            )

            request = build_action_proposal_request(actor, SEMANTIC_INTERACTION_PHRASE)
            catalog = list(request.get("catalog") or [])
            mara_cap = next(
                (
                    row
                    for row in catalog
                    if row.get("kind") == "INTERACTION" and int(row.get("target_dbref") or 0) == int(mara.id)
                ),
                None,
            )
            analyze_cap = next((row for row in catalog if row.get("object_action_id") == ANALYZE_ACTION_ID), None)
            movement_cap = next((row for row in catalog if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == "salir a la calle"), None)
            check(
                "snapshot-contains-exact-visible-mara-talk-capability-plus-regression-capabilities",
                mara_cap is not None and analyze_cap is not None and movement_cap is not None,
                f"talk={(mara_cap or {}).get('capability_id')} analyze={bool(analyze_cap)} movement={bool(movement_cap)} catalog={len(catalog)}",
            )
            if not mara_cap or not analyze_cap or not movement_cap:
                raise RuntimeError("required v0.73 capabilities missing")

            actor_key = f"DBREF:{int(actor.id)}"
            mara_key = str(getattr(mara.db, "npc_id", "") or f"DBREF:{int(mara.id)}")

            before_actor_fam = _relationship_familiarity(actor, mara_key)
            before_mara_fam = _relationship_familiarity(mara, actor_key)
            low = execute_validated_interaction_proposal(
                actor,
                _accepted_result(mara_cap, MIN_EXECUTION_CONFIDENCE - 0.01),
            )
            check(
                "interaction-bridge-rejects-low-confidence-without-memory-or-relationship-mutation",
                low.get("status") == "LOW_CONFIDENCE"
                and not low.get("executed")
                and _clone(getattr(actor.db, "memories", [])) == original_memories
                and _clone(getattr(actor.db, "relationships", {})) == original_relationships
                and _clone(getattr(mara.db, "memories", [])) == original_mara_memories
                and _clone(getattr(mara.db, "relationships", {})) == original_mara_relationships,
                f"status={low.get('status')}",
            )

            other_room = next(
                (getattr(exit_obj, "destination", None) for exit_obj in list(getattr(site, "exits", []) or []) if getattr(exit_obj, "destination", None)),
                None,
            )
            if not other_room:
                raise RuntimeError("alternate room missing for npc stale test")
            mara.move_to(other_room, quiet=True)
            stale = execute_validated_interaction_proposal(actor, _accepted_result(mara_cap, 1.0))
            check(
                "talk-proposal-is-revalidated-and-rejected-if-npc-moves-during-llm-delay",
                stale.get("status") == "STALE_OR_MISSING_CAPABILITY"
                and not stale.get("executed")
                and actor.location == site
                and mara.location == other_room
                and _clone(getattr(actor.db, "memories", [])) == original_memories,
                f"status={stale.get('status')} mara_location={mara.location.key if mara.location else None}",
            )
            mara.move_to(site, quiet=True)

            fixture = handle_action_proposal_result_v73(actor, _accepted_result(mara_cap, 1.0), emit_messages=False)
            actor_memory = _latest_memory(actor)
            mara_memory = _latest_memory(mara)
            after_actor_fam = _relationship_familiarity(actor, mara_key)
            after_mara_fam = _relationship_familiarity(mara, actor_key)
            check(
                "fresh-talk-capability-enters-existing-interaction-engine-and-records-semantic-social-state",
                fixture.get("status") == "INTERACTION_EXECUTED"
                and fixture.get("executed") is True
                and actor_memory.get("type") == "conversation"
                and actor_memory.get("with_name") == mara.key
                and mara_memory.get("type") == "conversation"
                and mara_memory.get("with_name") == actor.key
                and after_actor_fam == before_actor_fam + 1
                and after_mara_fam == before_mara_fam + 1,
                f"status={fixture.get('status')} actor_familiarity={after_actor_fam} mara_familiarity={after_mara_fam}",
            )

            fixture_text = str(fixture.get("rendered_text") or "")
            check(
                "interaction-feedback-comes-from-existing-engine-and-not-model-reason-or-private-facts",
                bool(fixture_text)
                and "validator-model-reason-never-render" not in fixture_text
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts
                and _clone(getattr(mara.db, "knowledge", {})) == original_mara_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == original_mara_facts,
                f"text={fixture_text!r}",
            )

            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships

            self.caller.msg(
                f"LIVE V073 INTERACTION PROBE: action={SEMANTIC_INTERACTION_PHRASE!r} target={mara.key!r}"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-exact-visible-mara-interaction-capability",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and _proposal_kind(live) == "INTERACTION"
                and str((live.get("proposal") or {}).get("capability_id") or "") == str(mara_cap.get("capability_id") or "")
                and float((live.get("proposal") or {}).get("confidence") or 0) >= MIN_EXECUTION_CONFIDENCE,
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            before_live_actor_fam = _relationship_familiarity(actor, mara_key)
            before_live_mara_fam = _relationship_familiarity(mara, actor_key)
            before_live_obj = len(object_action_history(actor))
            before_live_res = len(action_resolution_history(actor))
            live_handled = handle_action_proposal_result_v73(actor, live, emit_messages=False)
            live_actor_memory = _latest_memory(actor)
            live_mara_memory = _latest_memory(mara)
            check(
                "live-structured-interaction-revalidates-and-executes-existing-talk-engine",
                live_handled.get("status") == "INTERACTION_EXECUTED"
                and live_handled.get("executed") is True
                and live_actor_memory.get("with_name") == mara.key
                and live_mara_memory.get("with_name") == actor.key
                and _relationship_familiarity(actor, mara_key) == before_live_actor_fam + 1
                and _relationship_familiarity(mara, actor_key) == before_live_mara_fam + 1,
                f"handler={live_handled.get('status')} text={live_handled.get('rendered_text')!r}",
            )

            check(
                "live-interaction-does-not-create-action-history-copy-model-reason-or-transfer-facts",
                len(object_action_history(actor)) == before_live_obj
                and len(action_resolution_history(actor)) == before_live_res
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts
                and _clone(getattr(mara.db, "knowledge", {})) == original_mara_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == original_mara_facts
                and str((live.get("proposal") or {}).get("reason") or "") not in json.dumps(live_handled, ensure_ascii=False),
                "histories_unchanged=True facts_unchanged=True model_reason_not_forwarded=True",
            )

            self.caller.msg("--- LIVE V073 INTERACTION RESULT ---")
            self.caller.msg(json.dumps({
                "proposal": live.get("proposal"),
                "handler_status": live_handled.get("status"),
                "target": (live_handled.get("bridge") or {}).get("target_name"),
                "response_text": live_handled.get("rendered_text"),
            }, ensure_ascii=False, sort_keys=True))
            self.caller.msg("--- END LIVE V073 INTERACTION RESULT ---")

            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            object_regression = handle_action_proposal_result_v73(
                actor,
                _accepted_result(analyze_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v073-preserves-object-action-bridge",
                object_regression.get("status") == "WORLD_ENGINE_ACCEPTED"
                and (object_regression.get("bridge") or {}).get("world_engine_status") == "PENDING_RESOLUTION"
                and len(object_action_history(actor)) == before_obj + 1
                and len(action_resolution_history(actor)) == before_res + 1,
                f"status={object_regression.get('status')} engine={(object_regression.get('bridge') or {}).get('world_engine_status')}",
            )
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            movement_regression = handle_action_proposal_result_v73(
                actor,
                _accepted_result(movement_cap, 1.0),
                emit_messages=False,
            )
            check(
                "v073-preserves-real-exit-movement-bridge",
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
            "PERSISTENT SYSTEM RETAINED: structured INTERACTION may select a current visible NPC, but existing interaction engine owns greeting, memory and relationship mutation; semantic topics remain disabled"
        )
        self.caller.msg("========================================================")
