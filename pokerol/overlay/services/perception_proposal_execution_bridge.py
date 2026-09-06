from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.perception_engine import resolve_perception


PERCEPTION_BRIDGE_BUILD = "0.75.0-revalidated-visible-perception-proposal-bridge"


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


def _find_local_visible_target(actor, dbref):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    for obj in list(getattr(location, "contents", []) or []):
        if getattr(obj, "id", None) != wanted:
            continue
        if getattr(obj, "destination", None):
            return None
        if bool(getattr(obj.db, "hidden", False)):
            return None
        return obj
    return None


def _render_visible_target(target, result):
    details = list((result or {}).get("visible_target_details") or [])
    target_id = int(getattr(target, "id", 0) or 0)
    chosen = None
    for row in details:
        try:
            dbref = int(row.get("dbref") or 0)
        except Exception:
            dbref = 0
        if dbref and dbref == target_id:
            chosen = row
            break
        if str(row.get("name") or "") == str(getattr(target, "key", "")):
            chosen = row
            break
    chosen = chosen or (details[0] if details else {})
    desc = str(chosen.get("desc") or getattr(target.db, "desc", "") or "").strip()
    name = str(getattr(target, "key", "") or chosen.get("name") or "objetivo").strip()
    return desc or f"Observas {name}."


def execute_validated_visible_perception_proposal(
    actor,
    proposal_result,
    *,
    min_confidence=MIN_EXECUTION_CONFIDENCE,
):
    """Execute only a fresh visible-target PERCEPTION that resolves without a roll or hidden discovery."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": PERCEPTION_BRIDGE_BUILD}
    if not isinstance(proposal_result, dict):
        return {"status": "INVALID_PROPOSAL_RESULT", "executed": False, "build": PERCEPTION_BRIDGE_BUILD}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return {
            "status": "PROPOSAL_NOT_ACCEPTED",
            "executed": False,
            "proposal_status": proposal_result.get("status"),
            "build": PERCEPTION_BRIDGE_BUILD,
        }

    proposal = _proposal_dict(proposal_result)
    if str(proposal.get("kind") or "") != "PERCEPTION":
        return {
            "status": "UNSUPPORTED_EXECUTION_KIND",
            "executed": False,
            "kind": proposal.get("kind"),
            "build": PERCEPTION_BRIDGE_BUILD,
        }

    try:
        confidence = float(proposal.get("confidence"))
        threshold = float(min_confidence)
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "executed": False, "build": PERCEPTION_BRIDGE_BUILD}
    if confidence < threshold:
        return {
            "status": "LOW_CONFIDENCE",
            "executed": False,
            "confidence": confidence,
            "required_confidence": threshold,
            "build": PERCEPTION_BRIDGE_BUILD,
        }

    capability_id = str(proposal.get("capability_id") or "").strip()
    if not capability_id:
        return {"status": "MISSING_CAPABILITY_ID", "executed": False, "build": PERCEPTION_BRIDGE_BUILD}

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
            "build": PERCEPTION_BRIDGE_BUILD,
        }
    if str(current.get("kind") or "") != "PERCEPTION":
        return {
            "status": "CURRENT_KIND_MISMATCH",
            "executed": False,
            "capability_id": capability_id,
            "current_kind": current.get("kind"),
            "build": PERCEPTION_BRIDGE_BUILD,
        }

    target = _find_local_visible_target(actor, current.get("target_dbref"))
    if not target:
        return {
            "status": "CURRENT_TARGET_NOT_LOCAL",
            "executed": False,
            "capability_id": capability_id,
            "target_dbref": current.get("target_dbref"),
            "build": PERCEPTION_BRIDGE_BUILD,
        }

    before_discovered = _plain_list(getattr(actor.db, "discovered_facts", []))
    intent = {
        "intent": "PERCEIVE",
        "sense": "sight",
        "active_search": True,
        "target": str(target.key),
        "raw": f"observar {target.key}",
    }
    result = resolve_perception(actor, intent)
    after_discovered = _plain_list(getattr(actor.db, "discovered_facts", []))

    safe = (
        str((result or {}).get("status") or "") == "AUTO_SUCCESS"
        and (result or {}).get("roll") is None
        and not list((result or {}).get("discovered") or [])
        and str(target.key) in list((result or {}).get("visible_targets") or [])
        and after_discovered == before_discovered
    )
    if not safe:
        actor.db.discovered_facts = before_discovered
        return {
            "status": "PERCEPTION_MUTATION_OR_DISCOVERY_BLOCKED",
            "executed": False,
            "capability_id": capability_id,
            "engine_status": (result or {}).get("status"),
            "roll": (result or {}).get("roll"),
            "discovered": list((result or {}).get("discovered") or []),
            "build": PERCEPTION_BRIDGE_BUILD,
        }

    rendered = _render_visible_target(target, result)
    return {
        "status": "PERCEPTION_EXECUTED",
        "executed": True,
        "capability_id": capability_id,
        "confidence": confidence,
        "required_confidence": threshold,
        "current_capability": dict(current),
        "target_dbref": int(target.id),
        "target_name": str(target.key),
        "response_text": rendered,
        "engine_status": str(result.get("status") or ""),
        "roll": None,
        "discovered": [],
        "build": PERCEPTION_BRIDGE_BUILD,
    }
