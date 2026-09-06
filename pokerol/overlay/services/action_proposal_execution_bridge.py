from services.action_intent_proposal_engine import build_local_capability_catalog
from services.object_action_engine import begin_object_action


ACTION_BRIDGE_BUILD = "0.70.1-campaign-observed-object-action-execution-bridge"
MIN_EXECUTION_CONFIDENCE = 0.90


def _proposal_dict(proposal_result):
    try:
        return {str(key): value for key, value in (proposal_result.get("proposal") or {}).items()}
    except Exception:
        return {}


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _campaign_tags(engine_result):
    metadata = _plain_dict((engine_result or {}).get("metadata"))
    return sorted(
        {
            str(value).strip()
            for value in _plain_list(metadata.get("campaign_tags"))
            if str(value or "").strip()
        }
    )


def _observe_completed_campaign_action(actor, engine_result, action_id):
    if str((engine_result or {}).get("status") or "") != "COMPLETED":
        return None
    tags = _campaign_tags(engine_result)
    if not tags:
        return None

    from services.dm_campaign_registry import observe_active_campaign_evidence

    metadata = _plain_dict((engine_result or {}).get("metadata"))
    return observe_active_campaign_evidence(
        actor,
        {
            "authority": "WORLD_ENGINE",
            "source": "OBJECT_ACTION_EXECUTION",
            "action_types": ["OBJECT_ACTION_EXECUTED"],
            "campaign_tags": tags,
            "campaign_id": metadata.get("campaign_id"),
            "object_action_id": str(action_id or ""),
            "object_id": (engine_result or {}).get("object_id"),
            "object_dbref": (engine_result or {}).get("object_dbref"),
            "outcome": (engine_result or {}).get("outcome"),
            "result": {
                "status": (engine_result or {}).get("status"),
                "attempt_id": (engine_result or {}).get("attempt_id"),
            },
        },
    )


def _find_local_object(actor, dbref):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    for obj in list(getattr(location, "contents", []) or []):
        if getattr(obj, "id", None) == wanted:
            return obj
    return None


def execute_validated_object_action_proposal(
    actor,
    proposal_result,
    *,
    min_confidence=MIN_EXECUTION_CONFIDENCE,
    attempt_id=None,
):
    """Revalidate one accepted v0.69 OBJECT_ACTION proposal against current world state, then delegate to the real engine."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": ACTION_BRIDGE_BUILD}
    if not isinstance(proposal_result, dict):
        return {"status": "INVALID_PROPOSAL_RESULT", "executed": False, "build": ACTION_BRIDGE_BUILD}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return {
            "status": "PROPOSAL_NOT_ACCEPTED",
            "executed": False,
            "proposal_status": proposal_result.get("status"),
            "build": ACTION_BRIDGE_BUILD,
        }

    proposal = _proposal_dict(proposal_result)
    if str(proposal.get("kind") or "") != "OBJECT_ACTION":
        return {
            "status": "UNSUPPORTED_EXECUTION_KIND",
            "executed": False,
            "kind": proposal.get("kind"),
            "build": ACTION_BRIDGE_BUILD,
        }

    try:
        confidence = float(proposal.get("confidence"))
        threshold = float(min_confidence)
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "executed": False, "build": ACTION_BRIDGE_BUILD}
    if confidence < threshold:
        return {
            "status": "LOW_CONFIDENCE",
            "executed": False,
            "confidence": confidence,
            "required_confidence": threshold,
            "build": ACTION_BRIDGE_BUILD,
        }

    capability_id = str(proposal.get("capability_id") or "").strip()
    if not capability_id:
        return {"status": "MISSING_CAPABILITY_ID", "executed": False, "build": ACTION_BRIDGE_BUILD}

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
            "build": ACTION_BRIDGE_BUILD,
        }
    if str(current.get("kind") or "") != "OBJECT_ACTION":
        return {
            "status": "CURRENT_KIND_MISMATCH",
            "executed": False,
            "capability_id": capability_id,
            "current_kind": current.get("kind"),
            "build": ACTION_BRIDGE_BUILD,
        }

    obj = _find_local_object(actor, current.get("target_dbref"))
    if not obj:
        return {
            "status": "CURRENT_TARGET_NOT_LOCAL",
            "executed": False,
            "capability_id": capability_id,
            "target_dbref": current.get("target_dbref"),
            "build": ACTION_BRIDGE_BUILD,
        }

    action_id = str(current.get("object_action_id") or "").strip()
    if not action_id:
        return {
            "status": "CURRENT_ACTION_ID_MISSING",
            "executed": False,
            "capability_id": capability_id,
            "build": ACTION_BRIDGE_BUILD,
        }

    engine_result = begin_object_action(actor, obj, action_id, attempt_id=attempt_id)
    engine_status = str(engine_result.get("status") or "")
    accepted_statuses = {"PENDING_RESOLUTION", "COMPLETED"}
    campaign_observation = _observe_completed_campaign_action(actor, engine_result, action_id)
    if campaign_observation is not None:
        engine_result = {**dict(engine_result), "campaign_observation": campaign_observation}

    return {
        "status": "WORLD_ENGINE_ACCEPTED" if engine_status in accepted_statuses else "WORLD_ENGINE_REJECTED",
        "executed": engine_status in accepted_statuses,
        "capability_id": capability_id,
        "confidence": confidence,
        "required_confidence": threshold,
        "current_capability": dict(current),
        "world_engine_status": engine_status,
        "world_engine_result": engine_result,
        "campaign_observation": campaign_observation,
        "build": ACTION_BRIDGE_BUILD,
    }
