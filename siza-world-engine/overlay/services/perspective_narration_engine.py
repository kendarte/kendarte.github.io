from services.grounded_narration_context_engine import build_grounded_narration_request
from services.ollama_narration_provider import call_ollama_chat


PERSPECTIVE_NARRATION_BUILD = "0.67.0-viewer-authorized-grounded-narration"


def build_viewer_grounded_request(viewer, query="", max_facts=6, char_budget=1200):
    """Build narration strictly from Facts known by the viewer, never from a referenced NPC's private state."""
    grounded = build_grounded_narration_request(
        viewer,
        query=query,
        max_facts=max_facts,
        char_budget=char_budget,
    )
    safe = dict(grounded.get("safe_context") or {})
    world_state = dict(safe.get("world_state") or {})
    perspective = {
        "viewer_name": getattr(viewer, "key", None) if viewer else None,
        "viewer_dbref": int(viewer.id) if viewer and getattr(viewer, "id", None) is not None else None,
        "viewer_npc_id": str(getattr(getattr(viewer, "db", None), "npc_id", "") or "") if viewer else None,
        "knowledge_owner": "VIEWER",
        "location_name": world_state.get("location_name"),
        "location_room_id": world_state.get("location_room_id"),
    }
    return {
        "build": PERSPECTIVE_NARRATION_BUILD,
        "grounded_build": grounded.get("build"),
        "retrieval_build": grounded.get("retrieval_build"),
        "query": str(query or ""),
        "perspective": perspective,
        "safe_context": safe,
        "provider_payload": dict(grounded.get("provider_payload") or {}),
        "diagnostics": dict(grounded.get("diagnostics") or {}),
        "grounded": bool(grounded.get("grounded")),
        "has_relevant_facts": bool(grounded.get("has_relevant_facts")),
    }


def narrate_for_viewer(viewer, query="", **provider_options):
    """Run one read-only grounded narration from the viewer's authorized knowledge perspective."""
    request = build_viewer_grounded_request(viewer, query=query)
    result = call_ollama_chat(request.get("provider_payload") or {}, **provider_options)
    return {
        "build": PERSPECTIVE_NARRATION_BUILD,
        "request": request,
        "provider_result": result,
        "text": str(result.get("text") or "") if isinstance(result, dict) else "",
        "status": result.get("status") if isinstance(result, dict) else "INVALID_PROVIDER_RESULT",
    }
