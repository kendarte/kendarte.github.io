from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE


MOVEMENT_BRIDGE_BUILD = "0.72.0-revalidated-movement-execution-bridge"


def _proposal_dict(proposal_result):
    try:
        return {str(key): value for key, value in (proposal_result.get("proposal") or {}).items()}
    except Exception:
        return {}


def _movement_capability_id(exit_obj):
    if not exit_obj:
        return ""
    stable_id = str(getattr(exit_obj.db, "exit_id", "") or f"DBREF:{int(exit_obj.id)}")
    return f"MOVE:{stable_id}"


def _find_current_exit(actor, capability_id):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    wanted = str(capability_id or "").strip()
    for exit_obj in list(getattr(location, "exits", []) or []):
        if _movement_capability_id(exit_obj) == wanted:
            return exit_obj
    return None


def execute_validated_movement_proposal(
    actor,
    proposal_result,
    *,
    min_confidence=MIN_EXECUTION_CONFIDENCE,
):
    """Revalidate one accepted MOVEMENT proposal, then execute the exact current Evennia Exit command."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": MOVEMENT_BRIDGE_BUILD}
    if not isinstance(proposal_result, dict):
        return {"status": "INVALID_PROPOSAL_RESULT", "executed": False, "build": MOVEMENT_BRIDGE_BUILD}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return {
            "status": "PROPOSAL_NOT_ACCEPTED",
            "executed": False,
            "proposal_status": proposal_result.get("status"),
            "build": MOVEMENT_BRIDGE_BUILD,
        }

    proposal = _proposal_dict(proposal_result)
    if str(proposal.get("kind") or "") != "MOVEMENT":
        return {
            "status": "UNSUPPORTED_EXECUTION_KIND",
            "executed": False,
            "kind": proposal.get("kind"),
            "build": MOVEMENT_BRIDGE_BUILD,
        }

    try:
        confidence = float(proposal.get("confidence"))
        threshold = float(min_confidence)
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "executed": False, "build": MOVEMENT_BRIDGE_BUILD}
    if confidence < threshold:
        return {
            "status": "LOW_CONFIDENCE",
            "executed": False,
            "confidence": confidence,
            "required_confidence": threshold,
            "build": MOVEMENT_BRIDGE_BUILD,
        }

    capability_id = str(proposal.get("capability_id") or "").strip()
    if not capability_id:
        return {"status": "MISSING_CAPABILITY_ID", "executed": False, "build": MOVEMENT_BRIDGE_BUILD}

    current_catalog = build_local_capability_catalog(actor)
    current = next(
        (row for row in current_catalog if str(row.get("capability_id") or "") == capability_id),
        None,
    )
    if not current:
        return {
            "status": "STALE_OR_MISSING_CAPABILITY",
            "executed": False,
            "capability_id": capability_id,
            "current_catalog_count": len(current_catalog),
            "build": MOVEMENT_BRIDGE_BUILD,
        }
    if str(current.get("kind") or "") != "MOVEMENT":
        return {
            "status": "CURRENT_KIND_MISMATCH",
            "executed": False,
            "capability_id": capability_id,
            "current_kind": current.get("kind"),
            "build": MOVEMENT_BRIDGE_BUILD,
        }

    exit_obj = _find_current_exit(actor, capability_id)
    if not exit_obj:
        return {
            "status": "CURRENT_EXIT_NOT_FOUND",
            "executed": False,
            "capability_id": capability_id,
            "build": MOVEMENT_BRIDGE_BUILD,
        }

    destination = getattr(exit_obj, "destination", None)
    expected_dbref = current.get("target_dbref")
    if not destination or getattr(destination, "id", None) != expected_dbref:
        return {
            "status": "DESTINATION_MISMATCH",
            "executed": False,
            "capability_id": capability_id,
            "expected_target_dbref": expected_dbref,
            "actual_target_dbref": int(destination.id) if destination and getattr(destination, "id", None) is not None else None,
            "build": MOVEMENT_BRIDGE_BUILD,
        }

    origin = getattr(actor, "location", None)
    actor.execute_cmd(str(exit_obj.key))
    final_location = getattr(actor, "location", None)
    moved = bool(final_location is destination)
    return {
        "status": "MOVEMENT_EXECUTED" if moved else "MOVEMENT_REJECTED",
        "executed": moved,
        "capability_id": capability_id,
        "confidence": confidence,
        "required_confidence": threshold,
        "exit_key": str(exit_obj.key),
        "origin_name": getattr(origin, "key", None),
        "origin_dbref": int(origin.id) if origin and getattr(origin, "id", None) is not None else None,
        "destination_name": getattr(destination, "key", None),
        "destination_dbref": int(destination.id) if destination and getattr(destination, "id", None) is not None else None,
        "final_location_name": getattr(final_location, "key", None),
        "final_location_dbref": int(final_location.id) if final_location and getattr(final_location, "id", None) is not None else None,
        "current_capability": dict(current),
        "build": MOVEMENT_BRIDGE_BUILD,
    }
