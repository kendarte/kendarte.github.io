import json
import re

from evennia.utils import logger
from twisted.internet import threads

from services.grounded_dialogue_renderer import validate_grounded_dialogue_text
from services.narration_queue import run_serialized
from services.ollama_narration_provider import call_ollama_chat
from services.player_language_contract import (
    detect_player_language,
    get_actor_turn_language,
    language_instruction,
    localize,
    normalize_player_language,
)


STYLED_GROUNDED_DIALOGUE_BUILD = "0.82.2-bilingual-style-aware-grounded-dialogue"

_ALLOWED_STYLE = {
    "register": {"FORMAL", "NEUTRAL", "CASUAL"},
    "warmth": {"RESERVED", "NEUTRAL", "WARM"},
    "directness": {"DIRECT", "BALANCED", "EVASIVE"},
    "verbosity": {"TERSE", "NORMAL"},
    "cadence": {"CLIPPED", "PLAIN", "MEASURED"},
    "familiarity_band": {"NONE", "RECENT", "FAMILIAR", "ESTABLISHED"},
}

_DEFAULT_STYLE = {
    "register": "NEUTRAL",
    "warmth": "NEUTRAL",
    "directness": "BALANCED",
    "verbosity": "NORMAL",
    "cadence": "PLAIN",
    "familiarity_band": "NONE",
}


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def sanitize_style_context(style_context):
    raw = _plain_dict(style_context)
    output = dict(_DEFAULT_STYLE)
    for key, allowed in _ALLOWED_STYLE.items():
        candidate = str(raw.get(key) or "").strip().upper()
        if candidate in allowed:
            output[key] = candidate
    return output


def _warm_openers(language):
    return ("look,", "well,") if normalize_player_language(language) == "en" else ("mira,", "bueno,")


def _hedge_markers(language):
    return ("i think", "maybe", "perhaps", "possibly") if normalize_player_language(language) == "en" else (
        "creo que", "quizá", "quizas", "tal vez"
    )


def _style_directives(style, language="es"):
    """Translate only closed style enums into closed presentation instructions."""
    style = sanitize_style_context(style)
    language = normalize_player_language(language)
    directives = []

    register = style.get("register")
    if language == "en":
        if register == "FORMAL":
            directives.append("Use precise formal English; avoid casual filler.")
        elif register == "CASUAL":
            directives.append("Use natural conversational English, not bureaucratic phrasing.")

        warmth = style.get("warmth")
        if warmth == "RESERVED":
            directives.append("Keep verbal distance: add no greeting, comfort, or implied closeness.")
        elif warmth == "WARM":
            directives.append("Use a friendly verbal opening without adding factual information.")

        directness = style.get("directness")
        if directness == "DIRECT":
            directives.append("State the fact immediately; do not hedge or circle around it.")
        elif directness == "EVASIVE":
            directives.append("You may soften the wording, but you must still state the same complete fact.")

        if style.get("verbosity") == "TERSE":
            directives.append("Maximum 14 words and one sentence.")
        else:
            directives.append("One natural sentence; do not exceed 28 words.")

        cadence = style.get("cadence")
        if cadence == "CLIPPED":
            directives.append("Use clipped compact cadence; avoid unnecessary subordinate clauses.")
        elif cadence == "MEASURED":
            directives.append("Use a fluid measured cadence; one brief transition is allowed.")

        if (
            style.get("register") == "CASUAL"
            and style.get("warmth") == "WARM"
            and style.get("familiarity_band") in {"FAMILIAR", "ESTABLISHED"}
        ):
            directives.append("Start exactly with 'Look,'.")
        return directives

    if register == "FORMAL":
        directives.append("Usa español preciso y formal; evita muletillas coloquiales.")
    elif register == "CASUAL":
        directives.append("Usa español conversacional natural, no burocrático.")

    warmth = style.get("warmth")
    if warmth == "RESERVED":
        directives.append("Mantén distancia: no añadas saludo, consuelo ni cercanía verbal.")
    elif warmth == "WARM":
        directives.append("Da una entrada verbal amable sin añadir información factual.")

    directness = style.get("directness")
    if directness == "DIRECT":
        directives.append("Afirma el hecho de inmediato; no uses dudas ni rodeos.")
    elif directness == "EVASIVE":
        directives.append("Puedes suavizar la formulación, pero debes decir completo el mismo hecho.")

    if style.get("verbosity") == "TERSE":
        directives.append("Máximo 14 palabras y una sola oración.")
    else:
        directives.append("Una sola oración natural; no excedas 28 palabras.")

    cadence = style.get("cadence")
    if cadence == "CLIPPED":
        directives.append("Ritmo seco y compacto; evita subordinadas innecesarias.")
    elif cadence == "MEASURED":
        directives.append("Ritmo fluido y medido; una transición breve está permitida.")

    if (
        style.get("register") == "CASUAL"
        and style.get("warmth") == "WARM"
        and style.get("familiarity_band") in {"FAMILIAR", "ESTABLISHED"}
    ):
        directives.append("Empieza exactamente con 'Mira,'.")

    return directives


def _lower_first(text):
    value = str(text or "").strip()
    if not value:
        return value
    return value[:1].lower() + value[1:]


def _fact_matches_language(fact_text, language):
    fact = str(fact_text or "").strip()
    if not fact:
        return False
    detected = detect_player_language(fact, previous_language=language).get("language")
    return detected == normalize_player_language(language)


def build_safe_styled_fallback(fact_text, style_context=None, language="es"):
    """Return a same-language safe fallback; never leak a source-language Fact into the wrong player language."""
    fact = str(fact_text or "").strip()
    style = sanitize_style_context(style_context)
    language = normalize_player_language(language)
    if not fact:
        return ""
    if not _fact_matches_language(fact, language):
        return localize("dialogue_unavailable", language)
    if (
        style.get("register") == "CASUAL"
        and style.get("warmth") == "WARM"
        and style.get("familiarity_band") in {"FAMILIAR", "ESTABLISHED"}
    ):
        if language == "en":
            return f"Look, as far as I know, {_lower_first(fact)}"
        return f"Mira, por lo que sé, {_lower_first(fact)}"
    return fact


def validate_style_delivery(text, style_context=None, language="es"):
    """Require visible realization of high-signal style enums without judging factual content."""
    rendered = " ".join(str(text or "").split()).strip()
    style = sanitize_style_context(style_context)
    language = normalize_player_language(language)
    lower = rendered.lower()
    words = re.findall(r"\b[\wáéíóúüñÁÉÍÓÚÜÑ'-]+\b", rendered, flags=re.UNICODE)
    warm_openers = _warm_openers(language)

    if style.get("verbosity") == "TERSE" and len(words) > 14:
        return {"valid": False, "status": "STYLE_TOO_VERBOSE", "word_count": len(words)}
    if style.get("verbosity") == "NORMAL" and len(words) > 28:
        return {"valid": False, "status": "STYLE_TOO_VERBOSE", "word_count": len(words)}

    if style.get("directness") == "DIRECT" and any(marker in lower for marker in _hedge_markers(language)):
        return {"valid": False, "status": "STYLE_NOT_DIRECT"}

    needs_warm_opener = (
        style.get("register") == "CASUAL"
        and style.get("warmth") == "WARM"
        and style.get("familiarity_band") in {"FAMILIAR", "ESTABLISHED"}
    )
    if needs_warm_opener and not lower.startswith(warm_openers):
        return {"valid": False, "status": "STYLE_WARM_OPENER_MISSING"}

    if style.get("register") == "FORMAL" and style.get("warmth") == "RESERVED":
        if lower.startswith(warm_openers):
            return {"valid": False, "status": "STYLE_TOO_CASUAL"}

    return {
        "valid": True,
        "status": "STYLE_DELIVERY_ACCEPTED",
        "word_count": len(words),
        "warm_opener": lower.startswith(warm_openers),
    }


def build_styled_grounded_dialogue_request(npc_name, topic, fact_text, style_context=None, language="es"):
    """Expose only exact Fact text plus closed non-factual style enums/directives."""
    npc_name = str(npc_name or "NPC").strip() or "NPC"
    topic = str(topic or "").strip()
    fact_text = str(fact_text or "").strip()
    language = normalize_player_language(language)
    style = sanitize_style_context(style_context)
    directives = _style_directives(style, language=language)
    system = (
        "You are a dialogue renderer for a game. Rewrite ONE short natural NPC reply. "
        "The only authorized factual information is AUTHORIZED_FACT. AUTHORIZED_STYLE and STYLE_REALIZATION control only wording, tone, register, cadence, and length; they are never world facts. "
        "FAMILIARITY_BAND describes only prior interaction frequency and does not imply trust, affection, hostility, kinship, or shared secrets. "
        "Do not add names, places, numbers, dates, causes, actions, or conclusions absent from the authorized Fact. "
        "The authorized Fact may be in Spanish or English; translate it only as presentation while preserving its exact meaning. "
        "Follow STYLE_REALIZATION when compatible with the Fact. Do not explain your process and do not use JSON. "
        + language_instruction(language)
    )
    prompt = (
        f"NPC: {npc_name}\n"
        f"PLAYER_TOPIC: {topic}\n"
        f"AUTHORIZED_FACT: {fact_text}\n"
        f"PLAYER_LANGUAGE: {language}\n"
        f"AUTHORIZED_STYLE: {json.dumps(style, ensure_ascii=False, separators=(',', ':'))}\n"
        f"STYLE_REALIZATION: {json.dumps(directives, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "Return only the sentence the NPC would say."
    )
    return {
        "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        "npc_name": npc_name,
        "topic": topic,
        "fact_text": fact_text,
        "player_language": language,
        "safe_style": style,
        "style_directives": directives,
        "provider_payload": {"system": system, "prompt": prompt},
    }


def _validated_fallback(npc_name, topic, fact_text, style_context, fallback_text, language):
    candidate = build_safe_styled_fallback(fact_text, style_context=style_context, language=language)
    validation = validate_grounded_dialogue_text(
        candidate,
        npc_name=npc_name,
        topic=topic,
        fact_text=fact_text,
        language=language,
    )
    if bool(validation.get("valid")):
        return candidate, validation
    plain = str(fallback_text or "").strip()
    if plain and _fact_matches_language(plain, language):
        plain_validation = validate_grounded_dialogue_text(
            plain,
            npc_name=npc_name,
            topic=topic,
            fact_text=fact_text,
            language=language,
        )
        return plain, plain_validation
    return candidate, validation


def render_styled_grounded_dialogue_sync(
    npc_name,
    topic,
    fact_text,
    *,
    style_context=None,
    fallback_text="",
    language="es",
    provider_callable=None,
    **provider_options,
):
    """Render read-only prose, enforcing factual grounding, turn language, and visible style delivery."""
    language = normalize_player_language(language)
    style = sanitize_style_context(style_context)
    fallback, fallback_validation = _validated_fallback(
        npc_name,
        topic,
        fact_text,
        style,
        fallback_text,
        language,
    )
    request = build_styled_grounded_dialogue_request(
        npc_name,
        topic,
        fact_text,
        style_context=style,
        language=language,
    )
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
            "validation": fallback_validation,
            "style_validation": None,
            "build": STYLED_GROUNDED_DIALOGUE_BUILD,
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
            "style_validation": None,
            "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        }

    style_validation = validate_style_delivery(
        validation.get("text"),
        style_context=style,
        language=language,
    )
    if not bool(style_validation.get("valid")):
        return {
            "status": "FALLBACK_STYLE_MISMATCH",
            "rendered": False,
            "display_text": fallback,
            "request": request,
            "provider_result": packet,
            "validation": validation,
            "style_validation": style_validation,
            "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        }

    return {
        "status": "STYLED_GROUNDED_DIALOGUE_RENDERED",
        "rendered": True,
        "display_text": validation.get("text"),
        "request": request,
        "provider_result": packet,
        "validation": validation,
        "style_validation": style_validation,
        "build": STYLED_GROUNDED_DIALOGUE_BUILD,
    }


def _render_job(npc_name, topic, fact_text, style_context, fallback_text, language, provider_callable, provider_options):
    return render_styled_grounded_dialogue_sync(
        npc_name,
        topic,
        fact_text,
        style_context=style_context,
        fallback_text=fallback_text,
        language=language,
        provider_callable=provider_callable,
        **dict(provider_options or {}),
    )


def render_styled_grounded_dialogue_async(
    actor,
    npc_name,
    topic,
    fact_text,
    *,
    style_context=None,
    fallback_text="",
    provider_callable=None,
    on_result=None,
    **provider_options,
):
    """Snapshot style and turn language before dispatch; async callback remains presentation-only."""
    language = get_actor_turn_language(actor)
    safe_style = sanitize_style_context(style_context)
    safe_fallback = build_safe_styled_fallback(fact_text, safe_style, language=language)
    if fallback_text and _fact_matches_language(fallback_text, language):
        safe_fallback = str(fallback_text).strip()
    provider = provider_callable or call_ollama_chat
    deferred = run_serialized(
        actor,
        threads.deferToThread,
        _render_job,
        npc_name,
        topic,
        fact_text,
        safe_style,
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
            "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        }
        if callable(on_result):
            return on_result(actor, result)
        text = str(result.get("display_text") or safe_fallback).strip()
        if text:
            actor.msg("\n" + text)
        return result

    def _failed(failure):
        logger.log_err(f"SIZA styled grounded dialogue async failure: {failure}")
        if safe_fallback:
            actor.msg("\n" + safe_fallback)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "status": "STYLED_DIALOGUE_RENDER_QUEUED",
        "queued": True,
        "player_language": language,
        "safe_style": safe_style,
        "deferred": deferred,
        "build": STYLED_GROUNDED_DIALOGUE_BUILD,
    }
