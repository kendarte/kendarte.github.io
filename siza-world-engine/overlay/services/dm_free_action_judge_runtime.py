import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from evennia.utils import logger
from twisted.internet import threads

from services.dm_free_action_judge import (
    DM_JUDGE_BUILD,
    build_dm_judge_request,
    parse_dm_judge_response,
)
from services.narration_queue import run_serialized
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL


DM_JUDGE_RUNTIME_BUILD = "dm-0.1-async-bounded-judgment"
DEFAULT_TIMEOUT_SECONDS = 30.0


def call_prebuilt_dm_judge(
    request_packet,
    endpoint=DEFAULT_OLLAMA_ENDPOINT,
    model=DEFAULT_OLLAMA_MODEL,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
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
            "build": DM_JUDGE_RUNTIME_BUILD,
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
            "build": DM_JUDGE_RUNTIME_BUILD,
        }

    parsed = parse_dm_judge_response(raw_response, packet.get("steps") or [], http_status=status)
    parsed.update({
        "judge_build": DM_JUDGE_BUILD,
        "request": packet,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "build": DM_JUDGE_RUNTIME_BUILD,
    })
    return parsed


def _call_provider(provider, request_packet, provider_options):
    return provider(request_packet, **dict(provider_options or {}))


def dispatch_dm_judge_async(
    actor,
    raw_player_input,
    adjudication,
    dm_plan,
    *,
    on_result,
    on_failure=None,
    provider_callable=None,
    **provider_options,
):
    request_packet = build_dm_judge_request(raw_player_input, adjudication, dm_plan=dm_plan)
    provider = provider_callable or call_prebuilt_dm_judge
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
            "build": DM_JUDGE_RUNTIME_BUILD,
        }
        return on_result(actor, packet) if callable(on_result) else packet

    def _failed(failure):
        logger.log_err(f"SIZA DM judge async failure: {failure}")
        if callable(on_failure):
            return on_failure(actor, failure)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "status": "QUEUED",
        "queued": True,
        "request": request_packet,
        "deferred": deferred,
        "build": DM_JUDGE_RUNTIME_BUILD,
    }
