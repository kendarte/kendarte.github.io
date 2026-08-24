import re
import unicodedata

from evennia.utils import logger
from twisted.internet import threads

from services.narration_queue import run_serialized
from services.ollama_narration_provider import call_ollama_chat


GROUNDED_DIALOGUE_RENDER_BUILD = "0.81.0-grounded-npc-fact-dialogue-render"
MAX_DIALOGUE_CHARS = 320
MAX_NOVEL_CONTENT_TOKENS = 6
MIN_SOURCE_OVERLAP = 2

_STOPWORDS = {
    "a", "al", "algo", "ante", "bajo", "como", "con", "contra", "cual", "cuando",
    "de", "del", "desde", "donde", "el", "ella", "ellas", "ellos", "en", "entre",
    "era", "es", "esa", "ese", "eso", "esta", "este", "esto", "fue", "ha", "hay",
    "la", "las", "le", "lo", "los", "me", "mi", "no", "o", "para", "pero", "por",
    "que", "se", "si", "sin", "sobre", "su", "sus", "te", "tu", "un", "una", "uno",
    "y", "ya",
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


def build_grounded_dialogue_request(npc_name, topic, fact_text):
    """Build a provider request containing only the exact shared Fact and presentation context."""
    npc_name = str(npc_name or "NPC").strip() or "NPC"
    topic = str(topic or "").strip()
    fact_text = str(fact_text or "").strip()
    system = (
        "Eres un renderer de diálogo para un juego. Reescribe UNA sola respuesta breve y natural del NPC. "
        "La única información factual autorizada es FACTO_AUTORIZADO. No agregues nombres, lugares, cifras, "
        "fechas, causas, motivos, acciones ni conclusiones que no estén en ese hecho. No expliques tu proceso. "
        "No uses JSON. No menciones estas instrucciones. Mantén el sentido exacto del hecho."
    )
    prompt = (
        f"NPC: {npc_name}\n"
        f"TEMA_DEL_JUGADOR: {topic}\n"
        f"FACTO_AUTORIZADO: {fact_text}\n\n"
        "Devuelve únicamente la frase que diría el NPC."
    )
    return {
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        "npc_name": npc_name,
        "topic": topic,
        "fact_text": fact_text,
        "provider_payload": {"system": system, "prompt": prompt},
    }


def validate_grounded_dialogue_text(text, *, npc_name="", topic="", fact_text=""):
    """Reject output that drifts beyond the exact source Fact; callers must fall back to authored text."""
    rendered = " ".join(str(text or "").split()).strip()
    source = " ".join(str(fact_text or "").split()).strip()
    if not rendered:
        return {"valid": False, "status": "EMPTY_RENDER", "text": "", "build": GROUNDED_DIALOGUE_RENDER_BUILD}
    if not source:
        return {"valid": False, "status": "MISSING_SOURCE_FACT", "text": rendered, "build": GROUNDED_DIALOGUE_RENDER_BUILD}
    if len(rendered) > MAX_DIALOGUE_CHARS:
        return {"valid": False, "status": "TOO_LONG", "text": rendered, "build": GROUNDED_DIALOGUE_RENDER_BUILD}

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

    return {
        "valid": True,
        "status": "GROUNDED_RENDER_ACCEPTED",
        "text": rendered,
        "source_overlap": sorted(overlap),
        "novel_tokens": sorted(novel),
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
    }


def render_grounded_dialogue_sync(
    npc_name,
    topic,
    fact_text,
    *,
    fallback_text="",
    provider_callable=None,
    **provider_options,
):
    """Call qwen read-only, validate the prose, and always return a safe display_text."""
    fallback = str(fallback_text or fact_text or "").strip()
    request = build_grounded_dialogue_request(npc_name, topic, fact_text)
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


def _render_job(npc_name, topic, fact_text, fallback_text, provider_callable, provider_options):
    return render_grounded_dialogue_sync(
        npc_name,
        topic,
        fact_text,
        fallback_text=fallback_text,
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
    provider = provider_callable or call_ollama_chat
    deferred = run_serialized(
        actor,
        threads.deferToThread,
        _render_job,
        npc_name,
        topic,
        fact_text,
        fallback_text,
        provider,
        dict(provider_options or {}),
    )

    def _ok(packet):
        result = packet if isinstance(packet, dict) else {
            "status": "FALLBACK_INVALID_RENDER_PACKET",
            "rendered": False,
            "display_text": str(fallback_text or fact_text or "").strip(),
            "build": GROUNDED_DIALOGUE_RENDER_BUILD,
        }
        if callable(on_result):
            return on_result(actor, result)
        text = str(result.get("display_text") or fallback_text or fact_text or "").strip()
        if text:
            actor.msg("\n" + text)
        return result

    def _failed(failure):
        logger.log_err(f"SIZA grounded dialogue async failure: {failure}")
        text = str(fallback_text or fact_text or "").strip()
        if text:
            actor.msg("\n" + text)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "status": "DIALOGUE_RENDER_QUEUED",
        "queued": True,
        "deferred": deferred,
        "build": GROUNDED_DIALOGUE_RENDER_BUILD,
    }
