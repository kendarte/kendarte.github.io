import json

from evennia import Command

from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v82_commands import CmdSizaNoMatchV82
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.player_knowledge_query_engine import (
    PLAYER_KNOWLEDGE_QUERY_BUILD,
    parse_player_knowledge_query,
    query_player_known_facts,
)
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_PLAYER_KNOWLEDGE_QUERY_BUILD = "0.83.0-natural-deterministic-player-knowledge-query"
TEST_FACT_ID = "KFACT-V083-PLAYER-ARRASTRE-VERDE-001"
TEST_KNOWLEDGE_KEY = "V083_PLAYER_ARRASTRE_VERDE"
TEST_TOPIC = "marca de arrastre verde bajo mostrador"
TEST_TEXT = "La marca de arrastre verde termina junto al zócalo de la pescadería."
PRIVATE_FACT_ID = "KFACT-V083-PRIVATE-ARRASTRE-VERDE-001"
PRIVATE_KNOWLEDGE_KEY = "V083_PRIVATE_ARRASTRE_VERDE"
PRIVATE_SENTINEL = "NEVER_LEAK_V083_UNKNOWN_FACT"
SECOND_FACT_ID = "KFACT-V083-PLAYER-ARRASTRE-VERDE-002"
SECOND_KNOWLEDGE_KEY = "V083_PLAYER_ARRASTRE_VERDE_SECOND"
SECOND_TEXT = "La rozadura verde también cruza el borde inferior del mostrador."
QUERY = "¿Qué sé sobre la marca de arrastre verde?"
GENERAL_INQUIRY = "¿Por qué hay una marca de arrastre verde?"


def classify_v83_input(actor, raw):
    intent = parse_player_knowledge_query(raw)
    if intent:
        return {
            "build": NATURAL_PLAYER_KNOWLEDGE_QUERY_BUILD,
            "route": "KNOWLEDGE_QUERY",
            "raw": str(raw or "").strip(),
            "ai_allowed": False,
            "mutation_requires_bridge": False,
            "intent": intent,
        }
    base = classify_v741_input(actor, raw)
    return {**base, "build": NATURAL_PLAYER_KNOWLEDGE_QUERY_BUILD}


class CmdSizaNoMatchV83(CmdSizaNoMatchV82):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v83_input(self.caller, raw)
        if classification.get("route") == "KNOWLEDGE_QUERY":
            packet = query_player_known_facts(self.caller, raw)
            text = str(packet.get("response_text") or "").strip()
            if text:
                self.caller.msg("\n" + text)
            return None
        return super().func()


class CmdSizaValidateV83(Command):
    key = "siza-validate-v83"
    aliases = ["validate-v83"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.83 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        original_location = actor.location
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_memories = _clone(getattr(actor.db, "memories", []))
        original_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_discovered = _clone(getattr(actor.db, "discovered_facts", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.83 | {NATURAL_PLAYER_KNOWLEDGE_QUERY_BUILD} ===")
        self.caller.msg(
            "explicit first-person Knowledge query -> deterministic known-Fact retrieval -> public text only -> no Ollama and no mutation"
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
            actor.db.object_action_history = _clone(original_object_history)
            actor.db.action_resolution_history = _clone(original_resolution_history)

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
                    "source": {"validator": "v0.83-known"},
                    "learned_by": {"provider": "V083_VALIDATOR"},
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
                    "learned_by": {"provider": "V083_PRIVATE_VALIDATOR"},
                },
            )
            set_knowledge_level(actor, TEST_KNOWLEDGE_KEY, 1)
            set_knowledge_level(actor, PRIVATE_KNOWLEDGE_KEY, 0)

            parsed = parse_player_knowledge_query(QUERY)
            check(
                "first-person-knowledge-question-parses-to-filtered-player-authored-topic",
                parsed is not None
                and parsed.get("intent") == "QUERY_KNOWLEDGE"
                and parsed.get("topic") == "la marca de arrastre verde"
                and parsed.get("retrieval_query") == "marca arrastre verde",
                f"topic={(parsed or {}).get('topic')!r} query={(parsed or {}).get('retrieval_query')!r}",
            )

            route = classify_v83_input(actor, QUERY)
            check(
                "knowledge-question-now-bypasses-ollama-with-deterministic-route",
                route.get("route") == "KNOWLEDGE_QUERY"
                and route.get("ai_allowed") is False
                and route.get("mutation_requires_bridge") is False,
                f"route={route.get('route')} ai={route.get('ai_allowed')}",
            )

            general = classify_v83_input(actor, GENERAL_INQUIRY)
            check(
                "general-world-question-still-uses-existing-grounded-ai-inquiry",
                general.get("route") == "AI_INQUIRY" and general.get("ai_allowed") is True,
                f"route={general.get('route')}",
            )

            talk = classify_v83_input(actor, "hablo con Mara sobre el manifiesto duplicado")
            check(
                "explicit-talk-precedence-remains-unchanged",
                talk.get("route") == "INTERACTION" and talk.get("ai_allowed") is False,
                f"route={talk.get('route')}",
            )

            before_query_state = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "discovered": getattr(actor.db, "discovered_facts", []),
                    "object_history": getattr(actor.db, "object_action_history", []),
                    "resolution_history": getattr(actor.db, "action_resolution_history", []),
                }
            )
            packet = query_player_known_facts(actor, QUERY)
            after_query_state = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "discovered": getattr(actor.db, "discovered_facts", []),
                    "object_history": getattr(actor.db, "object_action_history", []),
                    "resolution_history": getattr(actor.db, "action_resolution_history", []),
                }
            )
            public_blob = json.dumps(packet, ensure_ascii=False)
            check(
                "deterministic-query-returns-only-the-known-matching-fact",
                packet.get("status") == "KNOWN_FACTS_FOUND"
                and packet.get("fact_count") == 1
                and packet.get("response_text") == TEST_TEXT
                and TEST_TEXT in public_blob
                and PRIVATE_SENTINEL not in public_blob,
                f"status={packet.get('status')} count={packet.get('fact_count')}",
            )
            check(
                "knowledge-query-exposes-no-fact-ids-provenance-or-knowledge-keys",
                TEST_FACT_ID not in public_blob
                and PRIVATE_FACT_ID not in public_blob
                and TEST_KNOWLEDGE_KEY not in public_blob
                and PRIVATE_KNOWLEDGE_KEY not in public_blob
                and "learned_by" not in public_blob
                and "source" not in public_blob,
                "public_packet_is_sanitized=True",
            )
            check(
                "knowledge-query-is-exactly-read-only",
                before_query_state == after_query_state,
                f"build={PLAYER_KNOWLEDGE_QUERY_BUILD}",
            )

            captured = []
            original_msg = actor.msg

            def capture_msg(text=None, *args, **kwargs):
                captured.append(str(text or ""))

            actor.msg = capture_msg
            try:
                cmd = CmdSizaNoMatchV83()
                cmd.caller = actor
                cmd.args = QUERY
                cmd.raw_string = QUERY
                cmd.cmdstring = cmd.key
                cmd.func()
            finally:
                actor.msg = original_msg

            rendered = "\n".join(captured)
            check(
                "real-v083-nomatch-renders-authoritative-known-text-without-debug-metadata",
                TEST_TEXT in rendered
                and PRIVATE_SENTINEL not in rendered
                and TEST_FACT_ID not in rendered
                and PRIVATE_FACT_ID not in rendered,
                f"rendered={rendered!r}",
            )

            actor.db.knowledge = {PRIVATE_KNOWLEDGE_KEY: 0}
            actor.db.knowledge_facts = []
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
                },
            )
            set_knowledge_level(actor, PRIVATE_KNOWLEDGE_KEY, 0)
            none = query_player_known_facts(actor, QUERY)
            check(
                "unknown-matching-facts-produce-safe-no-knowledge-response",
                none.get("status") == "NO_KNOWN_FACTS"
                and none.get("fact_count") == 0
                and PRIVATE_SENTINEL not in str(none.get("response_text") or ""),
                f"status={none.get('status')} text={none.get('response_text')!r}",
            )

            actor.db.knowledge = {
                TEST_KNOWLEDGE_KEY: 1,
                SECOND_KNOWLEDGE_KEY: 1,
            }
            actor.db.knowledge_facts = []
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
                },
            )
            upsert_knowledge_fact(
                actor,
                {
                    "id": SECOND_FACT_ID,
                    "topic": "marca de arrastre verde junto al zocalo",
                    "aliases": ["arrastre verde", "marca verde"],
                    "text": SECOND_TEXT,
                    "knowledge_key": SECOND_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                },
            )
            set_knowledge_level(actor, TEST_KNOWLEDGE_KEY, 1)
            set_knowledge_level(actor, SECOND_KNOWLEDGE_KEY, 1)
            multi = query_player_known_facts(actor, QUERY)
            check(
                "multiple-known-relevant-facts-are-returned-without-invented-summary",
                multi.get("status") == "KNOWN_FACTS_FOUND"
                and multi.get("fact_count") == 2
                and TEST_TEXT in str(multi.get("response_text") or "")
                and SECOND_TEXT in str(multi.get("response_text") or ""),
                f"count={multi.get('fact_count')}",
            )

            object_route = classify_v83_input(actor, "analizar manifiesto")
            perception_route = classify_v83_input(actor, "observo a Mara")
            movement_route = classify_v83_input(actor, "salir a la calle")
            check(
                "non-knowledge-object-perception-and-movement-routing-remains-unchanged",
                object_route.get("route") == "OBJECT_ACTION"
                and perception_route.get("route") == "PERCEPTION"
                and movement_route.get("route") == "MOVEMENT",
                f"object={object_route.get('route')} perception={perception_route.get('route')} movement={movement_route.get('route')}",
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
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor location, Knowledge/Facts, memories, relationships, discoveries and action histories restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: first-person Knowledge inspection is deterministic/read-only; general inquiries still use existing viewer-grounded narration"
        )
        self.caller.msg("========================================================")
