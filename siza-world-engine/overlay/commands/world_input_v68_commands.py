import json
import re
import unicodedata

from evennia import Command

from commands.siza_commands import CmdSizaNoMatch, _looks_like_movement, score_exit
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.object_action_input_engine import (
    match_object_action_input,
    render_object_action_input_result,
    route_object_action_input,
)
from services.ollama_narration_provider import (
    DEFAULT_NUM_PREDICT,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
)
from services.perception_engine import parse_perception_intent
from services.perspective_narration_engine import (
    ASYNC_VIEWER_NARRATION_BUILD,
    build_viewer_grounded_request,
    narrate_for_viewer,
    narrate_for_viewer_async,
)
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


NATURAL_INPUT_BUILD = "0.68.0-guarded-natural-input-grounded-narration"
PLAYER_FACT_ID = "FACT-V068-PLAYER-MANIFEST-001"
PLAYER_KEY = "V068_PLAYER_MANIFEST"
MARA_PRIVATE_FACT_ID = "FACT-V068-MARA-PRIVATE-001"
MARA_PRIVATE_KEY = "V068_MARA_PRIVATE"
PRIVATE_SENTINEL = "NEVER_LEAK_V068_MARA_PRIVATE_SENTINEL"

INQUIRY_PREFIXES = (
    "que ",
    "quien ",
    "donde ",
    "cuando ",
    "como ",
    "cual ",
    "cuales ",
    "cuanto ",
    "cuanta ",
    "por que ",
    "dime ",
    "cuentame ",
    "explica ",
    "explicame ",
    "quiero saber ",
    "me pregunto ",
    "sabes ",
)


def _normalize(text):
    value = unicodedata.normalize("NFD", str(text or ""))
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return " ".join(value.split())


def _looks_like_inquiry(raw):
    text = str(raw or "").strip()
    normalized = _normalize(text)
    if not normalized:
        return False
    if "?" in text or "¿" in text:
        return True
    padded = normalized + " "
    return any(padded.startswith(prefix) for prefix in INQUIRY_PREFIXES)


def _movement_probe(caller, raw):
    location = getattr(caller, "location", None)
    if not location:
        return {"matched": False, "scores": []}
    exits = list(getattr(location, "exits", []) or [])
    scored = [(score_exit(raw, exit_obj), exit_obj) for exit_obj in exits]
    scored = [(score, exit_obj) for score, exit_obj in scored if score > 0]
    if not scored:
        return {"matched": False, "scores": []}

    # Mirror the existing CmdSizaNoMatch gate exactly so this classifier never steals
    # input that the deterministic movement route would have handled.
    existing_gate_passes = _looks_like_movement(raw) or int(scored[0][0]) >= 700
    return {
        "matched": bool(existing_gate_passes),
        "scores": [
            {"score": int(score), "exit": exit_obj.key, "dbref": int(exit_obj.id)}
            for score, exit_obj in scored
        ],
    }


def classify_v68_input(caller, raw):
    """Classify one __nomatch input without executing any world mutation."""
    text = str(raw or "").strip()
    location = getattr(caller, "location", None) if caller else None
    if not text or not caller or not location:
        return {
            "build": NATURAL_INPUT_BUILD,
            "route": "LEGACY_EMPTY",
            "raw": text,
            "ai_allowed": False,
        }

    object_probe = match_object_action_input(caller, text)
    if bool(object_probe.get("matched")):
        return {
            "build": NATURAL_INPUT_BUILD,
            "route": "OBJECT_ACTION",
            "raw": text,
            "ai_allowed": False,
            "object_status": object_probe.get("status"),
            "object_action_id": object_probe.get("object_action_id"),
            "object_name": object_probe.get("object_name"),
        }

    interaction = parse_interaction_intent(text)
    if interaction:
        return {
            "build": NATURAL_INPUT_BUILD,
            "route": "INTERACTION",
            "raw": text,
            "ai_allowed": False,
            "intent": dict(interaction),
        }

    perception = parse_perception_intent(text)
    if perception:
        return {
            "build": NATURAL_INPUT_BUILD,
            "route": "PERCEPTION",
            "raw": text,
            "ai_allowed": False,
            "intent": dict(perception),
        }

    movement = _movement_probe(caller, text)
    if bool(movement.get("matched")):
        return {
            "build": NATURAL_INPUT_BUILD,
            "route": "MOVEMENT",
            "raw": text,
            "ai_allowed": False,
            "movement": movement,
        }

    if _looks_like_inquiry(text):
        return {
            "build": NATURAL_INPUT_BUILD,
            "route": "AI_INQUIRY",
            "raw": text,
            "ai_allowed": True,
        }

    return {
        "build": NATURAL_INPUT_BUILD,
        "route": "LEGACY_UNKNOWN",
        "raw": text,
        "ai_allowed": False,
    }


def route_v68_input(caller, raw, ai_dispatcher=None):
    """Execute only the object-action or AI branch; all legacy deterministic routes delegate unchanged."""
    classification = classify_v68_input(caller, raw)
    route = classification.get("route")

    if route == "OBJECT_ACTION":
        packet = route_object_action_input(caller, raw)
        text = render_object_action_input_result(packet)
        if text:
            caller.msg("\n" + text)
        return {
            "build": NATURAL_INPUT_BUILD,
            "classification": classification,
            "handled": True,
            "delegate_legacy": False,
            "object_packet": packet,
        }

    if route == "AI_INQUIRY":
        dispatcher = ai_dispatcher or narrate_for_viewer_async
        dispatch = dispatcher(caller, query=str(raw or "").strip())
        return {
            "build": NATURAL_INPUT_BUILD,
            "classification": classification,
            "handled": True,
            "delegate_legacy": False,
            "ai_dispatch": dispatch,
        }

    return {
        "build": NATURAL_INPUT_BUILD,
        "classification": classification,
        "handled": False,
        "delegate_legacy": True,
    }


class CmdSizaNoMatchV68(CmdSizaNoMatch):
    """Preserve deterministic input priority; use grounded Ollama only for otherwise-unmatched inquiries."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        packet = route_v68_input(self.caller, raw)
        if bool(packet.get("delegate_legacy")):
            return super().func()
        return None


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
    }


def _mara_private_fact(manifest, site):
    return {
        "id": MARA_PRIVATE_FACT_ID,
        "topic": "manifiesto duplicado relevo cierre detalle privado",
        "text": f"{PRIVATE_SENTINEL}: Mara conoce un detalle privado que el jugador no conoce.",
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


class CmdSizaValidateV68(Command):
    key = "siza-validate-v68"
    aliases = ["validate-v68"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.68 VALIDATION] FAIL | context={context}")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.68 | {NATURAL_INPUT_BUILD} ===")
        self.caller.msg("real __nomatch routing -> deterministic systems first -> viewer-grounded Ollama inquiry fallback")

        try:
            if viewer.location != site:
                viewer.move_to(site, quiet=True)

            _seed(viewer, _player_fact(manifest, site), 1)
            _seed(mara, _mara_private_fact(manifest, site), 1)
            seeded_viewer_knowledge = _clone(getattr(viewer.db, "knowledge", {}))
            seeded_viewer_facts = _clone(getattr(viewer.db, "knowledge_facts", []))
            seeded_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
            seeded_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))

            object_route = classify_v68_input(viewer, "analizar manifiesto")
            check(
                "authored-object-action-keeps-first-priority-over-ai",
                object_route.get("route") == "OBJECT_ACTION" and object_route.get("ai_allowed") is False,
                f"route={object_route.get('route')} action={object_route.get('object_action_id')}",
            )

            interaction_route = classify_v68_input(viewer, "hablo con Mara")
            check(
                "interaction-intent-keeps-priority-over-ai",
                interaction_route.get("route") == "INTERACTION" and interaction_route.get("ai_allowed") is False,
                f"route={interaction_route.get('route')}",
            )

            perception_route = classify_v68_input(viewer, "observo alrededor")
            check(
                "perception-intent-keeps-priority-over-ai",
                perception_route.get("route") == "PERCEPTION" and perception_route.get("ai_allowed") is False,
                f"route={perception_route.get('route')}",
            )

            movement_route = classify_v68_input(viewer, "salir a la calle")
            check(
                "movement-intent-keeps-priority-over-ai",
                movement_route.get("route") == "MOVEMENT" and movement_route.get("ai_allowed") is False,
                f"route={movement_route.get('route')}",
            )

            query = "Que se sobre el manifiesto duplicado y el relevo de cierre?"
            inquiry_route = classify_v68_input(viewer, query)
            check(
                "otherwise-unmatched-inquiry-is-the-only-ai-fallback-route",
                inquiry_route.get("route") == "AI_INQUIRY" and inquiry_route.get("ai_allowed") is True,
                f"route={inquiry_route.get('route')}",
            )

            unknown_action = classify_v68_input(viewer, "bailo en circulos sobre una mesa imaginaria")
            check(
                "unknown-action-is-not-narrated-as-if-it-happened",
                unknown_action.get("route") == "LEGACY_UNKNOWN" and unknown_action.get("ai_allowed") is False,
                f"route={unknown_action.get('route')}",
            )

            dispatch_calls = []

            def fake_dispatch(caller, query=""):
                dispatch_calls.append((int(caller.id), str(query)))
                return {"build": "V068-FAKE-DISPATCH", "queued": True}

            routed_inquiry = route_v68_input(viewer, query, ai_dispatcher=fake_dispatch)
            check(
                "ai-inquiry-route-dispatches-exactly-once-without-legacy-execution",
                len(dispatch_calls) == 1
                and routed_inquiry.get("handled") is True
                and routed_inquiry.get("delegate_legacy") is False
                and (routed_inquiry.get("ai_dispatch") or {}).get("queued") is True,
                f"calls={dispatch_calls}",
            )

            routed_unknown = route_v68_input(viewer, "bailo en circulos sobre una mesa imaginaria", ai_dispatcher=fake_dispatch)
            check(
                "legacy-unknown-route-never-calls-ai-dispatcher",
                len(dispatch_calls) == 1
                and routed_unknown.get("handled") is False
                and routed_unknown.get("delegate_legacy") is True,
                f"calls={len(dispatch_calls)}",
            )

            request = build_viewer_grounded_request(viewer, query=query)
            provider_text = json.dumps(request.get("provider_payload") or {}, ensure_ascii=False, sort_keys=True)
            selected = list((request.get("safe_context") or {}).get("selected_fact_ids") or [])
            check(
                "ai-fallback-remains-viewer-authorized-and-does-not-read-mara-private-facts",
                PLAYER_FACT_ID in selected
                and MARA_PRIVATE_FACT_ID not in selected
                and PRIVATE_SENTINEL not in provider_text,
                f"selected={selected} private_leaked={PRIVATE_SENTINEL in provider_text}",
            )

            check(
                "ai-fallback-provider-text-remains-free-of-internal-fact-identifiers",
                PLAYER_FACT_ID not in provider_text
                and MARA_PRIVATE_FACT_ID not in provider_text
                and "FACT-V068" not in provider_text,
                "metadata_clean=True",
            )

            check(
                "routing-and-grounded-request-building-are-read-only",
                _clone(getattr(viewer.db, "knowledge", {})) == seeded_viewer_knowledge
                and _clone(getattr(viewer.db, "knowledge_facts", [])) == seeded_viewer_facts
                and _clone(getattr(mara.db, "knowledge", {})) == seeded_mara_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == seeded_mara_facts,
                "viewer_and_npc_unchanged=True",
            )

            check(
                "runtime-ai-dispatch-is-explicitly-asynchronous",
                ASYNC_VIEWER_NARRATION_BUILD.startswith("0.68.0-") and callable(narrate_for_viewer_async),
                f"async_build={ASYNC_VIEWER_NARRATION_BUILD}",
            )

            self.caller.msg(
                f"LIVE OLLAMA PROBE: endpoint={DEFAULT_OLLAMA_ENDPOINT} model={DEFAULT_OLLAMA_MODEL} "
                f"num_predict={DEFAULT_NUM_PREDICT} route=AI_INQUIRY"
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
                "live-natural-input-grounded-ollama-call-succeeds",
                live.get("status") == "OK" and int(live.get("http_status") or 0) == 200,
                f"status={live.get('status')} http={live.get('http_status')} error={live.get('error')}",
            )

            check(
                "live-natural-input-response-is-complete-clean-and-nonempty",
                bool(str(live.get("text") or "").strip())
                and str(live.get("done_reason") or "").lower() != "length"
                and "FACT-V068" not in str(live.get("text") or "")
                and PRIVATE_SENTINEL not in str(live.get("text") or ""),
                f"chars={len(str(live.get('text') or ''))} done_reason={live.get('done_reason')}",
            )

            check(
                "live-natural-input-narration-does-not-persist-game-state",
                _clone(getattr(viewer.db, "knowledge", {})) == seeded_viewer_knowledge
                and _clone(getattr(viewer.db, "knowledge_facts", [])) == seeded_viewer_facts
                and _clone(getattr(mara.db, "knowledge", {})) == seeded_mara_knowledge
                and _clone(getattr(mara.db, "knowledge_facts", [])) == seeded_mara_facts,
                "state_unchanged=True",
            )

            if live.get("status") == "OK":
                self.caller.msg("--- LIVE NATURAL INPUT SAMPLE ---")
                self.caller.msg(str(live.get("text") or ""))
                self.caller.msg("--- END LIVE NATURAL INPUT SAMPLE ---")

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
        self.caller.msg("STATE RESTORED: viewer/Mara Knowledge/Facts and viewer location restored exactly")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: deterministic input routes remain authoritative; only unmatched inquiries reach async viewer-grounded Ollama"
        )
        self.caller.msg("========================================================")
