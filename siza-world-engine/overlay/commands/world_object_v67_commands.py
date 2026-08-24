import json

from evennia import Command

from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.ollama_narration_provider import (
    DEFAULT_NUM_PREDICT,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
)
from services.perspective_narration_engine import (
    PERSPECTIVE_NARRATION_BUILD,
    build_viewer_grounded_request,
    narrate_for_viewer,
)
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


PLAYER_FACT_ID = "FACT-V067-PLAYER-MANIFEST-001"
PLAYER_KEY = "V067_PLAYER_MANIFEST"
MARA_PRIVATE_FACT_ID = "FACT-V067-MARA-PRIVATE-001"
MARA_PRIVATE_KEY = "V067_MARA_PRIVATE"
PRIVATE_SENTINEL = "NEVER_LEAK_V067_MARA_PRIVATE_SENTINEL"


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


def _player_fact(manifest, site):
    return {
        "id": PLAYER_FACT_ID,
        "topic": "manifiesto duplicado relevo cierre",
        "text": "El jugador conoce que el manifiesto de la pescaderia contiene una anotacion duplicada vinculada al relevo de cierre.",
        "knowledge_key": PLAYER_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": str(getattr(manifest.db, "object_id", "") or ""),
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
        },
        "learned_by": {
            "action_id": "FACT_TRANSFER:V067-PLAYER-SEED",
            "outcome": "RECEIVED",
        },
        "transfer_history": [
            {
                "id": "V067-PLAYER-HOP-1",
                "source_name": "Informante de Prueba C",
                "target_name": "admin",
            }
        ],
    }


def _mara_private_fact(manifest, site):
    return {
        "id": MARA_PRIVATE_FACT_ID,
        "topic": "manifiesto duplicado relevo cierre secreto privado Mara",
        "text": f"{PRIVATE_SENTINEL}: Mara conoce un detalle privado adicional del manifiesto que el jugador no ha aprendido.",
        "knowledge_key": MARA_PRIVATE_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": str(getattr(manifest.db, "object_id", "") or ""),
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
        },
    }


class CmdSizaViewerNarrateV67(Command):
    key = "siza-viewer-narrate"
    aliases = ["viewer-narrate"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        if not query:
            self.caller.msg("Uso: siza-viewer-narrate <consulta>")
            return
        result = narrate_for_viewer(self.caller, query=query)
        provider = result.get("provider_result") or {}
        self.caller.msg(f"=== SIZA VIEWER NARRATION | {PERSPECTIVE_NARRATION_BUILD} ===")
        self.caller.msg(
            f"viewer={self.caller.key} | status={result.get('status')} | "
            f"selected={(result.get('request') or {}).get('safe_context', {}).get('selected_fact_ids')}"
        )
        if result.get("status") == "OK":
            self.caller.msg(result.get("text") or "")
        else:
            self.caller.msg(
                f"Provider failure: status={provider.get('status')} http={provider.get('http_status')} error={provider.get('error')}"
            )
        self.caller.msg("========================================================")


class CmdSizaValidateV67(Command):
    key = "siza-validate-v67"
    aliases = ["validate-v67"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.67 VALIDATION] FAIL | context={context}")
            return

        viewer = self.caller
        mara = context.get("mara")
        manifest = context.get("manifest")
        site = context.get("destination")
        original_viewer_location = viewer.location
        original_viewer_knowledge = _clone(getattr(viewer.db, "knowledge", {}))
        original_viewer_facts = _clone(getattr(viewer.db, "knowledge_facts", []))
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.67 | {PERSPECTIVE_NARRATION_BUILD} ===")
        self.caller.msg(f"viewer={viewer.key}#{viewer.id} | NPC private knowledge isolation -> grounded Ollama")

        try:
            if viewer.location != site:
                viewer.move_to(site, quiet=True)

            _seed(viewer, _player_fact(manifest, site), 1)
            _seed(mara, _mara_private_fact(manifest, site), 1)
            seeded_viewer_knowledge = _clone(getattr(viewer.db, "knowledge", {}))
            seeded_viewer_facts = _clone(getattr(viewer.db, "knowledge_facts", []))
            seeded_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
            seeded_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))

            query = "Que puedo afirmar sobre el manifiesto duplicado y el relevo de cierre?"
            request = build_viewer_grounded_request(viewer, query=query)
            safe = request.get("safe_context") or {}
            provider = request.get("provider_payload") or {}
            provider_text = f"{provider.get('system', '')}\n{provider.get('prompt', '')}"
            selected = list(safe.get("selected_fact_ids") or [])

            check(
                "perspective-explicitly-owns-knowledge-by-viewer-not-subject",
                (request.get("perspective") or {}).get("knowledge_owner") == "VIEWER"
                and (request.get("perspective") or {}).get("viewer_dbref") == int(viewer.id),
                f"perspective={request.get('perspective')}",
            )

            check(
                "viewer-known-relevant-fact-enters-grounded-context",
                PLAYER_FACT_ID in selected and "anotacion duplicada" in provider_text.lower(),
                f"selected={selected}",
            )

            check(
                "mara-private-known-fact-never-enters-viewer-provider-payload",
                MARA_PRIVATE_FACT_ID not in selected
                and MARA_PRIVATE_FACT_ID not in provider_text
                and PRIVATE_SENTINEL not in provider_text,
                f"private_selected={MARA_PRIVATE_FACT_ID in selected} sentinel_leaked={PRIVATE_SENTINEL in provider_text}",
            )

            subject_query = build_viewer_grounded_request(
                viewer,
                query="Que sabe Mara sobre el manifiesto duplicado, el relevo de cierre y su detalle privado?",
            )
            subject_provider = subject_query.get("provider_payload") or {}
            subject_text = f"{subject_provider.get('system', '')}\n{subject_provider.get('prompt', '')}"
            check(
                "mentioning-an-npc-in-query-cannot-switch-knowledge-owner",
                (subject_query.get("perspective") or {}).get("viewer_dbref") == int(viewer.id)
                and PRIVATE_SENTINEL not in subject_text
                and MARA_PRIVATE_FACT_ID not in subject_text,
                f"viewer_dbref={(subject_query.get('perspective') or {}).get('viewer_dbref')}",
            )

            check(
                "internal-fact-identifiers-remain-outside-provider-text",
                PLAYER_FACT_ID not in provider_text
                and MARA_PRIVATE_FACT_ID not in provider_text
                and "FACT-V067" not in provider_text,
                "provider_metadata_clean=True",
            )

            check(
                "viewer-current-location-is-the-authorized-world-state",
                (safe.get("world_state") or {}).get("location_room_id") == str(getattr(site.db, "room_id", "") or "")
                and (request.get("perspective") or {}).get("location_name") == site.key,
                f"location={(request.get('perspective') or {}).get('location_name')}",
            )

            repeat = build_viewer_grounded_request(viewer, query=query)
            check(
                "same-viewer-and-query-produce-byte-stable-request",
                request == repeat,
                f"stable={request == repeat}",
            )

            none = build_viewer_grounded_request(viewer, query="zzv067nomatchzz")
            check(
                "unrelated-query-does-not-fall-through-to-npc-private-knowledge",
                not (none.get("safe_context") or {}).get("selected_fact_ids")
                and PRIVATE_SENTINEL not in str(none.get("provider_payload") or {}),
                f"selected={(none.get('safe_context') or {}).get('selected_fact_ids')}",
            )

            check(
                "perspective-request-builder-is-read-only-for-viewer-and-npc",
                _clone(getattr(viewer.db, "knowledge", {})) == seeded_viewer_knowledge
                and _clone(getattr(viewer.db, "knowledge_facts", [])) == seeded_viewer_facts
                and _clone(getattr(mara.db, "knowledge", {})) == seeded_mara_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == seeded_mara_facts,
                "viewer_and_npc_unchanged=True",
            )

            self.caller.msg(
                f"LIVE OLLAMA PROBE: endpoint={DEFAULT_OLLAMA_ENDPOINT} model={DEFAULT_OLLAMA_MODEL} "
                f"num_predict={DEFAULT_NUM_PREDICT} perspective=VIEWER"
            )
            live_bundle = narrate_for_viewer(
                viewer,
                query=query,
                endpoint=DEFAULT_OLLAMA_ENDPOINT,
                model=DEFAULT_OLLAMA_MODEL,
                timeout=60,
                num_predict=DEFAULT_NUM_PREDICT,
                temperature=0,
            )
            live = live_bundle.get("provider_result") or {}

            check(
                "live-viewer-grounded-ollama-call-succeeds",
                live.get("status") == "OK" and int(live.get("http_status") or 0) == 200,
                f"status={live.get('status')} http={live.get('http_status')} error={live.get('error')}",
            )

            check(
                "live-response-is-complete-and-nonempty",
                live.get("status") == "OK"
                and bool(str(live.get("text") or "").strip())
                and str(live.get("done_reason") or "").lower() != "length",
                f"chars={len(str(live.get('text') or ''))} done_reason={live.get('done_reason')} eval_count={live.get('eval_count')}",
            )

            live_request = live.get("request_payload") or {}
            live_serialized = json.dumps(live_request, ensure_ascii=False, sort_keys=True)
            check(
                "live-http-boundary-contains-viewer-facts-but-no-npc-private-data-or-internal-ids",
                PRIVATE_SENTINEL not in live_serialized
                and MARA_PRIVATE_FACT_ID not in live_serialized
                and PLAYER_FACT_ID not in live_serialized
                and "FACT-V067" not in live_serialized,
                f"private_leaked={PRIVATE_SENTINEL in live_serialized} internal_id_leaked={'FACT-V067' in live_serialized}",
            )

            check(
                "live-model-output-does-not-persist-or-copy-private-npc-knowledge",
                _clone(getattr(viewer.db, "knowledge", {})) == seeded_viewer_knowledge
                and _clone(getattr(viewer.db, "knowledge_facts", [])) == seeded_viewer_facts
                and PRIVATE_SENTINEL not in str(live.get("text") or ""),
                f"private_in_response={PRIVATE_SENTINEL in str(live.get('text') or '')}",
            )

            check(
                "live-model-output-does-not-expose-internal-fact-ids",
                "FACT-V067" not in str(live.get("text") or "")
                and PLAYER_FACT_ID not in str(live.get("text") or "")
                and MARA_PRIVATE_FACT_ID not in str(live.get("text") or ""),
                f"internal_id_in_response={'FACT-V067' in str(live.get('text') or '')}",
            )

            if live.get("status") == "OK":
                self.caller.msg("--- LIVE VIEWER NARRATION SAMPLE ---")
                self.caller.msg(str(live.get("text") or ""))
                self.caller.msg("--- END LIVE VIEWER SAMPLE ---")

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if viewer.location != original_viewer_location:
                    viewer.move_to(original_viewer_location, quiet=True)
            except Exception:
                pass
            viewer.db.knowledge = original_viewer_knowledge
            viewer.db.knowledge_facts = original_viewer_facts
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: viewer and Mara Knowledge/Facts plus viewer location restored exactly")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: viewer-authorized grounded narration; NPC private Facts remain isolated"
        )
        self.caller.msg("========================================================")
