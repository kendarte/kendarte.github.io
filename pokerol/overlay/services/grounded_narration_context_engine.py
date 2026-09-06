from services.knowledge_fact_retrieval_engine import (
    DEFAULT_CHAR_BUDGET,
    DEFAULT_MAX_FACTS,
    FACT_RETRIEVAL_BUILD,
    retrieve_known_facts,
)
from services.player_language_contract import (
    detect_player_language,
    get_actor_turn_language,
    language_instruction,
    normalize_player_language,
)


GROUNDED_NARRATION_BUILD = "0.65.3-grounded-narration-bilingual-presentation"
DEFAULT_NARRATION_MAX_FACTS = min(6, DEFAULT_MAX_FACTS)
DEFAULT_NARRATION_CHAR_BUDGET = min(1200, DEFAULT_CHAR_BUDGET)


def _system_instructions(language):
    language = normalize_player_language(language)
    return (
        "You are Siza's narrator. Use only the WORLD STATE and KNOWN FACTS included in this request "
        "when stating concrete facts about the world, characters, objects, locations, or events. "
        "Do not invent or fill in missing information. If the requested information is absent from the authorized context, "
        "say naturally that it is not established or not known by this character. "
        "Never mention internal identifiers, Fact IDs, field names, provenance, or system mechanics. "
        "Write as the narrator of the world, not as a debugger, using no more than three complete sentences. "
        "Authorized Facts may be written in a different source language; preserve their meaning exactly while presenting them in the requested player language. "
        "You may write fluently, but never turn inference into fact. "
        + language_instruction(language)
    )


# Kept for compatibility with callers that inspect the module constant directly.
SYSTEM_INSTRUCTIONS = _system_instructions("es")


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


def _world_state(entity, retrieval):
    site = _plain_dict((retrieval or {}).get("site"))
    return {
        "entity_name": getattr(entity, "key", None) if entity else None,
        "entity_npc_id": str(getattr(getattr(entity, "db", None), "npc_id", "") or "") if entity else None,
        "location_name": site.get("name"),
        "location_room_id": site.get("room_id"),
        "location_dbref": site.get("dbref"),
    }


def _fact_lines(retrieval):
    """Provider-facing Fact text deliberately excludes internal Fact IDs and provenance metadata."""
    output = []
    for raw in _plain_list((retrieval or {}).get("selected")):
        row = _plain_dict(raw)
        text = str(row.get("text") or "").strip()
        topic = str(row.get("topic") or "").strip()
        payload = text or topic
        if payload:
            output.append(payload)
    return output


def _prompt_text(world_state, query, fact_lines, language="es"):
    language = normalize_player_language(language)
    entity_name = world_state.get("entity_name") or "Unknown entity"
    location_name = world_state.get("location_name") or "Unknown location"
    known_block = "\n".join(fact_lines) if fact_lines else "NONE"
    request = str(query or "").strip()
    return (
        "WORLD STATE\n"
        f"Entity: {entity_name}\n"
        f"Location: {location_name}\n\n"
        "KNOWN FACTS\n"
        f"{known_block}\n\n"
        "REQUEST\n"
        f"{request}\n\n"
        f"PLAYER LANGUAGE\n{language}\n\n"
        "GROUNDING RULE\n"
        "Every specific factual claim must be supported by WORLD STATE or KNOWN FACTS. "
        "If support is missing, acknowledge the missing information instead of inventing it. "
        "Do not expose internal identifiers or implementation details. "
        + language_instruction(language)
    )


def _resolve_request_language(entity, query, language):
    explicit = str(language or "").strip().lower()
    if explicit in {"es", "en"}:
        return explicit
    previous = get_actor_turn_language(entity) if entity is not None else "es"
    if str(query or "").strip():
        return detect_player_language(query, previous_language=previous).get("language") or previous
    return previous


def build_grounded_narration_request(
    entity,
    query="",
    max_facts=DEFAULT_NARRATION_MAX_FACTS,
    char_budget=DEFAULT_NARRATION_CHAR_BUDGET,
    language=None,
):
    """Build one deterministic provider-ready narration request without exposing omitted/unknown Facts."""
    player_language = _resolve_request_language(entity, query, language)
    retrieval = retrieve_known_facts(
        entity,
        query=query,
        max_facts=max_facts,
        char_budget=char_budget,
    )
    world_state = _world_state(entity, retrieval)
    selected = [_plain_dict(row) for row in _plain_list(retrieval.get("selected"))]
    fact_lines = _fact_lines(retrieval)
    prompt = _prompt_text(world_state, query, fact_lines, player_language)

    safe_context = {
        "world_state": world_state,
        "selected_fact_ids": [str(row.get("id") or "") for row in selected],
        "selected_facts": selected,
        "context_text": str(retrieval.get("context_text") or ""),
    }
    provider_payload = {
        "system": _system_instructions(player_language),
        "prompt": prompt,
    }
    return {
        "build": GROUNDED_NARRATION_BUILD,
        "retrieval_build": FACT_RETRIEVAL_BUILD,
        "entity": world_state.get("entity_name"),
        "entity_npc_id": world_state.get("entity_npc_id"),
        "query": str(query or ""),
        "player_language": player_language,
        "grounded": True,
        "has_relevant_facts": bool(selected),
        "safe_context": safe_context,
        "provider_payload": provider_payload,
        "diagnostics": {
            "selected_count": len(selected),
            "used_chars": int(retrieval.get("used_chars") or 0),
            "char_budget": int(retrieval.get("char_budget") or 0),
            "max_facts": int(retrieval.get("max_facts") or 0),
            "omitted": [_plain_dict(row) for row in _plain_list(retrieval.get("omitted"))],
        },
    }
