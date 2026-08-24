from evennia import Command

from commands.world_input_v71_commands import classify_v71_input
from commands.world_input_v74_commands import (
    CmdSizaNoMatchV74,
    SEMANTIC_TOPIC_PHRASE,
    TEST_FACT_ID,
    TEST_FACT_TEXT,
    TEST_KNOWLEDGE_KEY,
    _clone,
    _latest_memory,
)
from services.interaction_engine import parse_interaction_intent, resolve_interaction
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.object_action_engine import object_action_history
from services.action_resolution_engine import action_resolution_history
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_TOPIC_INTERACTION_BUILD = "0.74.1-explicit-talk-precedence"


def classify_v741_input(actor, raw):
    """Explicit deterministic TALK wins before weak object ambiguity can reach qwen."""
    text = str(raw or "").strip()
    interaction = parse_interaction_intent(text)
    if interaction and str(interaction.get("intent") or "") == "TALK":
        return {
            "build": NATURAL_TOPIC_INTERACTION_BUILD,
            "route": "INTERACTION",
            "raw": text,
            "ai_allowed": False,
            "intent": dict(interaction),
            "explicit_talk_precedence": True,
        }
    base = classify_v71_input(actor, text)
    return {**base, "build": NATURAL_TOPIC_INTERACTION_BUILD}


class CmdSizaNoMatchV741(CmdSizaNoMatchV74):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "INTERACTION" and classification.get("explicit_talk_precedence"):
            text = str(resolve_interaction(self.caller, classification.get("intent") or {}) or "").strip()
            if text:
                self.caller.msg("\n" + text)
            return None
        return super().func()


class CmdSizaValidateV741(Command):
    key = "siza-validate-v741"
    aliases = ["validate-v741"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.74.1 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        mara = context.get("mara")
        original_location = actor.location
        original_mara_location = mara.location
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_memories = _clone(getattr(actor.db, "memories", []))
        original_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_memories = _clone(getattr(mara.db, "memories", []))
        original_mara_relationships = _clone(getattr(mara.db, "relationships", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.74.1 | {NATURAL_TOPIC_INTERACTION_BUILD} ===")
        self.caller.msg("targeted rerun: explicit TALK precedence -> existing interaction engine; semantic fallback remains unchanged")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            explicit_raw = "hablo con Mara sobre manifiesto duplicado"
            explicit = classify_v741_input(actor, explicit_raw)
            check(
                "explicit-talk-with-topic-now-stays-deterministic",
                explicit.get("route") == "INTERACTION"
                and explicit.get("ai_allowed") is False
                and explicit.get("explicit_talk_precedence") is True,
                f"route={explicit.get('route')}",
            )

            semantic = classify_v741_input(actor, SEMANTIC_TOPIC_PHRASE)
            check(
                "semantic-topic-phrase-still-reaches-qwen-fallback",
                semantic.get("route") == "AI_ACTION_PROPOSAL" and semantic.get("ai_allowed") is True,
                f"route={semantic.get('route')}",
            )

            # Isolate one modern Fact and prove the exact explicit __nomatch path reaches the existing Knowledge-gated engine.
            mara.db.knowledge = {TEST_KNOWLEDGE_KEY: 1}
            mara.db.knowledge_facts = []
            upsert_knowledge_fact(
                mara,
                {
                    "id": TEST_FACT_ID,
                    "topic": "manifiesto duplicado",
                    "aliases": ["registro duplicado"],
                    "text": TEST_FACT_TEXT,
                    "knowledge_key": TEST_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                },
            )
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            mara.db.memories = original_mara_memories
            mara.db.relationships = original_mara_relationships
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history

            cmd = CmdSizaNoMatchV741()
            cmd.caller = actor
            cmd.args = explicit_raw
            cmd.raw_string = explicit_raw
            cmd.cmdstring = cmd.key
            cmd.func()

            latest = _latest_memory(actor)
            check(
                "real-explicit-nomatch-talk-uses-existing-topic-and-fact-engine-without-action-history",
                latest.get("outcome") == "knowledge_shared"
                and latest.get("topic") == "manifiesto duplicado"
                and latest.get("fact_id") == TEST_FACT_ID
                and latest.get("fact_text") == TEST_FACT_TEXT
                and len(object_action_history(actor)) == len(original_object_history or [])
                and len(action_resolution_history(actor)) == len(original_resolution_history or []),
                f"outcome={latest.get('outcome')} fact_id={latest.get('fact_id')}",
            )

            object_route = classify_v741_input(actor, "analizar manifiesto")
            check(
                "non-talk-object-action-routing-is-unchanged",
                object_route.get("route") == "OBJECT_ACTION",
                f"route={object_route.get('route')}",
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

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor/Mara location, social state, Knowledge/Facts and action histories restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: explicit TALK is deterministic; semantic TALK fallback still uses v0.74 qwen target selection and player-authored topics")
        self.caller.msg("========================================================")
