from evennia import Command
from evennia.utils import logger

from commands.siza_commands import _format_roll
from commands.world_input_v741_commands import classify_v741_input
from commands.world_input_v74_commands import _clone
from commands.world_input_v77_commands import (
    CmdSizaNoMatchV77,
    SEMANTIC_ACTIVE_SEARCH_PHRASE,
)
from services.action_resolution_engine import action_resolution_history
from services.active_perception_proposal_runtime import build_active_perception_proposal_request
from services.deterministic_active_perception_engine import (
    DETERMINISTIC_ACTIVE_PERCEPTION_BUILD,
    execute_deterministic_active_perception,
)
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.object_action_engine import object_action_history
from services.ollama_narrator import narrate_perception_async
from services.perception_engine import parse_perception_intent
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_DETERMINISTIC_PERCEPTION_BUILD = "0.78.0-deterministic-semantic-perception-parity"
DETERMINISTIC_SEARCH_PHRASE = "reviso detrás del mostrador"
TEST_PERCEPTION_FACT_ID = "FACT-V078-PESCADERIA-DETERMINISTIC-001"
TEST_KNOWLEDGE_FACT_ID = "KFACT-V078-PESCADERIA-DETERMINISTIC-001"
TEST_KNOWLEDGE_KEY = "V078_PESCADERIA_DETERMINISTIC"
TEST_DISCOVERY_TEXT = "Debajo del mostrador detectas una rozadura reciente que continúa hacia el zócalo."
TEST_KNOWLEDGE_TEXT = "Una rozadura reciente bajo el mostrador de la pescadería continúa hacia el zócalo."
LEGACY_FACT_ID = "FACT-V078-LEGACY-ONLY-001"
MALFORMED_FACT_ID = "FACT-V078-MALFORMED-001"


def _projectable_fact(perception_fact_id=TEST_PERCEPTION_FACT_ID):
    return {
        "id": perception_fact_id,
        "sense": "sight",
        "target": "mostrador",
        "keywords": ["mostrador", "debajo", "zócalo", "rozadura"],
        "fact": TEST_DISCOVERY_TEXT,
        "difficulty": 1,
        "knowledge_fact": {
            "id": TEST_KNOWLEDGE_FACT_ID,
            "topic": "rozadura bajo mostrador",
            "text": TEST_KNOWLEDGE_TEXT,
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "required_level": 1,
            "canon_status": "prototype",
        },
        "knowledge": {
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "mode": "MAX",
            "value": 1,
        },
    }


def _legacy_fact():
    return {
        "id": LEGACY_FACT_ID,
        "sense": "sight",
        "target": "mostrador",
        "keywords": ["mostrador"],
        "fact": "Encuentras una astilla vieja bajo el mostrador.",
        "difficulty": 1,
    }


def _malformed_fact():
    item = _projectable_fact(MALFORMED_FACT_ID)
    item["knowledge_fact"] = dict(item["knowledge_fact"])
    item["knowledge_fact"]["id"] = "KFACT-V078-MALFORMED-001"
    item["knowledge_fact"]["knowledge_key"] = "V078_WRONG_KEY"
    return item


def _emit_deterministic_perception(actor, packet):
    result = dict((packet or {}).get("result") or {})
    roll_line = _format_roll(result)
    if roll_line:
        actor.msg(roll_line)
    narrate_perception_async(actor, result)


class CmdSizaNoMatchV78(CmdSizaNoMatchV77):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        classification = classify_v741_input(self.caller, raw)
        if classification.get("route") == "PERCEPTION":
            intent = parse_perception_intent(raw)
            if intent and bool(intent.get("active_search")):
                packet = execute_deterministic_active_perception(self.caller, raw)
                if packet.get("status") == "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED" and packet.get("executed") is True:
                    _emit_deterministic_perception(self.caller, packet)
                    return None
                logger.log_err(
                    f"SIZA deterministic active perception failed before render: status={packet.get('status')}"
                )
                self.caller.msg("\nNo entiendo esa acción todavía.")
                return None
        return super().func()


class CmdSizaValidateV78(Command):
    key = "siza-validate-v78"
    aliases = ["validate-v78"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.78 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.78 | {NATURAL_DETERMINISTIC_PERCEPTION_BUILD} ===")
        self.caller.msg(
            "deterministic active search -> existing perception engine -> same authored Knowledge projection as semantic SEARCH"
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
                if str(item) not in {TEST_PERCEPTION_FACT_ID, LEGACY_FACT_ID, MALFORMED_FACT_ID}
            ]
            actor.db.knowledge = {
                str(key): value for key, value in dict(original_knowledge or {}).items()
                if str(key) not in {TEST_KNOWLEDGE_KEY, "V078_WRONG_KEY"}
            }
            actor.db.knowledge_facts = [
                row for row in list(original_facts or [])
                if str((row or {}).get("id") or "") not in {TEST_KNOWLEDGE_FACT_ID, "KFACT-V078-MALFORMED-001"}
            ]
            actor.db.object_action_history = list(original_object_history or [])
            actor.db.action_resolution_history = list(original_resolution_history or [])

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state["analyzed"] = False
            manifest.db.state = manifest_state

            classification = classify_v741_input(actor, DETERMINISTIC_SEARCH_PHRASE)
            intent = parse_perception_intent(DETERMINISTIC_SEARCH_PHRASE)
            check(
                "deterministic-active-search-stays-off-llm-and-parses-same-target",
                classification.get("route") == "PERCEPTION"
                and classification.get("ai_allowed") is False
                and bool(intent)
                and bool(intent.get("active_search"))
                and str(intent.get("target") or "") == "mostrador",
                f"route={classification.get('route')} target={(intent or {}).get('target')!r}",
            )

            site.db.perception_facts = [_projectable_fact()]
            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            before_memories = _clone(getattr(actor.db, "memories", []))
            before_relationships = _clone(getattr(actor.db, "relationships", {}))

            real_cmd = CmdSizaNoMatchV78()
            real_cmd.caller = actor
            real_cmd.args = DETERMINISTIC_SEARCH_PHRASE
            real_cmd.raw_string = DETERMINISTIC_SEARCH_PHRASE
            real_cmd.cmdstring = real_cmd.key
            real_cmd.func()

            check(
                "real-nomatch-deterministic-search-now-persists-discovery-and-knowledge",
                TEST_PERCEPTION_FACT_ID in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and int(dict(getattr(actor.db, "knowledge", {}) or {}).get(TEST_KNOWLEDGE_KEY, 0) or 0) >= 1
                and any(
                    str((row or {}).get("id") or "") == TEST_KNOWLEDGE_FACT_ID
                    for row in list(getattr(actor.db, "knowledge_facts", []) or [])
                )
                and len(object_action_history(actor)) == before_obj
                and len(action_resolution_history(actor)) == before_res
                and _clone(getattr(actor.db, "memories", [])) == before_memories
                and _clone(getattr(actor.db, "relationships", {})) == before_relationships,
                f"knowledge={dict(getattr(actor.db, 'knowledge', {}) or {}).get(TEST_KNOWLEDGE_KEY)}",
            )

            retrieval = retrieve_known_facts(actor, query="rozadura mostrador")
            check(
                "deterministic-discovery-is-immediately-available-to-normal-fact-retrieval",
                TEST_KNOWLEDGE_FACT_ID in list(retrieval.get("selected_fact_ids") or [])
                and TEST_KNOWLEDGE_TEXT in str(retrieval.get("context_text") or ""),
                f"selected={retrieval.get('selected_fact_ids')}",
            )

            after_first_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            after_first_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            after_first_facts = _clone(getattr(actor.db, "knowledge_facts", []))
            repeat = execute_deterministic_active_perception(actor, DETERMINISTIC_SEARCH_PHRASE)
            fact_count = sum(
                1 for row in list(getattr(actor.db, "knowledge_facts", []) or [])
                if str((row or {}).get("id") or "") == TEST_KNOWLEDGE_FACT_ID
            )
            check(
                "repeat-deterministic-search-is-idempotent-across-discovery-and-knowledge",
                repeat.get("status") == "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED"
                and repeat.get("engine_status") == "NO_AUTHORIZED_DISCOVERY"
                and _clone(getattr(actor.db, "discovered_facts", [])) == after_first_discovered
                and _clone(getattr(actor.db, "knowledge", {})) == after_first_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == after_first_facts
                and fact_count == 1,
                f"engine={repeat.get('engine_status')} fact_count={fact_count}",
            )

            clean_discovered = [item for item in list(original_discovered or []) if str(item) != LEGACY_FACT_ID]
            actor.db.discovered_facts = clean_discovered
            actor.db.knowledge = _clone(original_knowledge)
            actor.db.knowledge_facts = _clone(original_facts)
            site.db.perception_facts = [_legacy_fact()]
            legacy = execute_deterministic_active_perception(actor, DETERMINISTIC_SEARCH_PHRASE)
            check(
                "deterministic-legacy-perception-fact-keeps-discovered-only-behavior",
                legacy.get("status") == "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED"
                and legacy.get("engine_status") == "DISCOVERY"
                and LEGACY_FACT_ID in [str(item) for item in list(getattr(actor.db, "discovered_facts", []) or [])]
                and (legacy.get("knowledge_projection") or {}).get("status") == "NO_PROJECTION"
                and _clone(getattr(actor.db, "knowledge", {})) == _clone(original_knowledge)
                and _clone(getattr(actor.db, "knowledge_facts", [])) == _clone(original_facts),
                f"projection={(legacy.get('knowledge_projection') or {}).get('status')}",
            )

            actor.db.discovered_facts = [item for item in list(original_discovered or []) if str(item) != MALFORMED_FACT_ID]
            actor.db.knowledge = _clone(original_knowledge)
            actor.db.knowledge_facts = _clone(original_facts)
            site.db.perception_facts = [_malformed_fact()]
            before_bad_discovered = _clone(getattr(actor.db, "discovered_facts", []))
            before_bad_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            before_bad_facts = _clone(getattr(actor.db, "knowledge_facts", []))
            malformed = execute_deterministic_active_perception(actor, DETERMINISTIC_SEARCH_PHRASE)
            check(
                "malformed-deterministic-projection-rolls-back-discovery-and-knowledge",
                malformed.get("status") == "PROJECTION_FAILED"
                and malformed.get("restored") is True
                and _clone(getattr(actor.db, "discovered_facts", [])) == before_bad_discovered
                and _clone(getattr(actor.db, "knowledge", {})) == before_bad_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == before_bad_facts,
                f"error={(malformed.get('knowledge_projection') or {}).get('error')}",
            )

            actor.db.discovered_facts = _clone(original_discovered)
            actor.db.knowledge = _clone(original_knowledge)
            actor.db.knowledge_facts = _clone(original_facts)
            site.db.perception_facts = [_projectable_fact()]
            visible_before = _clone(getattr(actor.db, "discovered_facts", []))
            visible = execute_deterministic_active_perception(actor, "observo a Mara")
            check(
                "deterministic-visible-observe-remains-auto-success-without-discovery",
                visible.get("status") == "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED"
                and visible.get("engine_status") == "AUTO_SUCCESS"
                and _clone(getattr(actor.db, "discovered_facts", [])) == visible_before
                and (visible.get("knowledge_projection") or {}).get("status") in {"NO_DISCOVERIES", "NO_PROJECTION"},
                f"engine={visible.get('engine_status')}",
            )

            semantic = classify_v741_input(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            request = build_active_perception_proposal_request(actor, SEMANTIC_ACTIVE_SEARCH_PHRASE)
            check(
                "semantic-active-search-still-uses-v077-qwen-room-search-path",
                semantic.get("route") == "AI_ACTION_PROPOSAL"
                and semantic.get("ai_allowed") is True
                and str((request.get("room_search_capability") or {}).get("capability_id") or "").startswith("SEARCH:ROOM:"),
                f"route={semantic.get('route')} search={(request.get('room_search_capability') or {}).get('capability_id')}",
            )

            explicit_talk = classify_v741_input(actor, "hablo con Mara sobre manifiesto duplicado")
            check(
                "v078-preserves-explicit-talk-precedence",
                explicit_talk.get("route") == "INTERACTION" and explicit_talk.get("ai_allowed") is False,
                f"route={explicit_talk.get('route')}",
            )

            object_route = classify_v741_input(actor, "analizo el manifiesto")
            check(
                "v078-does-not-steal-authored-object-action-routing",
                object_route.get("route") in {"OBJECT_ACTION", "AI_ACTION_PROPOSAL"}
                and object_route.get("route") != "PERCEPTION",
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
            "PERSISTENT SYSTEM RETAINED: deterministic and semantic active perception now converge on the same authored discovery-to-Knowledge semantics"
        )
        self.caller.msg("========================================================")
