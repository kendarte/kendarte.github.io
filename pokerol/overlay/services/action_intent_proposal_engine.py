import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.object_action_engine import authored_object_actions
from services.ollama_narration_provider import DEFAULT_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_MODEL


ACTION_PROPOSAL_BUILD = "0.69.1-structured-action-intent-proposal"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_NUM_PREDICT = 160
ALLOWED_KINDS = {"OBJECT_ACTION", "MOVEMENT", "INTERACTION", "PERCEPTION", "UNSUPPORTED"}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _aliases(obj):
    try:
        return [str(value) for value in obj.aliases.all() if str(value or "").strip()]
    except Exception:
        return []


def build_local_capability_catalog(actor):
    """Return a deterministic read-only catalog of capabilities physically available from actor.location."""
    location = getattr(actor, "location", None) if actor else None
    if not actor or not location:
        return []

    rows = []

    for exit_obj in list(getattr(location, "exits", []) or []):
        destination = getattr(exit_obj, "destination", None)
        stable_id = str(getattr(exit_obj.db, "exit_id", "") or f"DBREF:{int(exit_obj.id)}")
        rows.append(
            {
                "capability_id": f"MOVE:{stable_id}",
                "kind": "MOVEMENT",
                "label": str(exit_obj.key),
                "aliases": _aliases(exit_obj),
                "target_name": getattr(destination, "key", None),
                "target_dbref": int(destination.id) if destination and getattr(destination, "id", None) is not None else None,
                "object_action_id": None,
            }
        )

    for obj in list(getattr(location, "contents", []) or []):
        if obj is actor or getattr(obj, "destination", None) or bool(getattr(obj.db, "hidden", False)):
            continue

        if bool(getattr(obj.db, "is_npc", False)):
            npc_id = str(getattr(obj.db, "npc_id", "") or f"DBREF:{int(obj.id)}")
            rows.append(
                {
                    "capability_id": f"TALK:{npc_id}",
                    "kind": "INTERACTION",
                    "label": f"Hablar con {obj.key}",
                    "aliases": _aliases(obj),
                    "target_name": str(obj.key),
                    "target_dbref": int(obj.id),
                    "object_action_id": None,
                }
            )

        rows.append(
            {
                "capability_id": f"OBSERVE:DBREF:{int(obj.id)}",
                "kind": "PERCEPTION",
                "label": f"Observar {obj.key}",
                "aliases": _aliases(obj),
                "target_name": str(obj.key),
                "target_dbref": int(obj.id),
                "object_action_id": None,
            }
        )

        for action in authored_object_actions(obj):
            if not bool(action.get("enabled", True)):
                continue
            action_id = str(action.get("id") or "")
            if not action_id:
                continue
            phrases = [str(action.get("name") or "")]
            phrases.extend(str(value) for value in _plain_list(action.get("input_phrases")) if str(value or "").strip())
            phrases.extend(str(value) for value in _plain_list(action.get("aliases")) if str(value or "").strip())
            rows.append(
                {
                    "capability_id": f"OBJECT_ACTION:DBREF:{int(obj.id)}:{action_id}",
                    "kind": "OBJECT_ACTION",
                    "label": str(action.get("name") or action_id),
                    "aliases": sorted(set(value for value in phrases if value)),
                    "target_name": str(obj.key),
                    "target_dbref": int(obj.id),
                    "object_action_id": action_id,
                }
            )

    rows.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("capability_id") or "")))
    return rows


def _proposal_schema(catalog):
    capability_ids = [str(row.get("capability_id") or "") for row in catalog if str(row.get("capability_id") or "")]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {"type": "string", "enum": sorted(ALLOWED_KINDS)},
            "capability_id": {"type": "string", "enum": [""] + capability_ids},
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Decimal confidence from 0.0 to 1.0. Never use a percentage such as 80 or 100.",
            },
            "reason": {"type": "string"},
        },
        "required": ["kind", "capability_id", "confidence", "reason"],
    }


def build_action_proposal_request(actor, raw):
    """Build a provider request containing only the current-room capability catalog and player action text."""
    catalog = build_local_capability_catalog(actor)
    schema = _proposal_schema(catalog)
    compact_catalog = [
        {
            "capability_id": row.get("capability_id"),
            "kind": row.get("kind"),
            "label": row.get("label"),
            "aliases": row.get("aliases"),
            "target_name": row.get("target_name"),
        }
        for row in catalog
    ]
    system = (
        "Eres un parser de intención de Siza, no un narrador y no ejecutas acciones. "
        "Selecciona únicamente una capability incluida en AVAILABLE CAPABILITIES cuando represente claramente la acción del jugador. "
        "Si ninguna capability corresponde, responde UNSUPPORTED con capability_id vacío. No inventes capacidades, IDs, objetos ni resultados. "
        "El campo confidence SIEMPRE es un número decimal entre 0.0 y 1.0, nunca un porcentaje: usa 1.0 para certeza total, no 100. "
        "Para UNSUPPORTED también usa la escala decimal 0.0-1.0 según tu certeza de que ninguna capability corresponde."
    )
    prompt = (
        "AVAILABLE CAPABILITIES\n"
        + json.dumps(compact_catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n\nPLAYER ACTION\n"
        + str(raw or "").strip()
    )
    payload = {
        "model": DEFAULT_OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0.0, "num_predict": DEFAULT_NUM_PREDICT},
    }
    return {
        "build": ACTION_PROPOSAL_BUILD,
        "actor": getattr(actor, "key", None) if actor else None,
        "location": getattr(getattr(actor, "location", None), "key", None) if actor else None,
        "raw": str(raw or ""),
        "catalog": catalog,
        "schema": schema,
        "ollama_payload": payload,
    }


def validate_action_proposal(proposal, catalog):
    """Validate model JSON strictly against the exact current catalog; never mutate world state."""
    if not isinstance(proposal, dict):
        return {"status": "INVALID_SHAPE", "accepted": False, "proposal": proposal}
    required = {"kind", "capability_id", "confidence", "reason"}
    if set(proposal.keys()) != required:
        return {"status": "INVALID_KEYS", "accepted": False, "proposal": proposal}

    kind = str(proposal.get("kind") or "")
    capability_id = str(proposal.get("capability_id") or "")
    if kind not in ALLOWED_KINDS:
        return {"status": "INVALID_KIND", "accepted": False, "proposal": proposal}
    try:
        confidence = float(proposal.get("confidence"))
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "accepted": False, "proposal": proposal}
    if confidence < 0 or confidence > 1:
        return {"status": "INVALID_CONFIDENCE", "accepted": False, "proposal": proposal}

    if kind == "UNSUPPORTED":
        if capability_id:
            return {"status": "UNSUPPORTED_WITH_CAPABILITY", "accepted": False, "proposal": proposal}
        return {"status": "UNSUPPORTED", "accepted": True, "proposal": proposal, "capability": None}

    by_id = {str(row.get("capability_id") or ""): row for row in catalog}
    capability = by_id.get(capability_id)
    if not capability:
        return {"status": "CAPABILITY_NOT_IN_CATALOG", "accepted": False, "proposal": proposal}
    if str(capability.get("kind") or "") != kind:
        return {"status": "KIND_MISMATCH", "accepted": False, "proposal": proposal, "capability": capability}
    return {"status": "ACCEPTED", "accepted": True, "proposal": proposal, "capability": capability}


def parse_action_proposal_response(raw, catalog, http_status=200):
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"status": "INVALID_ENCODING", "accepted": False, "http_status": int(http_status or 0)}
    try:
        packet = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (TypeError, ValueError):
        return {"status": "INVALID_JSON", "accepted": False, "http_status": int(http_status or 0)}
    message = packet.get("message") if isinstance(packet, dict) else None
    if not isinstance(message, dict):
        return {"status": "INVALID_RESPONSE", "accepted": False, "http_status": int(http_status or 0)}
    content = str(message.get("content") or "").strip()
    try:
        proposal = json.loads(content)
    except (TypeError, ValueError):
        return {"status": "INVALID_PROPOSAL_JSON", "accepted": False, "http_status": int(http_status or 0), "text": content}
    validated = validate_action_proposal(proposal, catalog)
    validated.update(
        {
            "http_status": int(http_status or 0),
            "model": packet.get("model"),
            "done": packet.get("done"),
            "done_reason": packet.get("done_reason"),
            "eval_count": packet.get("eval_count"),
            "response": packet,
        }
    )
    return validated


def call_ollama_action_proposal(actor, raw, endpoint=DEFAULT_OLLAMA_ENDPOINT, model=DEFAULT_OLLAMA_MODEL, timeout=DEFAULT_TIMEOUT_SECONDS):
    request_packet = build_action_proposal_request(actor, raw)
    payload = dict(request_packet.get("ollama_payload") or {})
    payload["model"] = str(model or DEFAULT_OLLAMA_MODEL)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = Request(str(endpoint), data=encoded, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
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
        return {"status": "HTTP_ERROR", "accepted": False, "http_status": int(getattr(exc, "code", 0) or 0), "error": str(exc), "request": request_packet, "elapsed_ms": int((time.monotonic() - started) * 1000)}
    except (URLError, socket.timeout, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        is_timeout = isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, socket.timeout)
        return {"status": "TIMEOUT" if is_timeout else "TRANSPORT_ERROR", "accepted": False, "http_status": 0, "error": str(reason or exc), "request": request_packet, "elapsed_ms": int((time.monotonic() - started) * 1000)}

    parsed = parse_action_proposal_response(raw_response, request_packet.get("catalog") or [], http_status=http_status)
    parsed.update({"build": ACTION_PROPOSAL_BUILD, "request": request_packet, "elapsed_ms": int((time.monotonic() - started) * 1000)})
    return parsed
