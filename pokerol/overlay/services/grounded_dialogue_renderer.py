import re
import unicodedata

from evennia.utils import logger
from twisted.internet import threads

from services.narration_queue import run_serialized
from services.ollama_narration_provider import call_ollama_chat
from services.player_language_contract import (
    detect_player_language,
    get_actor_turn_language,
    language_instruction,
    localize,
    normalize_player_language,
)


GROUNDED_DIALOGUE_RENDER_BUILD = "0.81.1-bilingual-grounded-npc-fact-dialogue"
MAX_DIALOGUE_CHARS = 320
MAX_NOVEL_CONTENT_TOKENS = 6
MAX_TRANSLATION_TOKEN_GROWTH = 8
MIN_SOURCE_OVERLAP = 2

_STOPWORDS = {
    "a", "al", "algo", "an", "and", "ante", "are", "as", "at", "bajo", "be", "but", "by",
    "como", "con", "contra", "cual", "cuando", "de", "del", "desde", "did", "do", "does", "donde",
    "el", "ella", "ellas", "ellos", "en", "entre", "era", "es", "esa", "ese", "eso", "esta", "este",
    "esto", "for", "from", "fue", "ha", "has", "have", "hay", "he", "her", "his", "i", "in", "is",
    "it", "la", "las", "le", "lo", "los", "me", "mi", "no", "not", "o", "of", "on", "or", "para",
    "pero", "por", "que", "se", "she", "si", "sin", "so", "sobre", "su", "sus", "te", "that", "the",
    "their", "them", "they", "this", "to", "tu", "un", "una", "uno", "was", "we", "were", "with", "you",
    "your", "y", "ya",
}


def _normalize(text):
    value = unicodedata.normalize("NFD", str(text or ""))
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return " ".join(value.split())


def _tokens(text):
    return [token for token in _normalize(text).split() if token]


def _content_tokens(text):
    return {token for token in _tokens(text) if token not in _STOPWORDS and len(token) > 2}


def _numbers(text):
    return set(re.findall(r"\b\d+(?:[.,]\d+)?\b", str(text or "")))


def _capitalized_noninitial_words(text):
    words = re.findall(r"\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]*\b", str(text or ""))
    sentences = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    sentence_first = set()
    for sentence in sentences:
        match = re.search(r"\b([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]*)\b", sentence)
        if match:
            sentence_first.add(_normalize(match.group(1)))
    return {_normalize(word) for word in words if _normalize(word) not in sentence_first}


def _source_language(text, fallback="es"):
    detection = detect_player_language(text, previous_language=fallback)
    return normalize_player_language(detection.get("language"), default=fallback)


def _safe_fallback(fact_text, language):
    language = normalize_player_language(language)
    source = str(fact_text or "").strip()
    if source and _source_language(source, fallback=language) == language:
        return source
    return localize("dialogue_unavailable", language)


def build_grounded_dialogue_request(npc_name, topic, fact_text, language="es"):
    """Build a provider request containing only the exact shared Fact and presentation context."""
    npc_name = str(npc_name or "NPC").strip() or "NPC"
    topic = str(topic or "").strip()
    fact_text = str(fact_text or "").strip()
    language = normalize_player_language(language)
    system = (
        "You are a dialogue renderer for a game. Rewrite ONE short natural NPC reply. "
        "The only authorized factual information is AUTHORIZED_FACT. Do not add names, places, numbers, dates, causes, motives, actions, or conclusions absent from that fact. "
        "The authorized Fact may be written in Spanish or English. You may translate it only as presentation while preserving the exact meaning. "
        "Do not explain your process, do not use JSON, and do not mention these instructions. "
        + language_instruction(language)
    )
    prompt = (
        f"NPC: {npc_name}\n"
        f"PLAYER_TOPIC: {topic}\n"
        f"AUTHORIZED_FACT: {fact_text}\n"
        f"PLAYER_LANGUAGE: {language}\n\n"
        "Return only the sentence the NPC would say."
    )
    return {
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        "npc_name": npc_name,
        "topic": topic,
        "fact_text": fact_text,
        "player_language": language,
        "provider_payload": {"system": system, "prompt": prompt},
    }


def validate_grounded_dialogue_text(text, *, npc_name="", topic="", fact_text="", language=None):
    """Reject factual drift. Cross-language presentation uses stricter shape/name/number limits instead of lexical overlap."""
    rendered = " ".join(str(text or "").split()).strip()
    source = " ".join(str(fact_text or "").split()).strip()
    if not rendered:
        return {"valid": False, "status": "EMPTY_RENDER", "text": "", "build": GROUNDED_DIALOGUE_RENDER_BUILD}
    if not source:
        return {"valid": False, "status": "MISSING_SOURCE_FACT", "text": rendered, "build": GROUNDED_DIALOGUE_RENDER_BUILD}
    if len(rendered) > MAX_DIALOGUE_CHARS:
        return {"valid": False, "status": "TOO_LONG", "text": rendered, "build": GROUNDED_DIALOGUE_RENDER_BUILD}

    target_language = normalize_player_language(language) if language else None
    source_language = _source_language(source, fallback=target_language or "es")
    cross_language = bool(target_language and target_language != source_language)

    source_numbers = _numbers(source)
    rendered_numbers = _numbers(rendered)
    if not rendered_numbers.issubset(source_numbers):
        return {
            "valid": False,
            "status": "NEW_NUMBER",
            "text": rendered,
            "new_numbers": sorted(rendered_numbers - source_numbers),
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    allowed_names = _content_tokens(" ".join([source, npc_name, topic]))
    new_capitals = {
        token for token in _capitalized_noninitial_words(rendered)
        if token and token not in allowed_names
    }
    if new_capitals:
        return {
            "valid": False,
            "status": "NEW_PROPER_NAME",
            "text": rendered,
            "new_names": sorted(new_capitals),
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    source_content = _content_tokens(" ".join([source, topic, npc_name]))
    rendered_content = _content_tokens(rendered)
    overlap = rendered_content & source_content

    if cross_language:
        if len(rendered_content) > len(source_content) + MAX_TRANSLATION_TOKEN_GROWTH:
            return {
                "valid": False,
                "status": "TRANSLATION_TOO_EXPANSIVE",
                "text": rendered,
                "source_content_count": len(source_content),
                "rendered_content_count": len(rendered_content),
                "build": GROUNDED_DIALOGUE_RENDER_BUILD,
            }
        rendered_language = detect_player_language(rendered, previous_language=target_language).get("language")
        if rendered_language != target_language:
            return {
                "valid": False,
                "status": "WRONG_PLAYER_LANGUAGE",
                "text": rendered,
                "expected_language": target_language,
                "detected_language": rendered_language,
                "build": GROUNDED_DIALOGUE_RENDER_BUILD,
            }
        return {
            "valid": True,
            "status": "GROUNDED_TRANSLATION_ACCEPTED",
            "text": rendered,
            "source_language": source_language,
            "player_language": target_language,
            "cross_language": True,
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    required_overlap = min(MIN_SOURCE_OVERLAP, len(source_content)) if source_content else 0
    if len(overlap) < required_overlap:
        return {
            "valid": False,
            "status": "INSUFFICIENT_SOURCE_OVERLAP",
            "text": rendered,
            "overlap": sorted(overlap),
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    novel = rendered_content - source_content
    if len(novel) > MAX_NOVEL_CONTENT_TOKENS:
        return {
            "valid": False,
            "status": "TOO_MUCH_NOVEL_CONTENT",
            "text": rendered,
            "novel_tokens": sorted(novel),
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    if target_language:
        rendered_language = detect_player_language(rendered, previous_language=target_language).get("language")
        if rendered_language != target_language:
            return {
                "valid": False,
                "status": "WRONG_PLAYER_LANGUAGE",
                "text": rendered,
                "expected_language": target_language,
                "detected_language": rendered_language,
                "build": GROUNDED_DIALOGUE_RENDER_BUILD,
            }

    return {
        "valid": True,
        "status": "GROUNDED_RENDER_ACCEPTED",
        "text": rendered,
        "source_overlap": sorted(overlap),
        "novel_tokens": sorted(novel),
        "player_language": target_language,
        "cross_language": False,
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
    }


def render_grounded_dialogue_sync(
    npc_name,
    topic,
    fact_text,
    *,
    fallback_text="",
    language="es",
    provider_callable=None,
    **provider_options,
):
    """Call qwen read-only, validate the prose, and always return a safe display_text."""
    language = normalize_player_language(language)
    fallback = _safe_fallback(fact_text, language)
    if fallback_text and _source_language(fallback_text, fallback=language) == language:
        fallback = str(fallback_text).strip()
    request = build_grounded_dialogue_request(npc_name, topic, fact_text, language=language)
    provider = provider_callable or call_ollama_chat
    result = provider(request.get("provider_payload") or {}, **dict(provider_options or {}))
    packet = result if isinstance(result, dict) else {}
    if packet.get("status") != "OK":
        return {
            "status": "FALLBACK_PROVIDER_FAILURE",
            "rendered": False,
            "display_text": fallback,
            "request": request,
            "provider_result": packet,
            "validation": None,
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    validation = validate_grounded_dialogue_text(
        packet.get("text"),
        npc_name=npc_name,
        topic=topic,
        fact_text=fact_text,
        language=language,
    )
    if not bool(validation.get("valid")):
        return {
            "status": "FALLBACK_UNGROUNDED_RENDER",
            "rendered": False,
            "display_text": fallback,
            "request": request,
            "provider_result": packet,
            "validation": validation,
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }

    return {
        "status": "GROUNDED_DIALOGUE_RENDERED",
        "rendered": True,
        "display_text": validation.get("text"),
        "request": request,
        "provider_result": packet,
        "validation": validation,
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
    }


def _render_job(npc_name, topic, fact_text, fallback_text, language, provider_callable, provider_options):
    return render_grounded_dialogue_sync(
        npc_name,
        topic,
        fact_text,
        fallback_text=fallback_text,
        language=language,
        provider_callable=provider_callable,
        **dict(provider_options or {}),
    )


def render_grounded_dialogue_async(
    actor,
    npc_name,
    topic,
    fact_text,
    *,
    fallback_text="",
    provider_callable=None,
    on_result=None,
    **provider_options,
):
    """Render dialogue off the reactor. The callback is presentation-only and never mutates world state here."""
    language = get_actor_turn_language(actor)
    provider = provider_callable or call_ollama_chat
    safe_fallback = _safe_fallback(fact_text, language)
    if fallback_text and _source_language(fallback_text, fallback=language) == language:
        safe_fallback = str(fallback_text).strip()
    deferred = run_serialized(
        actor,
        threads.deferToThread,
        _render_job,
        npc_name,
        topic,
        fact_text,
        safe_fallback,
        language,
        provider,
        dict(provider_options or {}),
    )

    def _ok(packet):
        result = packet if isinstance(packet, dict) else {
            "status": "FALLBACK_INVALID_RENDER_PACKET",
            "rendered": False,
            "display_text": safe_fallback,
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }
        if callable(on_result):
            return on_result(actor, result)
        text = str(result.get("display_text") or safe_fallback).strip()
        if text:
            actor.msg("\n" + text)
        return result

    def _failed(failure):
        logger.log_err(f"SIZA grounded dialogue async failure: {failure}")
        if safe_fallback:
            actor.msg("\n" + safe_fallback)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "status": "DIALOGUE_RENDER_QUEUED",
        "queued": True,
        "player_language": language,
        "deferred": deferred,
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
    }
