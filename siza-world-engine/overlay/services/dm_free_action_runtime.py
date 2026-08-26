import json
import socket
import time
from copy import deepcopy
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from evennia.utils import logger
from twisted.internet import threads

from services.dm_context_broker import build_dm_context_packet
from services.dm_free_action_interpreter import (
    DM_FREE_ACTION_BUILD,
    build_dm_free_action_request,
    parse_dm_free_action_response,
)
from services.narration_queue import run_serialized
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL
from services.player_language_contract import get_actor_turn_language


DM_FREE_ACTION_RUNTIME_BUILD = "dm-0.1.3-async-bounded-context-retry-interpretation"
DEFAULT_TIMEOUT_SECONDS = 30.0


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _attach_dm_context(request_packet, context_packet):
    """Add DM-only read context to the existing interpreter request without expanding its reference catalog."""
    packet = deepcopy(_plain_dict(request_packet))
    context = deepcopy(_plain_dict(context_packet))
    payload = deepcopy(_plain_dict(packet.get("ollama_payload")))
    messages = [deepcopy(_plain_dict(row)) for row in list(payload.get("messages") or [])]
    if len(messages) >= 2:
        try:
            user = json.loads(str(messages[-1].get("content") or "{}"))
        except (TypeError, ValueError):
            user = {}
        user["DM CONTEXT"] = {
            "world_engine": context.get("world_engine") or [],
            "world_book": context.get("world_book") or {},
            "authority": context.get("authority") or {},
        }
        messages[-1]["content"] = json.dumps(user, ensure_ascii=False, separators=(",", ":"))
        messages[0]["content"] = (
            str(messages[0].get("content") or "")
            + " DM CONTEXT is read-only information for interpretation and adjudication. "
            + "World Book excerpts are NOT player Knowledge and must never be treated as something the player knows. "
            + "DM CONTEXT cannot authorize an action, create a ref, create a Fact, or establish an outcome."
        )
        payload["messages"] = messages
    packet["ollama_payload"] = payload
    packet["dm_context"] = context
    return packet


def call_prebuilt_dm_free_action(
    request_packet,
    endpoint=DEFAULT_OLLAMA_ENDPOINT,
    model=DEFAULT_OLLAMA_MODEL,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    """HTTP-only worker call. All Evennia/world reads must happen before entering this function."""
    packet = dict(request_packet or {})
    payload = dict(packet.get("ollama_payload") or {})
    payload["model"] = str(model or DEFAULT_OLLAMA_MODEL)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(
        str(endpoint or DEFAULT_OLLAMA_ENDPOINT),
        data=encoded,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        timeout_value = max(0.05, float(timeout))
    except (TypeError, ValueError):
        timeout_value = DEFAULT_TIMEOUT_SECONDS

    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_value) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw_response = response.read()
    except HTTPError as exc:
        return {
            "status": "HTTP_ERROR",
            "accepted": False,
            "http_status": int(getattr(exc, "code", 0) or 0),
            "error": str(exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "build": DM_FREE_ACTION_RUNTIME_BUILD,
        }
    except (URLError, socket.timeout, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        is_timeout = isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, socket.timeout)
        return {
            "status": "TIMEOUT" if is_timeout else "TRANSPORT_ERROR",
            "accepted": False,
            "http_status": 0,
            "error": str(reason or exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "build": DM_FREE_ACTION_RUNTIME_BUILD,
        }

    parsed = parse_dm_free_action_response(raw_response, packet.get("allowed_refs") or [], http_status=status)
    parsed.update({
        "interpreter_build": DM_FREE_ACTION_BUILD,
        "request": packet,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "build": DM_FREE_ACTION_RUNTIME_BUILD,
    })
    return parsed


def _call_provider(provider, request_packet, provider_options):
    return provider(request_packet, **dict(provider_options or {}))


def dispatch_dm_free_action_async(
    actor,
    raw_player_input,
    dm_plan,
    world_snapshot,
    *,
    on_result,
    on_failure=None,
    provider_callable=None,
    context_needs=None,
    **provider_options,
):
    """Retrieve bounded context on reactor, interpret in worker, return result to reactor."""
    requested_needs = [str(value) for value in list(context_needs or []) if str(value or "").strip()]
    context_packet = build_dm_context_packet(
        actor,
        raw_player_input,
        dm_plan,
        world_snapshot,
        context_needs=requested_needs,
    )
    request_packet = build_dm_free_action_request(
        raw_player_input,
        dm_plan,
        world_snapshot,
        player_language=get_actor_turn_language(actor),
    )
    request_packet = _attach_dm_context(request_packet, context_packet)
    request_packet["context_retry_needs"] = requested_needs
    provider = provider_callable or call_prebuilt_dm_free_action
    deferred = run_serialized(
        actor,
        threads.deferToThread,
        _call_provider,
        provider,
        request_packet,
        dict(provider_options or {}),
    )

    def _ok(result):
        packet = result if isinstance(result, dict) else {
            "status": "INVALID_PROVIDER_RESULT",
            "accepted": False,
            "build": DM_FREE_ACTION_RUNTIME_BUILD,
        }
        return on_result(actor, packet) if callable(on_result) else packet

    def _failed(failure):
        logger.log_err(f"SIZA DM free action async failure: {failure}")
        if callable(on_failure):
            return on_failure(actor, failure)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "status": "QUEUED",
        "queued": True,
        "request": request_packet,
        "context": context_packet,
        "context_needs": requested_needs,
        "deferred": deferred,
        "build": DM_FREE_ACTION_RUNTIME_BUILD,
    }
