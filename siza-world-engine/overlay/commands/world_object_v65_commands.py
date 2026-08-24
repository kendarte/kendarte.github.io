from evennia import Command

from services.grounded_narration_context_engine import (
    GROUNDED_NARRATION_BUILD,
    SYSTEM_INSTRUCTIONS,
    build_grounded_narration_request,
)
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.npc_simulation import find_npc
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


KNOWN_FACT_ID = "FACT-V065-KNOWN-MANIFEST-001"
KNOWN_KEY = "V065_KNOWN_MANIFEST"
UNKNOWN_FACT_ID = "FACT-V065-UNKNOWN-MANIFEST-001"
UNKNOWN_KEY = "V065_UNKNOWN_MANIFEST"
IRRELEVANT_FACT_ID = "FACT-V065-IRRELEVANT-CANTINA-001"
IRRELEVANT_KEY = "V065_IRRELEVANT_CANTINA"
UNKNOWN_SENTINEL = "NEVER_LEAK_V065_SECRET_LEDGER"


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


def _seed(entity, fact, level):
    upsert_knowledge_fact(entity, fact)
    set_knowledge_level(entity, fact.get("knowledge_key"), level)


def _known_fact(manifest, site):
    return {
        "id": KNOWN_FACT_ID,
        "topic": "manifiesto duplicado relevo de cierre",
        "text": "Mara conoce que el manifiesto contiene una anotacion duplicada vinculada al relevo de cierre.",
        "knowledge_key": KNOWN_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": str(getattr(manifest.db, "object_id", "") or ""),
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
            "object_dbref": int(manifest.id),
            "site_dbref": int(site.id),
        },
        "learned_by": {
            "action_id": "OBJECT_ACTION_COMPLETED:V065-KNOWN-SEED",
            "object_action_id": "ACT-MARA-VERIFY-MANIFEST-DUPLICATE-001",
            "attempt_id": "V065-KNOWN-SEED",
            "outcome": "COMPLETED",
        },
        "transfer_history": [
            {"id": "V065-HOP-1", "source_name": "Informante de Prueba C", "target_name": "Mara Vensal"}
        ],
    }


def _unknown_fact(manifest, site):
    return {
        "id": UNKNOWN_FACT_ID,
        "topic": "manifiesto duplicado relevo de cierre secreto",
        "text": f"{UNKNOWN_SENTINEL}: este dato esta almacenado pero Mara no lo conoce.",
        "knowledge_key": UNKNOWN_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": str(getattr(manifest.db, "object_id", "") or ""),
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
        },
    }


def _irrelevant_fact():
    return {
        "id": IRRELEVANT_FACT_ID,
        "topic": "menu de la cantina",
        "text": "La cantina sirve sopa durante el turno de manana.",
        "knowledge_key": IRRELEVANT_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {"site_room_id": "CAR-KAL-DAR-006", "site_name": "Cantina de Turno"},
    }


class CmdSizaNarrationContextV65(Command):
    key = "siza-narration-context"
    aliases = ["narration-context"]
    locks = "cmd:all()"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|", 1)]
        target = find_npc(parts[0]) if parts and parts[0] else None
        if not target:
            self.caller.msg("Uso: siza-narration-context <NPC> | <consulta>")
            return
        query = parts[1] if len(parts) > 1 else ""
        packet = build_grounded_narration_request(target, query=query)
        safe = packet.get("safe_context") or {}
        provider = packet.get("provider_payload") or {}
        self.caller.msg(f"=== SIZA GROUNDED NARRATION | {GROUNDED_NARRATION_BUILD} ===")
        self.caller.msg(
            f"NPC: {target.key} | query={query!r} | selected={safe.get('selected_fact_ids')} | "
            f"has_relevant_facts={packet.get('has_relevant_facts')}"
        )
        self.caller.msg("--- PROVIDER SYSTEM ---")
        self.caller.msg(provider.get("system") or "")
        self.caller.msg("--- PROVIDER PROMPT ---")
        self.caller.msg(provider.get("prompt") or "")
        self.caller.msg("========================================================")


class CmdSizaValidateV65(Command):
    key = "siza-validate-v65"
    aliases = ["validate-v65"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.65 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.65 | {GROUNDED_NARRATION_BUILD} ===")
        self.caller.msg(f"NPC: {mara.key}#{mara.id} | retrieval -> provider-safe narration request")

        try:
            if mara.location != site:
                mara.move_to(site, quiet=True)

            _seed(mara, _known_fact(manifest, site), 1)
            _seed(mara, _unknown_fact(manifest, site), 0)
            _seed(mara, _irrelevant_fact(), 1)

            seeded_knowledge = _clone(getattr(mara.db, "knowledge", {}))
            seeded_facts = _clone(getattr(mara.db, "knowledge_facts", []))
            query = "manifiesto anotacion duplicada relevo cierre"

            packet = build_grounded_narration_request(mara, query=query, max_facts=6, char_budget=1200)
            safe = packet.get("safe_context") or {}
            provider = packet.get("provider_payload") or {}
            provider_text = f"{provider.get('system', '')}\n{provider.get('prompt', '')}"
            selected_ids = list(safe.get("selected_fact_ids") or [])

            check(
                "grounded-request-builds-on-v064-known-only-retrieval",
                packet.get("grounded") is True
                and str(packet.get("retrieval_build") or "").startswith("0.64.1-")
                and KNOWN_FACT_ID in selected_ids,
                f"selected={selected_ids} retrieval={packet.get('retrieval_build')}",
            )

            check(
                "provider-payload-has-only-system-and-prompt-boundary",
                set(provider.keys()) == {"system", "prompt"},
                f"keys={sorted(provider.keys())}",
            )

            check(
                "known-relevant-fact-enters-provider-prompt-without-internal-id",
                "anotacion duplicada" in provider_text.lower()
                and KNOWN_FACT_ID not in provider_text,
                f"selected={selected_ids} id_leaked={KNOWN_FACT_ID in provider_text}",
            )

            check(
                "stored-but-unknown-fact-never-enters-provider-payload",
                UNKNOWN_FACT_ID not in selected_ids
                and UNKNOWN_SENTINEL not in provider_text,
                f"unknown_selected={UNKNOWN_FACT_ID in selected_ids} sentinel_leaked={UNKNOWN_SENTINEL in provider_text}",
            )

            check(
                "known-but-irrelevant-fact-never-enters-provider-payload",
                IRRELEVANT_FACT_ID not in selected_ids
                and "sopa durante el turno" not in provider_text.lower(),
                f"irrelevant_selected={IRRELEVANT_FACT_ID in selected_ids}",
            )

            check(
                "provider-system-enforces-explicit-grounding-contract",
                provider.get("system") == SYSTEM_INSTRUCTIONS
                and "No inventes" in str(provider.get("system") or "")
                and "únicamente" in str(provider.get("system") or "")
                and "No menciones identificadores internos" in str(provider.get("system") or ""),
                "system_contract_present=True",
            )

            check(
                "current-world-location-enters-authorized-world-state",
                safe.get("world_state", {}).get("location_room_id") == str(getattr(site.db, "room_id", "") or "")
                and f"Location: {site.key}" in str(provider.get("prompt") or ""),
                f"location={safe.get('world_state', {}).get('location_name')}",
            )

            selected_known = next((row for row in safe.get("selected_facts") or [] if row.get("id") == KNOWN_FACT_ID), {})
            original_known = next((row for row in getattr(mara.db, "knowledge_facts", []) if str(row.get("id") or "") == KNOWN_FACT_ID), {})
            check(
                "safe-context-preserves-selected-fact-provenance",
                selected_known.get("source") == original_known.get("source")
                and selected_known.get("learned_by") == original_known.get("learned_by")
                and selected_known.get("transfer_history") == original_known.get("transfer_history"),
                f"history={len(selected_known.get('transfer_history') or [])}",
            )

            repeat = build_grounded_narration_request(mara, query=query, max_facts=6, char_budget=1200)
            check(
                "same-input-produces-byte-stable-provider-request",
                packet == repeat,
                f"selected={selected_ids}",
            )

            none = build_grounded_narration_request(mara, query="zzv065nothingmatcheszz", max_facts=6, char_budget=1200)
            none_provider = none.get("provider_payload") or {}
            check(
                "no-relevant-facts-produces-explicit-none-context-not-leakage",
                none.get("has_relevant_facts") is False
                and not (none.get("safe_context") or {}).get("selected_fact_ids")
                and "KNOWN FACTS\nNONE" in str(none_provider.get("prompt") or "")
                and UNKNOWN_SENTINEL not in str(none_provider),
                f"selected={(none.get('safe_context') or {}).get('selected_fact_ids')}",
            )

            diagnostics_text = str(packet.get("diagnostics") or {})
            check(
                "omission-diagnostics-stay-outside-provider-payload",
                UNKNOWN_FACT_ID in diagnostics_text
                and UNKNOWN_FACT_ID not in provider_text,
                f"diagnostic_has_unknown={UNKNOWN_FACT_ID in diagnostics_text}",
            )

            check(
                "grounded-request-builder-is-read-only",
                _clone(getattr(mara.db, "knowledge", {})) == seeded_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == seeded_facts,
                "knowledge_and_facts_unchanged=True",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if mara.location != original_location:
                    mara.move_to(original_location, quiet=True)
            except Exception:
                pass
            mara.db.knowledge = original_knowledge
            mara.db.knowledge_facts = original_facts

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: Mara location, Knowledge and Facts restored exactly")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: known-only Fact retrieval -> provider-safe grounded narration request boundary"
        )
        self.caller.msg("========================================================")
