from evennia.utils import logger
from twisted.internet import threads

from services.action_intent_proposal_engine import build_action_proposal_request, _proposal_schema
from services.action_proposal_async_runtime import (
    ASYNC_ACTION_PROPOSAL_BUILD,
    DEFAULT_ACTION_FAILURE_TEXT,
    call_prebuilt_action_proposal,
)
from services.narration_queue import run_serialized


ACTIVE_PERCEPTION_PROPOSAL_BUILD = "0.76.0-room-search-capability-proposal"


def build_room_search_capability(actor):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    room_id = str(getattr(location.db, "room_id", "") or f"DBREF:{int(location.id)}")
    return {
        "capability_id": f"SEARCH:ROOM:{room_id}",
        "kind": "PERCEPTION",
        "label": f"Buscar indicios ocultos en {location.key}",
        "aliases": [
            "buscar indicios ocultos",
            "registrar el lugar",
            "escudrinar el entorno",
            "rastrear detalles",
            "buscar algo escondido",
        ],
        "target_name": str(location.key),
        "target_dbref": int(location.id),
        "object_action_id": None,
        "perception_mode": "ACTIVE_ROOM_SEARCH",
    }


def _compact_catalog(catalog):
    return [
        {
            "capability_id": row.get("capability_id"),
            "kind": row.get("kind"),
            "label": row.get("label"),
            "aliases": row.get("aliases"),
            "target_name": row.get("target_name"),
        }
        for row in list(catalog or [])
    ]


def build_active_perception_proposal_request(actor, raw):
    """Extend the normal current-room catalog with one generic room-search capability without exposing hidden facts."""
    base = build_action_proposal_request(actor, raw)
    catalog = [dict(row) for row in list(base.get("catalog") or [])]
    search_cap = build_room_search_capability(actor)
    if search_cap:
        catalog.append(search_cap)
    catalog.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("capability_id") or "")))

    schema = _proposal_schema(catalog)
    payload = dict(base.get("ollama_payload") or {})
    old_messages = list(payload.get("messages") or [])
    system_text = str((old_messages[0] if old_messages else {}).get("content") or "")
    prompt = (
        "AVAILABLE CAPABILITIES\n"
        + __import__("json").dumps(
            _compact_catalog(catalog),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n\nPLAYER ACTION\n"
        + str(raw or "").strip()
    )
    payload["messages"] = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": prompt},
    ]
    payload["format"] = schema

    return {
        **base,
        "build": ACTIVE_PERCEPTION_PROPOSAL_BUILD,
        "catalog": catalog,
        "schema": schema,
        "ollama_payload": payload,
        "room_search_capability": dict(search_cap) if search_cap else None,
    }


def _call_provider(provider_callable, request_packet, provider_options):
    return provider_callable(request_packet, **dict(provider_options or {}))


def dispatch_active_perception_proposal_async(
    actor,
    raw,
    *,
    on_result,
    on_failure=None,
    provider_callable=None,
    **provider_options,
):
    """Snapshot the v0.76 extended catalog on the reactor, then perform provider I/O in the serialized worker path."""
    request_packet = build_active_perception_proposal_request(actor, raw)
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
        logger.log_err(f"SIZA active perception proposal async failure: {failure}")
        if callable(on_failure):
            return on_failure(actor, failure)
        actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "build": ASYNC_ACTION_PROPOSAL_BUILD,
        "proposal_build": ACTIVE_PERCEPTION_PROPOSAL_BUILD,
        "request": request_packet,
        "deferred": deferred,
        "queued": True,
    }
