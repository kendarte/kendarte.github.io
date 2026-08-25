import json

from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v83_commands import (
    PRIVATE_FACT_ID,
    PRIVATE_KNOWLEDGE_KEY,
    PRIVATE_SENTINEL,
    QUERY,
    TEST_FACT_ID,
    TEST_KNOWLEDGE_KEY,
    TEST_TEXT,
    TEST_TOPIC,
)
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.player_knowledge_query_engine import query_player_known_facts
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V0831_VALIDATION_BUILD = "0.83.1-targeted-structural-public-packet-privacy"
_FORBIDDEN_FACT_KEYS = {
    "id",
    "fact_id",
    "knowledge_key",
    "knowledge_level",
    "required_level",
    "source",
    "learned_by",
    "transfer_history",
    "relevance_score",
    "relevance_reasons",
    "context_line",
}
_ALLOWED_TOP_LEVEL_KEYS = {
    "status",
    "handled",
    "topic",
    "topic_source",
    "retrieval_query",
    "retrieval_query_source",
    "facts",
    "fact_count",
    "response_text",
    "build",
}
_ALLOWED_FACT_KEYS = {"topic", "text"}


def _forbidden_keys(value, path="root"):
    hits = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = str(key)
            if name in _FORBIDDEN_FACT_KEYS:
                hits.append(f"{path}.{name}")
            hits.extend(_forbidden_keys(item, f"{path}.{name}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            hits.extend(_forbidden_keys(item, f"{path}[{index}]"))
    return hits


class CmdSizaValidateV831(Command):
    key = "siza-validate-v831"
    aliases = ["validate-v831"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.83.1 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        original_location = actor.location
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_memories = _clone(getattr(actor.db, "memories", []))
        original_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_discovered = _clone(getattr(actor.db, "discovered_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.83.1 | {V0831_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted rerun: validate public Knowledge-query packet structurally; topic_source fields are metadata, not Fact provenance"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)

            actor.db.knowledge = {
                TEST_KNOWLEDGE_KEY: 1,
                PRIVATE_KNOWLEDGE_KEY: 0,
            }
            actor.db.knowledge_facts = []
            actor.db.memories = _clone(original_memories)
            actor.db.relationships = _clone(original_relationships)
            actor.db.discovered_facts = _clone(original_discovered)

            upsert_knowledge_fact(
                actor,
                {
                    "id": TEST_FACT_ID,
                    "topic": TEST_TOPIC,
                    "aliases": ["arrastre verde", "marca verde"],
                    "text": TEST_TEXT,
                    "knowledge_key": TEST_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"validator": "v0.83.1-known"},
                    "learned_by": {"provider": "V0831_VALIDATOR"},
                },
            )
            upsert_knowledge_fact(
                actor,
                {
                    "id": PRIVATE_FACT_ID,
                    "topic": TEST_TOPIC,
                    "aliases": ["arrastre verde", "marca verde"],
                    "text": f"{PRIVATE_SENTINEL}: detalle que el jugador todavía no conoce.",
                    "knowledge_key": PRIVATE_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"private": PRIVATE_SENTINEL},
                    "learned_by": {"provider": "V0831_PRIVATE_VALIDATOR"},
                },
            )
            set_knowledge_level(actor, TEST_KNOWLEDGE_KEY, 1)
            set_knowledge_level(actor, PRIVATE_KNOWLEDGE_KEY, 0)

            before = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "discovered": getattr(actor.db, "discovered_facts", []),
                }
            )
            packet = query_player_known_facts(actor, QUERY)
            after = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "discovered": getattr(actor.db, "discovered_facts", []),
                }
            )

            top_keys = set(str(key) for key in packet.keys())
            fact_rows = list(packet.get("facts") or [])
            check(
                "public-packet-top-level-schema-is-explicitly-allowlisted",
                top_keys == _ALLOWED_TOP_LEVEL_KEYS,
                f"keys={sorted(top_keys)}",
            )

            fact_key_sets = [set(str(key) for key in row.keys()) for row in fact_rows if isinstance(row, dict)]
            forbidden_hits = _forbidden_keys(packet)
            check(
                "public-facts-contain-only-topic-and-text-with-no-structured-provenance",
                bool(fact_rows)
                and all(keys == _ALLOWED_FACT_KEYS for keys in fact_key_sets)
                and not forbidden_hits,
                f"fact_keys={fact_key_sets} forbidden_hits={forbidden_hits}",
            )

            blob = json.dumps(packet, ensure_ascii=False)
            check(
                "unknown-matching-fact-and-private-sentinel-remain-absent-from-public-boundary",
                packet.get("fact_count") == 1
                and packet.get("response_text") == TEST_TEXT
                and PRIVATE_SENTINEL not in blob
                and PRIVATE_FACT_ID not in blob
                and PRIVATE_KNOWLEDGE_KEY not in blob,
                f"count={packet.get('fact_count')} private_leaked={PRIVATE_SENTINEL in blob}",
            )

            check(
                "topic-source-metadata-is-legitimate-and-query-remains-read-only",
                packet.get("topic_source") == "PLAYER_INPUT"
                and packet.get("retrieval_query_source") == "PLAYER_INPUT_FILTERED"
                and before == after,
                f"topic_source={packet.get('topic_source')} retrieval_source={packet.get('retrieval_query_source')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts
            actor.db.memories = original_memories
            actor.db.relationships = original_relationships
            actor.db.discovered_facts = original_discovered

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor location, Knowledge/Facts, memories, relationships and discoveries restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.83 production query packet was already sanitized; v0.83.1 only fixes the validator to distinguish field names ending in _source from actual Fact provenance"
        )
        self.caller.msg("========================================================")
