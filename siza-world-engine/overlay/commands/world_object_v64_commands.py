from evennia import Command

from services.knowledge_context_engine import knowledge_facts, knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.knowledge_fact_retrieval_engine import FACT_RETRIEVAL_BUILD, retrieve_known_facts
from services.npc_simulation import find_npc
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v57 import (
    FACT_ID as SOURCE_FACT_ID,
    FACT_TEXT as SOURCE_FACT_TEXT,
    FACT_TOPIC as SOURCE_FACT_TOPIC,
    KNOWLEDGE_KEY as SOURCE_KNOWLEDGE_KEY,
)
from world.upgrade_pilot_v63 import (
    FACT_ID as DIRECT_FACT_ID,
    FACT_TEXT as DIRECT_FACT_TEXT,
    FACT_TOPIC as DIRECT_FACT_TOPIC,
    KNOWLEDGE_KEY as DIRECT_KNOWLEDGE_KEY,
    ensure_v63_pilot_content,
)


DECOY_FACT_ID = "FACT-V064-UNKNOWN-DECOY-001"
DECOY_KEY = "V064_UNKNOWN_DECOY"
IRRELEVANT_FACT_ID = "FACT-V064-IRRELEVANT-CANTINA-001"
IRRELEVANT_KEY = "V064_IRRELEVANT_CANTINA"
SITE_MATCH_FACT_ID = "FACT-V064-SITE-MATCH-001"
SITE_OTHER_FACT_ID = "FACT-V064-SITE-OTHER-001"
SITE_KEY = "V064_SITE_TEST"
BUDGET_FACT_ID = "FACT-V064-BUDGET-001"
BUDGET_KEY = "V064_BUDGET_TEST"
EMPTY_QUERY_TOKEN = "zzv064nomatchzz"


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


def _source_fact(manifest, site):
    return {
        "id": SOURCE_FACT_ID,
        "topic": SOURCE_FACT_TOPIC,
        "text": SOURCE_FACT_TEXT,
        "knowledge_key": SOURCE_KNOWLEDGE_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": MANIFEST_ID,
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
            "object_dbref": int(manifest.id),
            "site_dbref": int(site.id),
        },
        "learned_by": {
            "object_action_id": "ACT-TEST-PESCADERIA-CONSOLIDAR-HALLAZGO-001",
            "attempt_id": "V064-SOURCE-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V064-SOURCE-SEED",
        },
        "transfer_history": [
            {"id": "V064-HOP-1", "source_name": "admin", "target_name": "Informante de Prueba C"},
            {"id": "V064-HOP-2", "source_name": "Informante de Prueba C", "target_name": "Mara Vensal"},
        ],
    }


def _direct_fact(manifest, site):
    return {
        "id": DIRECT_FACT_ID,
        "topic": DIRECT_FACT_TOPIC,
        "text": DIRECT_FACT_TEXT,
        "knowledge_key": DIRECT_KNOWLEDGE_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": MANIFEST_ID,
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
            "object_dbref": int(manifest.id),
            "site_dbref": int(site.id),
        },
        "learned_by": {
            "action_id": "OBJECT_ACTION_COMPLETED:V064-DIRECT-SEED",
            "object_action_id": "ACT-MARA-VERIFY-MANIFEST-DUPLICATE-001",
            "attempt_id": "V064-DIRECT-SEED",
            "outcome": "COMPLETED",
        },
        "transfer_history": [],
    }


def _seed_fact(entity, fact, level):
    upsert_knowledge_fact(entity, fact)
    set_knowledge_level(entity, fact.get("knowledge_key"), level)


def _fact_ids(packet):
    return list(packet.get("selected_fact_ids") or [])


class CmdSizaFactContextV64(Command):
    key = "siza-fact-context"
    aliases = ["fact-context"]
    locks = "cmd:all()"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|", 1)]
        target = find_npc(parts[0]) if parts and parts[0] else None
        if not target:
            self.caller.msg("Uso: siza-fact-context <NPC> | <consulta>")
            return
        query = parts[1] if len(parts) > 1 else ""
        packet = retrieve_known_facts(target, query=query)
        self.caller.msg(f"=== SIZA FACT CONTEXT | {FACT_RETRIEVAL_BUILD} ===")
        self.caller.msg(
            f"NPC: {target.key} | query={query!r} | site={packet.get('site', {}).get('name')} | "
            f"selected={len(packet.get('selected') or [])} | chars={packet.get('used_chars')}/{packet.get('char_budget')}"
        )
        for row in packet.get("selected") or []:
            self.caller.msg(
                f"  score={row.get('relevance_score')} | {row.get('id')} | reasons={row.get('relevance_reasons')}"
            )
            self.caller.msg(f"    {row.get('context_line')}")
        if not packet.get("selected"):
            self.caller.msg("Context: NONE")
        self.caller.msg(f"Omitted: {packet.get('omitted')}")
        self.caller.msg("========================================================")


class CmdSizaValidateV64(Command):
    key = "siza-validate-v64"
    aliases = ["validate-v64"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.64 VALIDATION] FAIL | context={context}")
            return

        mara = context.get("mara")
        manifest = context.get("manifest")
        site = context.get("destination")
        original_location = mara.location
        original_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.64 | {FACT_RETRIEVAL_BUILD} ===")
        self.caller.msg(f"NPC: {mara.key}#{mara.id} | deterministic read-only Fact context retrieval")

        try:
            if mara.location != site:
                mara.move_to(site, quiet=True)

            _seed_fact(mara, _source_fact(manifest, site), 1)
            _seed_fact(mara, _direct_fact(manifest, site), 1)
            _seed_fact(
                mara,
                {
                    "id": DECOY_FACT_ID,
                    "topic": "manifiesto anotacion duplicada relevo cierre evidencia decisiva",
                    "text": "Este texto no debe entrar nunca porque el NPC no conoce realmente este Fact.",
                    "knowledge_key": DECOY_KEY,
                    "required_level": 1,
                    "source": {"object_id": MANIFEST_ID, "object_name": manifest.key, "site_room_id": str(getattr(site.db, 'room_id', '') or ''), "site_name": site.key},
                },
                0,
            )
            _seed_fact(
                mara,
                {
                    "id": IRRELEVANT_FACT_ID,
                    "topic": "menu de la cantina",
                    "text": "La cantina sirve estofado de pescado durante el cambio de turno.",
                    "knowledge_key": IRRELEVANT_KEY,
                    "required_level": 1,
                    "source": {"site_room_id": "CAR-KAL-DAR-006", "site_name": "Cantina de Turno"},
                },
                1,
            )
            _seed_fact(
                mara,
                {
                    "id": SITE_MATCH_FACT_ID,
                    "topic": "sello operativo",
                    "text": "El sello operativo de prueba coincide con la secuencia observada.",
                    "knowledge_key": SITE_KEY,
                    "required_level": 1,
                    "source": {"site_room_id": str(getattr(site.db, 'room_id', '') or ''), "site_name": site.key},
                },
                1,
            )
            _seed_fact(
                mara,
                {
                    "id": SITE_OTHER_FACT_ID,
                    "topic": "sello operativo",
                    "text": "El sello operativo de prueba coincide con la secuencia observada.",
                    "knowledge_key": SITE_KEY,
                    "required_level": 1,
                    "source": {"site_room_id": "CAR-KAL-DAR-006", "site_name": "Cantina de Turno"},
                },
                1,
            )
            _seed_fact(
                mara,
                {
                    "id": BUDGET_FACT_ID,
                    "topic": "zetaunique",
                    "text": "zetaunique " + ("evidencia extensa " * 20),
                    "knowledge_key": BUDGET_KEY,
                    "required_level": 1,
                    "source": {"site_room_id": str(getattr(site.db, 'room_id', '') or ''), "site_name": site.key},
                },
                1,
            )

            seeded_facts = _clone(getattr(mara.db, "knowledge_facts", []))
            seeded_knowledge = _clone(getattr(mara.db, "knowledge", {}))

            main = retrieve_known_facts(
                mara,
                query="manifiesto anotacion duplicada relevo cierre",
                max_facts=8,
                char_budget=2000,
            )
            main_ids = _fact_ids(main)
            check(
                "relevant-known-facts-are-selected",
                SOURCE_FACT_ID in main_ids and DIRECT_FACT_ID in main_ids,
                f"selected={main_ids}",
            )
            check(
                "stored-but-unknown-fact-is-never-exposed",
                DECOY_FACT_ID not in main_ids
                and any(row.get("id") == DECOY_FACT_ID and row.get("reason") == "UNKNOWN" for row in main.get("omitted") or []),
                f"selected={main_ids}",
            )
            check(
                "known-but-irrelevant-fact-is-filtered-for-nonempty-query",
                IRRELEVANT_FACT_ID not in main_ids,
                f"selected={main_ids}",
            )

            exact_unknown = retrieve_known_facts(mara, query=DECOY_FACT_ID, max_facts=8, char_budget=2000)
            check(
                "exact-query-cannot-bypass-knowledge-gate",
                DECOY_FACT_ID not in _fact_ids(exact_unknown),
                f"selected={_fact_ids(exact_unknown)}",
            )

            exact_known = retrieve_known_facts(mara, query=SOURCE_FACT_ID, max_facts=8, char_budget=2000)
            check(
                "exact-known-fact-id-receives-deterministic-priority",
                bool(exact_known.get("selected"))
                and exact_known.get("selected")[0].get("id") == SOURCE_FACT_ID
                and "EXACT_FACT_ID" in (exact_known.get("selected")[0].get("relevance_reasons") or []),
                f"first={(_fact_ids(exact_known) or [None])[0]}",
            )

            site_rank = retrieve_known_facts(mara, query="sello operativo", max_facts=8, char_budget=2000)
            rank_ids = [fact_id for fact_id in _fact_ids(site_rank) if fact_id in {SITE_MATCH_FACT_ID, SITE_OTHER_FACT_ID}]
            check(
                "current-site-source-breaks-equal-query-relevance-deterministically",
                rank_ids[:2] == [SITE_MATCH_FACT_ID, SITE_OTHER_FACT_ID],
                f"site_rank={rank_ids}",
            )

            repeat_a = retrieve_known_facts(mara, query="manifiesto anotacion duplicada relevo cierre", max_facts=8, char_budget=2000)
            repeat_b = retrieve_known_facts(mara, query="manifiesto anotacion duplicada relevo cierre", max_facts=8, char_budget=2000)
            check(
                "same-input-produces-byte-stable-selection-packet",
                repeat_a == repeat_b,
                f"ids={_fact_ids(repeat_a)}",
            )

            limited = retrieve_known_facts(mara, query="manifiesto anotacion duplicada relevo cierre", max_facts=1, char_budget=2000)
            check(
                "max-facts-budget-is-deterministic",
                len(limited.get("selected") or []) == 1
                and any(row.get("reason") == "MAX_FACTS" for row in limited.get("omitted") or []),
                f"selected={_fact_ids(limited)}",
            )

            budgeted = retrieve_known_facts(mara, query="zetaunique", max_facts=8, char_budget=40)
            check(
                "character-budget-never-overflows",
                int(budgeted.get("used_chars") or 0) <= 40
                and BUDGET_FACT_ID not in _fact_ids(budgeted)
                and any(row.get("id") == BUDGET_FACT_ID and row.get("reason") == "CHAR_BUDGET" for row in budgeted.get("omitted") or []),
                f"used={budgeted.get('used_chars')} selected={_fact_ids(budgeted)}",
            )

            selected_source = next((row for row in main.get("selected") or [] if row.get("id") == SOURCE_FACT_ID), {})
            original_source = find_knowledge_fact(mara, SOURCE_FACT_ID) or {}
            check(
                "selected-packet-preserves-source-learning-and-transfer-provenance",
                selected_source.get("source") == original_source.get("source")
                and selected_source.get("learned_by") == original_source.get("learned_by")
                and selected_source.get("transfer_history") == original_source.get("transfer_history"),
                f"history={len(selected_source.get('transfer_history') or [])}",
            )

            accent = retrieve_known_facts(mara, query="pescadería manifiesto", max_facts=8, char_budget=2000)
            check(
                "accent-normalization-keeps-spanish-queries-deterministic",
                SOURCE_FACT_ID in _fact_ids(accent) and DIRECT_FACT_ID in _fact_ids(accent),
                f"selected={_fact_ids(accent)}",
            )

            none = retrieve_known_facts(mara, query=EMPTY_QUERY_TOKEN, max_facts=8, char_budget=2000)
            check(
                "no-relevant-known-facts-produces-empty-context",
                not none.get("selected") and none.get("context_text") == "",
                f"selected={_fact_ids(none)}",
            )

            no_query = retrieve_known_facts(mara, query="", max_facts=3, char_budget=2000)
            check(
                "empty-query-still-returns-only-known-facts-with-hard-limit",
                len(no_query.get("selected") or []) == 3
                and all(int(row.get("knowledge_level") or 0) >= int(row.get("required_level") or 1) for row in no_query.get("selected") or []),
                f"selected={_fact_ids(no_query)}",
            )

            check(
                "retrieval-is-read-only-and-does-not-mutate-entity-state",
                _clone(getattr(mara.db, "knowledge_facts", [])) == seeded_facts
                and _clone(getattr(mara.db, "knowledge", {})) == seeded_knowledge,
                "knowledge_and_facts_unchanged=True",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            mara.db.knowledge = original_knowledge
            mara.db.knowledge_facts = original_facts
            try:
                if mara.location != original_location:
                    mara.move_to(original_location, quiet=True)
            except Exception:
                pass

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: Mara location, Knowledge and Facts restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: deterministic known-only Fact retrieval with relevance, site bias, provenance and budgets")
        self.caller.msg("========================================================")
