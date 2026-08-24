from evennia import Command
from evennia.utils import logger

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v80_commands import (
    CmdSizaNoMatchV80,
    CmdSizaValidateV80,
    SEMANTIC_ASK_PHRASE,
    handle_action_proposal_result_v80,
)
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT, call_prebuilt_action_proposal
from services.active_perception_proposal_runtime import (
    build_active_perception_proposal_request,
    dispatch_active_perception_proposal_async,
)
from services.knowledge_context_engine import fact_knowledge_state, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_CONVERSATION_ACQUISITION_WIRING_BUILD = "0.80.1-semantic-talk-acquisition-async-wiring"
WIRING_FACT_ID = "KFACT-V0801-MARA-WIRING-001"
WIRING_KNOWLEDGE_KEY = "V0801_MARA_WIRING"
WIRING_TOPIC = "registro del relevo nocturno"
WIRING_TEXT = "Mara confirma que el registro del relevo nocturno fue firmado después del cierre de la dársena."
WIRING_PRIVATE_SENTINEL = "NEVER_LEAK_V0801_WIRING_FACT"


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


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.80.1 action proposal runtime failure: {failure}")
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
    return failure


def dispatch_unknown_action_v801(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v80(
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


class CmdSizaNoMatchV801(CmdSizaNoMatchV80):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v801(self.caller, raw)
            return None
        return super().func()


class CmdSizaValidateV801(Command):
    key = "siza-validate-v801"
    aliases = ["validate-v801"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.80.1 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
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
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.80.1 | {NATURAL_CONVERSATION_ACQUISITION_WIRING_BUILD} ===")
        self.caller.msg("targeted wiring: semantic AI_ACTION_PROPOSAL -> v0.80 callback -> NPC Fact becomes player Knowledge")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            actor.db.knowledge = {str(k): v for k, v in dict(original_actor_knowledge or {}).items() if str(k) != WIRING_KNOWLEDGE_KEY}
            actor.db.knowledge_facts = [row for row in list(original_actor_facts or []) if str((row or {}).get("id") or "") != WIRING_FACT_ID]
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)
            mara.db.knowledge = {WIRING_KNOWLEDGE_KEY: 1}
            mara.db.knowledge_facts = []
            mara.db.memories = _clone(original_mara_memories)
            mara.db.relationships = _clone(original_mara_relationships)
            upsert_knowledge_fact(
                mara,
                {
                    "id": WIRING_FACT_ID,
                    "topic": WIRING_TOPIC,
                    "aliases": ["relevo nocturno", "registro del relevo"],
                    "text": WIRING_TEXT,
                    "knowledge_key": WIRING_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"validator_private_sentinel": WIRING_PRIVATE_SENTINEL},
                    "learned_by": {"provider": "V0801_VALIDATOR"},
                },
            )
            set_knowledge_level(mara, WIRING_KNOWLEDGE_KEY, 1)

            classification = classify_v741_input(actor, SEMANTIC_ASK_PHRASE)
            check(
                "semantic-topic-talk-is-owned-by-ai-proposal-route-before-v0801-dispatch",
                classification.get("route") == "AI_ACTION_PROPOSAL" and classification.get("ai_allowed") is True,
                f"route={classification.get('route')}",
            )

            request = build_active_perception_proposal_request(actor, SEMANTIC_ASK_PHRASE)
            request_text = str(request.get("ollama_payload") or {})
            check(
                "v0801-provider-boundary-still-excludes-npc-fact-state",
                WIRING_FACT_ID not in request_text and WIRING_TEXT not in request_text and WIRING_PRIVATE_SENTINEL not in request_text,
                f"private_leaked={WIRING_PRIVATE_SENTINEL in request_text}",
            )

            self.caller.msg(f"LIVE V0801 SEMANTIC TALK ACQUISITION PROBE: action={SEMANTIC_ASK_PHRASE!r}")
            live = call_prebuilt_action_proposal(request, timeout=60)
            check(
                "live-qwen-selects-an-interaction-capability-for-semantic-question",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and str((live.get("proposal") or {}).get("kind") or "") == "INTERACTION",
                f"status={live.get('status')} proposal={live.get('proposal')}",
            )

            handled = handle_action_proposal_result_v80(
                actor,
                live,
                raw_player_input=SEMANTIC_ASK_PHRASE,
                emit_messages=False,
            )
            acquired = find_knowledge_fact(actor, WIRING_FACT_ID)
            check(
                "live-semantic-callback-acquires-exact-npc-fact-into-player-knowledge",
                handled.get("status") == "INTERACTION_EXECUTED"
                and (handled.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired is not None
                and fact_knowledge_state(actor, acquired).get("known") is True
                and acquired.get("text") == WIRING_TEXT,
                f"handler={handled.get('status')} acquisition={(handled.get('knowledge_acquisition') or {}).get('status')}",
            )

            reason = str((live.get("proposal") or {}).get("reason") or "")
            persistent = str(_clone({
                "fact": acquired,
                "memories": getattr(actor.db, "memories", []),
                "relationships": getattr(actor.db, "relationships", {}),
            }))
            check(
                "live-model-reason-is-not-persisted-by-v0801-callback",
                not reason or reason not in persistent,
                "reason_persisted=False",
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

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor/Mara location, Knowledge/Facts and social state restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: V80 owns semantic conversation acquisition callback; older action bridges remain authoritative")
        self.caller.msg("========================================================")
