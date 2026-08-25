from services.conversation_fact_acquisition_engine import acquire_fact_from_new_conversation
from services.interaction_engine import (
    _extract_topic,
    _find_npc,
    _plain_dict,
    _plain_list,
    _record_conversation,
    normalize,
)
from services.interaction_proposal_execution_bridge import extract_player_authored_topic
from services.knowledge_context_engine import fact_knowledge_state
from services.npc_fact_disclosure_engine import _visible_local_npc_by_dbref
from services.npc_fact_disclosure_state_engine import evaluate_fact_disclosure_v85


RANKED_FACT_CONVERSATION_BUILD = "0.86.1-ranked-topic-single-fact-authority"
_TOPIC_STOPWORDS = {
    "a", "al", "de", "del", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "con", "en", "por", "para", "sobre", "que", "y", "o", "se", "su", "sus",
}


def _content_tokens(text):
    return [
        token
        for token in normalize(text).split()
        if token and token not in _TOPIC_STOPWORDS
    ]


def _fact_aliases(fact):
    output = []
    topic = str((fact or {}).get("topic") or "").strip()
    if topic:
        output.append(topic)
    for raw in _plain_list((fact or {}).get("aliases")):
        value = str(raw or "").strip()
        if value:
            output.append(value)
    return output


def fact_topic_match_score(fact, topic):
    """Rank authored topic/aliases by specificity instead of accepting the first one-token overlap."""
    query_norm = normalize(topic)
    query_tokens = set(_content_tokens(topic))
    if not query_norm or not query_tokens:
        return 0

    best = 0
    for alias in _fact_aliases(fact):
        alias_norm = normalize(alias)
        alias_tokens = set(_content_tokens(alias))
        if not alias_norm or not alias_tokens:
            continue

        if query_norm == alias_norm:
            best = max(best, 100000 + len(alias_tokens) * 100)
            continue

        overlap = query_tokens & alias_tokens
        if not overlap:
            continue

        phrase_bonus = 0
        if alias_norm in query_norm or query_norm in alias_norm:
            phrase_bonus = 50000

        overlap_count = len(overlap)
        query_coverage = overlap_count / max(1, len(query_tokens))
        alias_coverage = overlap_count / max(1, len(alias_tokens))
        score = (
            phrase_bonus
            + overlap_count * 1000
            + int(query_coverage * 400)
            + int(alias_coverage * 400)
        )
        best = max(best, score)

    return int(best)


def _fact_response_text(fact):
    response = str((fact or {}).get("response") or "").strip()
    if not response:
        response = str((fact or {}).get("fact") or "").strip()
    if not response:
        response = str((fact or {}).get("text") or "").strip()
    return response


def select_best_known_topic_fact(npc, topic):
    """Return one exact known Fact candidate. Stable source order breaks equal-score ties."""
    if not npc or not str(topic or "").strip():
        return None

    ranked = []
    for index, raw in enumerate(_plain_list(getattr(npc.db, "knowledge_facts", []))):
        fact = _plain_dict(raw)
        if not fact or not str(fact.get("id") or "").strip():
            continue
        if not bool(fact_knowledge_state(npc, fact).get("known")):
            continue
        response = _fact_response_text(fact)
        if not response:
            continue
        score = fact_topic_match_score(fact, topic)
        if score <= 0:
            continue
        ranked.append((int(score), -int(index), fact, response))

    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    score, _neg_index, fact, response = ranked[0]
    return {
        "fact": dict(fact),
        "fact_id": str(fact.get("id") or ""),
        "response_text": response,
        "score": int(score),
        "build": RANKED_FACT_CONVERSATION_BUILD,
    }


def resolve_ranked_talk_with_disclosure_and_acquisition(
    actor,
    raw,
    *,
    expected_target_dbref=None,
):
    """Choose one Fact once, then use that same fact_id for disclosure, memory and authoritative transfer."""
    location = getattr(actor, "location", None) if actor else None
    if not actor or not location:
        return {
            "status": "INTERACTION_REJECTED",
            "executed": False,
            "response_text": "",
            "knowledge_acquisition": {
                "status": "NO_ACTOR_OR_LOCATION",
                "acquired": False,
                "build": RANKED_FACT_CONVERSATION_BUILD,
            },
            "build": RANKED_FACT_CONVERSATION_BUILD,
        }

    npc = (
        _visible_local_npc_by_dbref(actor, expected_target_dbref)
        if expected_target_dbref is not None
        else _find_npc(location, raw)
    )
    if not npc:
        return {
            "status": "INTERACTION_EXECUTED",
            "executed": True,
            "response_text": "No identificas a ningún interlocutor visible para esa acción.",
            "knowledge_acquisition": {
                "status": "NO_SHARED_FACT_IN_NEW_CONVERSATION",
                "acquired": False,
                "build": RANKED_FACT_CONVERSATION_BUILD,
            },
            "build": RANKED_FACT_CONVERSATION_BUILD,
        }

    topic = str(
        extract_player_authored_topic(raw)
        or _extract_topic(raw, npc=npc)
        or ""
    ).strip()
    if not topic:
        greeting = str(npc.db.dialogue_greeting or "").strip() or f"{npc.key} te presta atención."
        before_count = len(_plain_list(getattr(actor.db, "memories", [])))
        _record_conversation(actor, npc, None, outcome="greeting")
        acquisition = acquire_fact_from_new_conversation(
            actor,
            before_count,
            expected_target_dbref=int(npc.id),
        )
        return {
            "status": "INTERACTION_EXECUTED",
            "executed": True,
            "response_text": greeting,
            "knowledge_acquisition": acquisition,
            "selected_fact_id": None,
            "build": RANKED_FACT_CONVERSATION_BUILD,
        }

    selected = select_best_known_topic_fact(npc, topic)
    if not selected:
        text = f"{npc.key} no aporta información concreta sobre {topic}."
        before_count = len(_plain_list(getattr(actor.db, "memories", [])))
        _record_conversation(actor, npc, topic, outcome="no_information")
        acquisition = acquire_fact_from_new_conversation(
            actor,
            before_count,
            expected_target_dbref=int(npc.id),
        )
        return {
            "status": "INTERACTION_EXECUTED",
            "executed": True,
            "response_text": text,
            "knowledge_acquisition": acquisition,
            "selected_fact_id": None,
            "topic": topic,
            "build": RANKED_FACT_CONVERSATION_BUILD,
        }

    fact = dict(selected.get("fact") or {})
    fact_id = str(selected.get("fact_id") or "")
    gate = evaluate_fact_disclosure_v85(npc, actor, fact)
    if not bool(gate.get("allowed", True)):
        return {
            "status": "INTERACTION_EXECUTED",
            "executed": True,
            "response_text": f"{npc.key} evita dar detalles sobre {topic}.",
            "knowledge_acquisition": {
                "status": "DISCLOSURE_BLOCKED",
                "acquired": False,
                "fact_id": fact_id,
                "build": RANKED_FACT_CONVERSATION_BUILD,
            },
            "disclosure": gate,
            "selected_fact_id": fact_id,
            "selection_score": selected.get("score"),
            "topic": topic,
            "build": RANKED_FACT_CONVERSATION_BUILD,
        }

    response_text = str(selected.get("response_text") or "").strip()
    before_count = len(_plain_list(getattr(actor.db, "memories", [])))
    _record_conversation(
        actor,
        npc,
        topic,
        outcome="knowledge_shared",
        fact_id=fact_id,
        fact_text=response_text,
    )
    acquisition = acquire_fact_from_new_conversation(
        actor,
        before_count,
        expected_target_dbref=int(npc.id),
    )
    return {
        "status": "INTERACTION_EXECUTED",
        "executed": True,
        "response_text": response_text,
        "knowledge_acquisition": acquisition,
        "disclosure": gate,
        "selected_fact_id": fact_id,
        "selection_score": selected.get("score"),
        "topic": topic,
        "build": RANKED_FACT_CONVERSATION_BUILD,
    }
