import re
import unicodedata

from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts


FACT_RETRIEVAL_BUILD = "0.64.1-deterministic-known-fact-retrieval"
DEFAULT_MAX_FACTS = 8
DEFAULT_CHAR_BUDGET = 1600
_TOKEN_RE = re.compile(r"[a-z0-9_:-]+")


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


def _fold(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _tokens(value):
    return tuple(sorted(set(_TOKEN_RE.findall(_fold(value)))))


def _fact_search_text(fact):
    source = _plain_dict((fact or {}).get("source"))
    parts = [
        (fact or {}).get("id"),
        (fact or {}).get("topic"),
        (fact or {}).get("text"),
        (fact or {}).get("knowledge_key"),
        source.get("object_id"),
        source.get("object_name"),
        source.get("site_room_id"),
        source.get("site_name"),
    ]
    return " ".join(str(part) for part in parts if part is not None)


def _current_site(entity, explicit_site=None):
    site = explicit_site or getattr(entity, "location", None)
    if not site:
        return {"room_id": None, "name": None, "dbref": None}
    return {
        "room_id": str(getattr(site.db, "room_id", "") or "") or None,
        "name": getattr(site, "key", None),
        "dbref": int(site.id) if getattr(site, "id", None) is not None else None,
    }


def _site_match(fact, site):
    source = _plain_dict((fact or {}).get("source"))
    room_id = str(site.get("room_id") or "")
    site_name = _fold(site.get("name"))
    source_room_id = str(source.get("site_room_id") or "")
    source_name = _fold(source.get("site_name"))
    return bool(
        (room_id and source_room_id and room_id == source_room_id)
        or (site_name and source_name and site_name == source_name)
    )


def _relevance(fact, query_tokens, query_folded, site):
    fact_id = _fold((fact or {}).get("id"))
    knowledge_key = _fold((fact or {}).get("knowledge_key"))
    search_text = _fact_search_text(fact)
    fact_tokens = set(_tokens(search_text))
    overlap = sorted(set(query_tokens).intersection(fact_tokens))

    semantic_score = 0
    score = 0
    reasons = []
    if query_folded and query_folded == fact_id:
        semantic_score += 1000
        score += 1000
        reasons.append("EXACT_FACT_ID")
    if query_folded and query_folded == knowledge_key:
        semantic_score += 800
        score += 800
        reasons.append("EXACT_KNOWLEDGE_KEY")
    if overlap:
        semantic_score += 100 * len(overlap)
        score += 100 * len(overlap)
        reasons.append(f"TOKEN_OVERLAP:{','.join(overlap)}")

    # Location is only a ranking bias among already relevant Facts. It must
    # never make an unrelated Fact eligible for a non-empty semantic query.
    if _site_match(fact, site):
        score += 50
        reasons.append("CURRENT_SITE_SOURCE")

    return score, semantic_score, reasons


def _context_line(fact):
    fact_id = str((fact or {}).get("id") or "")
    topic = str((fact or {}).get("topic") or fact_id)
    text = str((fact or {}).get("text") or "").strip()
    payload = text or topic
    return f"[{fact_id}] {payload}"


def _selected_fact_packet(fact, state, score, reasons, line):
    return {
        "id": str((fact or {}).get("id") or ""),
        "topic": (fact or {}).get("topic"),
        "text": (fact or {}).get("text"),
        "knowledge_key": state.get("knowledge_key"),
        "knowledge_level": state.get("level"),
        "required_level": state.get("required_level"),
        "canon_status": (fact or {}).get("canon_status") or (fact or {}).get("status") or "prototype",
        "source": _plain_dict((fact or {}).get("source")),
        "learned_by": _plain_dict((fact or {}).get("learned_by")),
        "transfer_history": [_plain_dict(row) for row in _plain_list((fact or {}).get("transfer_history"))],
        "relevance_score": int(score),
        "relevance_reasons": list(reasons),
        "context_line": line,
    }


def retrieve_known_facts(entity, query="", site=None, max_facts=DEFAULT_MAX_FACTS, char_budget=DEFAULT_CHAR_BUDGET):
    """Build a deterministic, read-only context packet from Facts this entity actually knows."""
    try:
        max_facts = max(0, int(max_facts))
    except (TypeError, ValueError):
        max_facts = DEFAULT_MAX_FACTS
    try:
        char_budget = max(0, int(char_budget))
    except (TypeError, ValueError):
        char_budget = DEFAULT_CHAR_BUDGET

    query_folded = _fold(query)
    query_tokens = _tokens(query)
    site_packet = _current_site(entity, explicit_site=site)
    candidates = []
    omitted = []

    for fact in knowledge_facts(entity):
        fact_id = str(fact.get("id") or "")
        state = fact_knowledge_state(entity, fact)
        if not bool(state.get("known")):
            omitted.append({"id": fact_id, "reason": "UNKNOWN"})
            continue

        score, semantic_score, reasons = _relevance(fact, query_tokens, query_folded, site_packet)
        if query_folded and semantic_score <= 0:
            omitted.append({"id": fact_id, "reason": "NOT_RELEVANT"})
            continue

        line = _context_line(fact)
        candidates.append(
            {
                "fact": fact,
                "state": state,
                "score": score,
                "reasons": reasons,
                "line": line,
            }
        )

    candidates.sort(key=lambda row: (-int(row.get("score") or 0), str((row.get("fact") or {}).get("id") or "")))

    selected = []
    context_lines = []
    used_chars = 0
    for row in candidates:
        fact_id = str((row.get("fact") or {}).get("id") or "")
        if len(selected) >= max_facts:
            omitted.append({"id": fact_id, "reason": "MAX_FACTS"})
            continue

        line = str(row.get("line") or "")
        incremental = len(line) + (1 if context_lines else 0)
        if used_chars + incremental > char_budget:
            omitted.append({"id": fact_id, "reason": "CHAR_BUDGET"})
            continue

        selected.append(
            _selected_fact_packet(
                row.get("fact") or {},
                row.get("state") or {},
                row.get("score") or 0,
                row.get("reasons") or [],
                line,
            )
        )
        context_lines.append(line)
        used_chars += incremental

    omitted.sort(key=lambda row: (str(row.get("reason") or ""), str(row.get("id") or "")))
    return {
        "build": FACT_RETRIEVAL_BUILD,
        "entity": getattr(entity, "key", None) if entity else None,
        "entity_npc_id": str(getattr(getattr(entity, "db", None), "npc_id", "") or "") if entity else None,
        "query": str(query or ""),
        "query_tokens": list(query_tokens),
        "site": site_packet,
        "max_facts": max_facts,
        "char_budget": char_budget,
        "used_chars": used_chars,
        "selected": selected,
        "selected_fact_ids": [row.get("id") for row in selected],
        "omitted": omitted,
        "context_text": "\n".join(context_lines),
    }
