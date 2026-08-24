from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.active_perception_proposal_runtime import build_room_search_capability
from services.perception_engine import normalize, resolve_perception


ACTIVE_PERCEPTION_BRIDGE_BUILD = "0.76.0-revalidated-active-perception-execution-bridge"


_SEARCH_NOISE = {
    "me", "pongo", "puse", "quiero", "trato", "intento", "a", "al", "el", "la", "los", "las",
    "de", "del", "en", "por", "para", "que", "si", "hay", "un", "una", "unos", "unas", "algo",
    "algun", "alguna", "detras", "debajo", "dentro", "encima", "cerca", "entre", "hacia", "sobre",
    "fijo", "fijarme", "escudrino", "escudrinar", "rastreo", "rastrear", "registro", "registrar",
    "indago", "indagar", "hurgo", "hurgar", "miro", "mirar", "veo", "ver", "busco", "buscar",
    "reviso", "revisar", "examino", "examinar", "inspecciono", "inspeccionar", "investigo", "investigar",
    "cuidadosamente", "detenidamente", "minuciosamente", "atentamente", "bien", "raro", "rara", "raros",
    "escondido", "escondida", "oculto", "oculta", "pista", "pistas", "indicio", "indicios", "detalle", "detalles",
}


def _proposal_dict(proposal_result):
    try:
        return {str(key): value for key, value in (proposal_result.get("proposal") or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def extract_active_search_target(raw):
    """Derive only a search target from player-authored text; model prose is never consulted."""
    tokens = [token for token in normalize(str(raw or "")).split() if token]
    meaningful = [token for token in tokens if token not in _SEARCH_NOISE]
    return " ".join(meaningful).strip()


def _sentence(text):
    value = str(text or "").strip().rstrip(".")
    if not value:
        return ""
    return value[:1].upper() + value[1:] + "."


def _render_active_search(result):
    status = str((result or {}).get("status") or "")
    target = str((result or {}).get("target") or "").strip()
    if status == "DISCOVERY":
        discovered = [str(item).strip() for item in list((result or {}).get("discovered") or []) if str(item).strip()]
        return " ".join(_sentence(item) for item in discovered) or "La búsqueda no descubre ningún detalle nuevo."
    if status == "NO_DISCOVERY":
        if target:
            return f"Buscas indicios relacionados con {target}, pero no descubres ningún detalle nuevo."
        return "La búsqueda no descubre ningún detalle nuevo."
    if status == "NO_AUTHORIZED_DISCOVERY":
        if target:
            return f"La búsqueda no aporta información nueva sobre {target}."
        return "La búsqueda no aporta información nueva."
    if status == "AUTO_SUCCESS":
        details = list((result or {}).get("visible_target_details") or [])
        if details:
            detail = details[0] or {}
            name = str(detail.get("name") or "el objetivo")
            desc = str(detail.get("desc") or "").strip()
            return (f"Distingues {name}. " + desc).strip()
        visible = [str(item) for item in list((result or {}).get("visible_targets") or []) if item]
        if visible:
            return "A simple vista distingues " + ", ".join(visible) + "."
    return "No obtienes información nueva con esa búsqueda."


def execute_validated_active_perception_proposal(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    min_confidence=MIN_EXECUTION_CONFIDENCE,
):
    """Revalidate the current-room SEARCH capability, then let the existing perception engine own roll/discovery persistence."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": ACTIVE_PERCEPTION_BRIDGE_BUILD}
    if not isinstance(proposal_result, dict):
        return {"status": "INVALID_PROPOSAL_RESULT", "executed": False, "build": ACTIVE_PERCEPTION_BRIDGE_BUILD}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return {
            "status": "PROPOSAL_NOT_ACCEPTED",
            "executed": False,
            "proposal_status": proposal_result.get("status"),
            "build": ACTIVE_PERCEPTION_BRIDGE_BUILD,
        }

    proposal = _proposal_dict(proposal_result)
    if str(proposal.get("kind") or "") != "PERCEPTION":
        return {
            "status": "UNSUPPORTED_EXECUTION_KIND",
            "executed": False,
            "kind": proposal.get("kind"),
            "build": ACTIVE_PERCEPTION_BRIDGE_BUILD,
        }

    try:
        confidence = float(proposal.get("confidence"))
        threshold = float(min_confidence)
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "executed": False, "build": ACTIVE_PERCEPTION_BRIDGE_BUILD}
    if confidence < threshold:
        return {
            "status": "LOW_CONFIDENCE",
            "executed": False,
            "confidence": confidence,
            "required_confidence": threshold,
            "build": ACTIVE_PERCEPTION_BRIDGE_BUILD,
        }

    capability_id = str(proposal.get("capability_id") or "").strip()
    current = build_room_search_capability(actor)
    if not current or capability_id != str(current.get("capability_id") or ""):
        return {
            "status": "STALE_OR_MISSING_CAPABILITY",
            "executed": False,
            "capability_id": capability_id,
            "current_capability_id": (current or {}).get("capability_id"),
            "build": ACTIVE_PERCEPTION_BRIDGE_BUILD,
        }

    target = extract_active_search_target(raw_player_input)
    before_discovered = _plain_list(getattr(actor.db, "discovered_facts", []))
    intent = {
        "intent": "PERCEIVE",
        "sense": "sight",
        "active_search": True,
        "target": target,
        "raw": str(raw_player_input or ""),
    }
    result = resolve_perception(actor, intent)
    status = str((result or {}).get("status") or "")
    after_discovered = _plain_list(getattr(actor.db, "discovered_facts", []))

    if status not in {"DISCOVERY", "NO_DISCOVERY", "NO_AUTHORIZED_DISCOVERY", "AUTO_SUCCESS"}:
        actor.db.discovered_facts = before_discovered
        return {
            "status": "ACTIVE_PERCEPTION_ENGINE_REJECTED",
            "executed": False,
            "engine_status": status,
            "build": ACTIVE_PERCEPTION_BRIDGE_BUILD,
        }

    added = [item for item in after_discovered if str(item) not in {str(value) for value in before_discovered}]
    response_text = _render_active_search(result)
    return {
        "status": "ACTIVE_PERCEPTION_EXECUTED",
        "executed": True,
        "capability_id": capability_id,
        "confidence": confidence,
        "required_confidence": threshold,
        "current_capability": dict(current),
        "room_dbref": int(actor.location.id) if getattr(actor, "location", None) else None,
        "room_name": getattr(getattr(actor, "location", None), "key", None),
        "search_target": target or None,
        "target_source": "PLAYER_INPUT",
        "engine_status": status,
        "roll": (result or {}).get("roll"),
        "discovered": list((result or {}).get("discovered") or []),
        "discovered_fact_ids_added": added,
        "response_text": response_text,
        "build": ACTIVE_PERCEPTION_BRIDGE_BUILD,
    }
