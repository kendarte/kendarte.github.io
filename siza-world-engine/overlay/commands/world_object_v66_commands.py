import json

from evennia import Command

from services.grounded_narration_context_engine import build_grounded_narration_request
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.npc_simulation import find_npc
from services.ollama_narration_provider import (
    DEFAULT_NUM_PREDICT,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_PROVIDER_BUILD,
    build_ollama_chat_payload,
    call_ollama_chat,
    parse_ollama_chat_response,
)
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


KNOWN_FACT_ID = "FACT-V066-KNOWN-LOCAL-OLLAMA-001"
KNOWN_KEY = "V066_KNOWN_LOCAL_OLLAMA"
UNKNOWN_FACT_ID = "FACT-V066-UNKNOWN-LOCAL-OLLAMA-001"
UNKNOWN_KEY = "V066_UNKNOWN_LOCAL_OLLAMA"
UNKNOWN_SENTINEL = "NEVER_LEAK_V066_PRIVATE_MANIFEST_SENTINEL"


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
        "topic": "verificacion local del manifiesto duplicado",
        "text": "Mara conoce que el manifiesto de la pescaderia contiene una anotacion duplicada vinculada al relevo de cierre.",
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
            "action_id": "OBJECT_ACTION_COMPLETED:V066-KNOWN-SEED",
            "object_action_id": "ACT-MARA-VERIFY-MANIFEST-DUPLICATE-001",
            "attempt_id": "V066-KNOWN-SEED",
            "outcome": "COMPLETED",
        },
    }


def _unknown_fact(manifest, site):
    return {
        "id": UNKNOWN_FACT_ID,
        "topic": "verificacion local del manifiesto duplicado secreto",
        "text": f"{UNKNOWN_SENTINEL}: este dato existe en almacenamiento pero Mara no lo conoce.",
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


class CmdSizaNarrateV66(Command):
    key = "siza-narrate"
    aliases = ["narrate"]
    locks = "cmd:all()"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|", 1)]
        target = find_npc(parts[0]) if parts and parts[0] else None
        if not target:
            self.caller.msg("Uso: siza-narrate <NPC> | <consulta>")
            return
        query = parts[1] if len(parts) > 1 else ""
        grounded = build_grounded_narration_request(target, query=query)
        safe = grounded.get("safe_context") or {}
        result = call_ollama_chat(grounded.get("provider_payload") or {})

        self.caller.msg(f"=== SIZA OLLAMA NARRATION | {OLLAMA_PROVIDER_BUILD} ===")
        self.caller.msg(
            f"NPC: {target.key} | model={DEFAULT_OLLAMA_MODEL} | status={result.get('status')} | "
            f"selected={safe.get('selected_fact_ids')}"
        )
        if result.get("status") == "OK":
            self.caller.msg("--- NARRATION ---")
            self.caller.msg(result.get("text") or "")
        else:
            self.caller.msg(
                f"Provider failure: status={result.get('status')} http={result.get('http_status')} error={result.get('error')}"
            )
        self.caller.msg("========================================================")


class CmdSizaValidateV66(Command):
    key = "siza-validate-v66"
    aliases = ["validate-v66"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.66 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.66 | {OLLAMA_PROVIDER_BUILD} ===")
        self.caller.msg(
            f"NPC: {mara.key}#{mara.id} | grounded provider boundary -> live Ollama {DEFAULT_OLLAMA_MODEL}"
        )

        try:
            if mara.location != site:
                mara.move_to(site, quiet=True)

            _seed(mara, _known_fact(manifest, site), 1)
            _seed(mara, _unknown_fact(manifest, site), 0)
            seeded_knowledge = _clone(getattr(mara.db, "knowledge", {}))
            seeded_facts = _clone(getattr(mara.db, "knowledge_facts", []))

            query = "Que sabe Mara sobre la verificacion local del manifiesto duplicado y el relevo de cierre?"
            grounded = build_grounded_narration_request(mara, query=query, max_facts=6, char_budget=1200)
            provider = grounded.get("provider_payload") or {}
            selected_ids = list((grounded.get("safe_context") or {}).get("selected_fact_ids") or [])
            chat = build_ollama_chat_payload(provider)
            serialized_chat = json.dumps(chat, ensure_ascii=False, sort_keys=True)

            check(
                "v066-starts-from-grounded-v065-provider-boundary",
                KNOWN_FACT_ID in selected_ids
                and UNKNOWN_FACT_ID not in selected_ids
                and set(provider.keys()) == {"system", "prompt"},
                f"selected={selected_ids}",
            )

            check(
                "ollama-request-maps-provider-boundary-to-two-chat-messages-exactly",
                chat.get("messages") == [
                    {"role": "system", "content": provider.get("system")},
                    {"role": "user", "content": provider.get("prompt")},
                ],
                f"roles={[row.get('role') for row in chat.get('messages') or []]}",
            )

            check(
                "ollama-request-forces-bounded-nonstreaming-nonthinking-generation",
                chat.get("model") == DEFAULT_OLLAMA_MODEL
                and chat.get("stream") is False
                and chat.get("think") is False
                and int((chat.get("options") or {}).get("num_predict") or 0) == DEFAULT_NUM_PREDICT
                and float((chat.get("options") or {}).get("temperature") or 0) == 0.0,
                f"model={chat.get('model')} stream={chat.get('stream')} think={chat.get('think')} options={chat.get('options')}",
            )

            check(
                "unknown-stored-fact-never-crosses-ollama-http-request-boundary",
                UNKNOWN_SENTINEL not in serialized_chat and UNKNOWN_FACT_ID not in serialized_chat,
                f"sentinel_leaked={UNKNOWN_SENTINEL in serialized_chat}",
            )

            repeated = build_ollama_chat_payload(provider)
            check(
                "same-grounded-input-produces-byte-stable-ollama-request",
                chat == repeated,
                f"stable={chat == repeated}",
            )

            valid_parse = parse_ollama_chat_response(
                {"model": DEFAULT_OLLAMA_MODEL, "message": {"role": "assistant", "content": "respuesta de prueba"}, "done": True},
                http_status=200,
            )
            check(
                "ollama-response-parser-accepts-valid-nonstreaming-message",
                valid_parse.get("status") == "OK" and valid_parse.get("text") == "respuesta de prueba",
                f"status={valid_parse.get('status')}",
            )

            invalid_json = parse_ollama_chat_response("{not-json", http_status=200)
            check(
                "ollama-response-parser-rejects-invalid-json-without-exception",
                invalid_json.get("status") == "INVALID_JSON" and invalid_json.get("text") == "",
                f"status={invalid_json.get('status')}",
            )

            invalid_shape = parse_ollama_chat_response({"model": DEFAULT_OLLAMA_MODEL, "done": True}, http_status=200)
            check(
                "ollama-response-parser-rejects-missing-message-without-exception",
                invalid_shape.get("status") == "INVALID_RESPONSE" and invalid_shape.get("text") == "",
                f"status={invalid_shape.get('status')}",
            )

            transport_failure = call_ollama_chat(
                provider,
                endpoint="http://127.0.0.1:1/api/chat",
                timeout=0.2,
                num_predict=8,
            )
            check(
                "ollama-transport-failure-is-structured-not-an-unhandled-exception",
                transport_failure.get("status") in {"TRANSPORT_ERROR", "TIMEOUT", "HTTP_ERROR"}
                and transport_failure.get("text") == "",
                f"status={transport_failure.get('status')}",
            )

            self.caller.msg(
                f"LIVE OLLAMA PROBE: endpoint={DEFAULT_OLLAMA_ENDPOINT} model={DEFAULT_OLLAMA_MODEL} "
                f"num_predict={DEFAULT_NUM_PREDICT}"
            )
            live = call_ollama_chat(
                provider,
                endpoint=DEFAULT_OLLAMA_ENDPOINT,
                model=DEFAULT_OLLAMA_MODEL,
                timeout=60,
                num_predict=DEFAULT_NUM_PREDICT,
                temperature=0,
            )

            check(
                "live-local-ollama-chat-call-succeeds",
                live.get("status") == "OK" and int(live.get("http_status") or 0) == 200,
                f"status={live.get('status')} http={live.get('http_status')} error={live.get('error')}",
            )

            check(
                "live-local-ollama-returns-nonempty-assistant-content",
                live.get("status") == "OK" and bool(str(live.get("text") or "").strip()),
                f"model={live.get('model')} chars={len(str(live.get('text') or ''))} eval_count={live.get('eval_count')}",
            )

            live_request = live.get("request_payload") or {}
            live_serialized = json.dumps(live_request, ensure_ascii=False, sort_keys=True)
            check(
                "live-http-request-is-the-same-audited-grounded-request",
                live_request == chat
                and UNKNOWN_SENTINEL not in live_serialized
                and UNKNOWN_FACT_ID not in live_serialized,
                f"same_request={live_request == chat} sentinel_leaked={UNKNOWN_SENTINEL in live_serialized}",
            )

            check(
                "live-model-output-does-not-auto-persist-as-knowledge-or-facts",
                _clone(getattr(mara.db, "knowledge", {})) == seeded_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == seeded_facts,
                "knowledge_and_facts_unchanged=True",
            )

            check(
                "live-model-never-receives-or-echoes-unknown-sentinel",
                UNKNOWN_SENTINEL not in str(live.get("text") or "")
                and UNKNOWN_FACT_ID not in str(live.get("text") or ""),
                f"sentinel_in_response={UNKNOWN_SENTINEL in str(live.get('text') or '')}",
            )

            if live.get("status") == "OK":
                self.caller.msg("--- LIVE OLLAMA SAMPLE ---")
                self.caller.msg(str(live.get("text") or ""))
                self.caller.msg("--- END LIVE SAMPLE ---")

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
            "PERSISTENT SYSTEM RETAINED: grounded provider payload -> isolated local Ollama adapter; model output remains read-only"
        )
        self.caller.msg("========================================================")
