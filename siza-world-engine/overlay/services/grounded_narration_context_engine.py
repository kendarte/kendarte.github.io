from services.knowledge_fact_retrieval_engine import (
    DEFAULT_CHAR_BUDGET,
    DEFAULT_MAX_FACTS,
    FACT_RETRIEVAL_BUILD,
    retrieve_known_facts,
)


GROUNDED_NARRATION_BUILD = "0.65.1-grounded-narration-clean-provider-text"
DEFAULT_NARRATION_MAX_FACTS = min(6, DEFAULT_MAX_FACTS)
DEFAULT_NARRATION_CHAR_BUDGET = min(1200, DEFAULT_CHAR_BUDGET)

SYSTEM_INSTRUCTIONS = (
    "Eres el narrador de Siza. Usa únicamente el WORLD STATE y los KNOWN FACTS incluidos en esta solicitud "
    "para afirmar hechos concretos sobre el mundo, personajes, objetos, lugares o sucesos. "
    "No inventes ni completes datos ausentes. Si la información solicitada no aparece en el contexto autorizado, "
    "indica de forma natural que ese dato no está establecido o no es conocido por este personaje. "
    "No menciones identificadores internos, IDs de Facts, nombres de campos, provenance ni mecanismos del sistema. "
    "Redacta como narrador del mundo, no como depurador. Responde de forma concisa en un máximo de tres oraciones completas. "
    "Puedes redactar con fluidez, pero no conviertas inferencias en hechos."
)


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


def _prompt_text(world_state, query, fact_lines):
    entity_name = world_state.get("entity_name") or "Entidad desconocida"
    location_name = world_state.get("location_name") or "Ubicación desconocida"
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
        "GROUNDING RULE\n"
        "Toda afirmación factual específica debe estar respaldada por WORLD STATE o KNOWN FACTS. "
        "Si falta respaldo, reconoce la ausencia de información en vez de inventarla. "
        "No expongas identificadores internos ni detalles de implementación."
    )


def build_grounded_narration_request(
    entity,
    query="",
    max_facts=DEFAULT_NARRATION_MAX_FACTS,
    char_budget=DEFAULT_NARRATION_CHAR_BUDGET,
):
    """Build one deterministic provider-ready narration request without exposing omitted/unknown Facts."""
    retrieval = retrieve_known_facts(
        entity,
        query=query,
        max_facts=max_facts,
        char_budget=char_budget,
    )
    world_state = _world_state(entity, retrieval)
    selected = [_plain_dict(row) for row in _plain_list(retrieval.get("selected"))]
    fact_lines = _fact_lines(retrieval)
    prompt = _prompt_text(world_state, query, fact_lines)

    safe_context = {
        "world_state": world_state,
        "selected_fact_ids": [str(row.get("id") or "") for row in selected],
        "selected_facts": selected,
        "context_text": str(retrieval.get("context_text") or ""),
    }
    provider_payload = {
        "system": SYSTEM_INSTRUCTIONS,
        "prompt": prompt,
    }
    return {
        "build": GROUNDED_NARRATION_BUILD,
        "retrieval_build": FACT_RETRIEVAL_BUILD,
        "entity": world_state.get("entity_name"),
        "entity_npc_id": world_state.get("entity_npc_id"),
        "query": str(query or ""),
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
