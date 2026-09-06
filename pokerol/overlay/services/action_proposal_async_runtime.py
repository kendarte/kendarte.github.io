import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from evennia.utils import logger
from twisted.internet import threads

from services.action_intent_proposal_engine import (
    ACTION_PROPOSAL_BUILD,
    DEFAULT_TIMEOUT_SECONDS,
    build_action_proposal_request,
    parse_action_proposal_response,
)
from services.narration_queue import run_serialized
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL


ASYNC_ACTION_PROPOSAL_BUILD = "0.71.0-reactor-safe-async-action-proposal"
DEFAULT_ACTION_FAILURE_TEXT = "No entiendo esa acción todavía."


def call_prebuilt_action_proposal(
    request_packet,
    endpoint=DEFAULT_OLLAMA_ENDPOINT,
    model=DEFAULT_OLLAMA_MODEL,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    """Perform only HTTP/JSON work from a prebuilt request; never read Evennia objects in the worker thread."""
    request_packet = dict(request_packet or {})
    payload = dict(request_packet.get("ollama_payload") or {})
    catalog = list(request_packet.get("catalog") or [])
    payload["model"] = str(model or DEFAULT_OLLAMA_MODEL)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = Request(
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
        with urlopen(req, timeout=timeout_value) as response:
            http_status = int(getattr(response, "status", 200) or 200)
            raw_response = response.read()
    except HTTPError as exc:
        return {
            "status": "HTTP_ERROR",
            "accepted": False,
            "http_status": int(getattr(exc, "code", 0) or 0),
            "error": str(exc),
            "request": request_packet,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "build": ASYNC_ACTION_PROPOSAL_BUILD,
        }
    except (URLError, socket.timeout, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        is_timeout = isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, socket.timeout)
        return {
            "status": "TIMEOUT" if is_timeout else "TRANSPORT_ERROR",
            "accepted": False,
            "http_status": 0,
            "error": str(reason or exc),
            "request": request_packet,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "build": ASYNC_ACTION_PROPOSAL_BUILD,
        }

    parsed = parse_action_proposal_response(raw_response, catalog, http_status=http_status)
    parsed.update(
        {
            "proposal_build": ACTION_PROPOSAL_BUILD,
            "build": ASYNC_ACTION_PROPOSAL_BUILD,
            "request": request_packet,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    )
    return parsed


def _call_provider(provider_callable, request_packet, provider_options):
    return provider_callable(request_packet, **dict(provider_options or {}))


def dispatch_action_proposal_async(
    actor,
    raw,
    *,
    on_result,
    on_failure=None,
    provider_callable=None,
    **provider_options,
):
    """Snapshot capabilities on the reactor, perform HTTP in a worker, then return to reactor for result handling."""
    request_packet = build_action_proposal_request(actor, raw)
    provider = provider_callable or call_prebuilt_action_proposal
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
        }
        return on_result(actor, packet) if callable(on_result) else packet

    def _failed(failure):
        logger.log_err(f"SIZA action proposal async failure: {failure}")
        if callable(on_failure):
            return on_failure(actor, failure)
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "build": ASYNC_ACTION_PROPOSAL_BUILD,
        "request": request_packet,
        "deferred": deferred,
        "queued": True,
    }
