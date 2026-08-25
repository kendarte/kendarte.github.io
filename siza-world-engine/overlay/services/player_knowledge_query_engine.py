from services.interaction_engine import normalize
from services.knowledge_fact_retrieval_engine import retrieve_known_facts


PLAYER_KNOWLEDGE_QUERY_BUILD = "0.83.0-deterministic-player-known-fact-query"
MAX_QUERY_FACTS = 5

_QUERY_PREFIXES = (
    "que se sobre ",
    "que se de ",
    "que conozco sobre ",
    "que conozco de ",
    "que informacion tengo sobre ",
    "que informacion tengo de ",
    "que datos tengo sobre ",
    "que datos tengo de ",
)

_QUERY_STOPWORDS = {
    "a", "al", "el", "la", "los", "las", "de", "del", "en", "por", "para",
    "un", "una", "unos", "unas", "que", "sobre", "acerca", "tema", "asunto",
    "esto", "eso", "esta", "este", "ese", "esa", "lo", "le", "me", "mi",
    "con", "sin", "bajo", "tras", "detras", "debajo", "encima",
}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _clean_query(topic):
    tokens = [
        token for token in normalize(topic).split()
        if token and token not in _QUERY_STOPWORDS
    ]
    return " ".join(tokens).strip()


def parse_player_knowledge_query(raw):
    """Recognize only explicit first-person requests to inspect the player's own known Facts."""
    normalized = normalize(raw)
    if not normalized:
        return None

    topic = ""
    matched_prefix = ""
    for prefix in _QUERY_PREFIXES:
        if normalized.startswith(prefix):
            matched_prefix = prefix.strip()
            topic = normalized[len(prefix):].strip()
            break

    if not topic:
        return None

    retrieval_query = _clean_query(topic)
    if not retrieval_query:
        return None

    return {
        "intent": "QUERY_KNOWLEDGE",
        "topic": topic,
        "topic_source": "PLAYER_INPUT",
        "retrieval_query": retrieval_query,
        "retrieval_query_source": "PLAYER_INPUT_FILTERED",
        "matched_prefix": matched_prefix,
        "raw": str(raw or ""),
        "build": PLAYER_KNOWLEDGE_QUERY_BUILD,
    }


def query_player_known_facts(actor, raw, *, max_facts=MAX_QUERY_FACTS):
    """Retrieve only Facts the actor already knows. This is read-only and never calls an LLM."""
    intent = parse_player_knowledge_query(raw)
    if not intent:
        return {
            "status": "NOT_KNOWLEDGE_QUERY",
            "handled": False,
            "build": PLAYER_KNOWLEDGE_QUERY_BUILD,
        }

    retrieval = retrieve_known_facts(
        actor,
        query=intent.get("retrieval_query") or "",
        site=getattr(actor, "location", None),
        max_facts=max_facts,
    )
    selected = _plain_list(retrieval.get("selected"))

    public_facts = []
    seen_text = set()
    for raw_fact in selected:
        try:
            fact = {str(key): value for key, value in raw_fact.items()}
        except Exception:
            continue
        text = " ".join(str(fact.get("text") or "").split()).strip()
        if not text or text in seen_text:
            continue
        seen_text.add(text)
        public_facts.append(
            {
                "topic": str(fact.get("topic") or "").strip() or None,
                "text": text,
            }
        )

    topic = str(intent.get("topic") or "").strip()
    if not public_facts:
        response_text = f"No tienes información conocida sobre {topic}."
        status = "NO_KNOWN_FACTS"
    elif len(public_facts) == 1:
        response_text = public_facts[0]["text"]
        status = "KNOWN_FACTS_FOUND"
    else:
        lines = [f"Sobre {topic}, sabes lo siguiente:"]
        lines.extend(fact["text"] for fact in public_facts)
        response_text = "\n".join(lines)
        status = "KNOWN_FACTS_FOUND"

    return {
        "status": status,
        "handled": True,
        "topic": topic,
        "topic_source": "PLAYER_INPUT",
        "retrieval_query": intent.get("retrieval_query"),
        "retrieval_query_source": "PLAYER_INPUT_FILTERED",
        "facts": public_facts,
        "fact_count": len(public_facts),
        "response_text": response_text,
        "build": PLAYER_KNOWLEDGE_QUERY_BUILD,
    }
