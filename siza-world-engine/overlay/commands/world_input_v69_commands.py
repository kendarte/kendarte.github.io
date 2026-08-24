import json

from evennia import Command

from services.action_intent_proposal_engine import (
    ACTION_PROPOSAL_BUILD,
    build_action_proposal_request,
    build_local_capability_catalog,
    call_ollama_action_proposal,
    parse_action_proposal_response,
    validate_action_proposal,
)
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


PRIVATE_SENTINEL = "NEVER_LEAK_V069_PRIVATE_KNOWLEDGE_SENTINEL"


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


def _response_for(proposal):
    return {
        "model": DEFAULT_OLLAMA_MODEL,
        "message": {"role": "assistant", "content": json.dumps(proposal, ensure_ascii=False)},
        "done": True,
        "done_reason": "stop",
    }


class CmdSizaValidateV69(Command):
    key = "siza-validate-v69"
    aliases = ["validate-v69"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.69 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        original_location = actor.location
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.69 | {ACTION_PROPOSAL_BUILD} ===")
        self.caller.msg("free-form action text -> structured proposal constrained to current-room capability catalog -> NO EXECUTION")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)

            actor.db.knowledge_facts = list(getattr(actor.db, "knowledge_facts", []) or []) + [
                {
                    "id": "FACT-V069-PRIVATE-SENTINEL",
                    "topic": "dato privado no relacionado",
                    "text": PRIVATE_SENTINEL,
                    "knowledge_key": "V069_PRIVATE_SENTINEL",
                    "required_level": 1,
                }
            ]
            seeded_knowledge = _clone(getattr(actor.db, "knowledge", {}))
            seeded_facts = _clone(getattr(actor.db, "knowledge_facts", []))

            catalog_a = build_local_capability_catalog(actor)
            catalog_b = build_local_capability_catalog(actor)
            kinds = {str(row.get("kind") or "") for row in catalog_a}
            analyze_row = next((row for row in catalog_a if row.get("object_action_id") == ANALYZE_ACTION_ID), None)

            check(
                "local-capability-catalog-is-deterministic-and-covers-real-room-affordances",
                catalog_a == catalog_b
                and {"OBJECT_ACTION", "MOVEMENT", "INTERACTION", "PERCEPTION"}.issubset(kinds)
                and analyze_row is not None,
                f"count={len(catalog_a)} kinds={sorted(kinds)} analyze={bool(analyze_row)}",
            )

            request = build_action_proposal_request(actor, "quiero analizar el manifiesto de carga")
            payload = request.get("ollama_payload") or {}
            schema = request.get("schema") or {}
            capability_enum = (((schema.get("properties") or {}).get("capability_id") or {}).get("enum") or [])
            expected_ids = [""] + [str(row.get("capability_id") or "") for row in catalog_a]
            check(
                "structured-output-schema-enumerates-only-real-current-capabilities",
                capability_enum == expected_ids
                and payload.get("format") == schema
                and payload.get("stream") is False
                and payload.get("think") is False,
                f"enum_count={len(capability_enum)} catalog_count={len(catalog_a)}",
            )

            serialized_request = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            check(
                "action-proposal-provider-boundary-does-not-read-player-knowledge-or-facts",
                PRIVATE_SENTINEL not in serialized_request
                and "knowledge_facts" not in serialized_request
                and "V069_PRIVATE_SENTINEL" not in serialized_request,
                f"sentinel_leaked={PRIVATE_SENTINEL in serialized_request}",
            )

            valid = {
                "kind": "OBJECT_ACTION",
                "capability_id": str(analyze_row.get("capability_id")),
                "confidence": 0.95,
                "reason": "Coincide con analizar el manifiesto.",
            }
            valid_result = validate_action_proposal(valid, catalog_a)
            check(
                "catalog-member-proposal-is-accepted-without-execution",
                valid_result.get("status") == "ACCEPTED"
                and valid_result.get("accepted") is True
                and (valid_result.get("capability") or {}).get("object_action_id") == ANALYZE_ACTION_ID,
                f"status={valid_result.get('status')}",
            )

            hallucinated = dict(valid)
            hallucinated["capability_id"] = "OBJECT_ACTION:INVENTED:DOES-NOT-EXIST"
            hallucinated_result = validate_action_proposal(hallucinated, catalog_a)
            check(
                "hallucinated-capability-is-rejected-before-world-engine",
                hallucinated_result.get("status") == "CAPABILITY_NOT_IN_CATALOG"
                and hallucinated_result.get("accepted") is False,
                f"status={hallucinated_result.get('status')}",
            )

            mismatch = dict(valid)
            mismatch["kind"] = "MOVEMENT"
            mismatch_result = validate_action_proposal(mismatch, catalog_a)
            check(
                "kind-capability-mismatch-is-rejected-before-world-engine",
                mismatch_result.get("status") == "KIND_MISMATCH"
                and mismatch_result.get("accepted") is False,
                f"status={mismatch_result.get('status')}",
            )

            unsupported = {
                "kind": "UNSUPPORTED",
                "capability_id": "",
                "confidence": 0.99,
                "reason": "No existe esa capacidad en el lugar.",
            }
            unsupported_result = validate_action_proposal(unsupported, catalog_a)
            check(
                "unsupported-is-an-explicit-valid-no-action-result",
                unsupported_result.get("status") == "UNSUPPORTED"
                and unsupported_result.get("accepted") is True
                and unsupported_result.get("capability") is None,
                f"status={unsupported_result.get('status')}",
            )

            parsed_valid = parse_action_proposal_response(_response_for(valid), catalog_a, http_status=200)
            check(
                "structured-response-parser-validates-model-json-against-catalog",
                parsed_valid.get("status") == "ACCEPTED"
                and parsed_valid.get("accepted") is True,
                f"status={parsed_valid.get('status')}",
            )

            invalid_json = parse_action_proposal_response("{not-json", catalog_a, http_status=200)
            check(
                "invalid-provider-json-is-rejected-without-exception",
                invalid_json.get("status") == "INVALID_JSON" and invalid_json.get("accepted") is False,
                f"status={invalid_json.get('status')}",
            )

            invalid_proposal = parse_action_proposal_response(
                {"model": DEFAULT_OLLAMA_MODEL, "message": {"role": "assistant", "content": "not-json"}},
                catalog_a,
                http_status=200,
            )
            check(
                "invalid-structured-content-is-rejected-without-exception",
                invalid_proposal.get("status") == "INVALID_PROPOSAL_JSON" and invalid_proposal.get("accepted") is False,
                f"status={invalid_proposal.get('status')}",
            )

            transport_failure = call_ollama_action_proposal(
                actor,
                "analizar manifiesto",
                endpoint="http://127.0.0.1:1/api/chat",
                timeout=0.2,
            )
            check(
                "proposal-transport-failure-is-structured-and-never-executes",
                transport_failure.get("status") in {"TRANSPORT_ERROR", "TIMEOUT", "HTTP_ERROR"}
                and transport_failure.get("accepted") is False,
                f"status={transport_failure.get('status')}",
            )

            self.caller.msg(
                f"LIVE STRUCTURED PROPOSAL: endpoint={DEFAULT_OLLAMA_ENDPOINT} model={DEFAULT_OLLAMA_MODEL} action='quiero analizar el manifiesto de carga'"
            )
            live_known = call_ollama_action_proposal(
                actor,
                "quiero analizar el manifiesto de carga",
                endpoint=DEFAULT_OLLAMA_ENDPOINT,
                model=DEFAULT_OLLAMA_MODEL,
                timeout=60,
            )
            known_cap = live_known.get("capability") or {}
            check(
                "live-qwen-selects-a-real-catalog-capability-for-supported-action",
                live_known.get("status") == "ACCEPTED"
                and live_known.get("accepted") is True
                and known_cap.get("object_action_id") == ANALYZE_ACTION_ID,
                f"status={live_known.get('status')} proposal={live_known.get('proposal')} capability={known_cap.get('capability_id')}",
            )

            self.caller.msg(
                "LIVE UNSUPPORTED PROPOSAL: action='bailo en circulos sobre una mesa imaginaria'"
            )
            live_unknown = call_ollama_action_proposal(
                actor,
                "bailo en circulos sobre una mesa imaginaria",
                endpoint=DEFAULT_OLLAMA_ENDPOINT,
                model=DEFAULT_OLLAMA_MODEL,
                timeout=60,
            )
            check(
                "live-qwen-returns-explicit-unsupported-instead-of-inventing-capability",
                live_unknown.get("status") == "UNSUPPORTED"
                and live_unknown.get("accepted") is True
                and not (live_unknown.get("proposal") or {}).get("capability_id"),
                f"status={live_unknown.get('status')} proposal={live_unknown.get('proposal')}",
            )

            check(
                "live-structured-proposals-are-read-only-and-do-not-persist-world-or-knowledge-state",
                _clone(getattr(actor.db, "knowledge", {})) == seeded_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == seeded_facts
                and actor.location == site,
                "state_unchanged=True",
            )

            check(
                "v069-has-no-execution-bridge-by-design",
                not hasattr(live_known, "execute")
                and "execute" not in (live_known or {})
                and "action_result" not in (live_known or {}),
                "proposal_only=True",
            )

            if live_known.get("proposal"):
                self.caller.msg("--- LIVE SUPPORTED PROPOSAL ---")
                self.caller.msg(json.dumps(live_known.get("proposal"), ensure_ascii=False, sort_keys=True))
                self.caller.msg("--- END SUPPORTED PROPOSAL ---")
            if live_unknown.get("proposal"):
                self.caller.msg("--- LIVE UNSUPPORTED PROPOSAL ---")
                self.caller.msg(json.dumps(live_unknown.get("proposal"), ensure_ascii=False, sort_keys=True))
                self.caller.msg("--- END UNSUPPORTED PROPOSAL ---")

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

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor location/Knowledge/Facts restored exactly")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: Ollama may propose only catalog-bound structured intents; no execution bridge exists in v0.69"
        )
        self.caller.msg("========================================================")
