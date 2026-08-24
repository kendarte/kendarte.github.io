import json
import re

from evennia.utils import logger
from twisted.internet import threads

from services.grounded_dialogue_renderer import validate_grounded_dialogue_text
from services.narration_queue import run_serialized
from services.ollama_narration_provider import call_ollama_chat


STYLED_GROUNDED_DIALOGUE_BUILD = "0.82.1-enforced-style-aware-grounded-dialogue-render"

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

_SAFE_WARM_OPENERS = ("mira,", "bueno,")
_HEDGE_MARKERS = ("creo que", "quizá", "quizas", "tal vez")


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


def _style_directives(style):
    """Translate only closed style enums into closed presentation instructions."""
    style = sanitize_style_context(style)
    directives = []

    register = style.get("register")
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

    verbosity = style.get("verbosity")
    if verbosity == "TERSE":
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


def build_safe_styled_fallback(fact_text, style_context=None):
    """Deterministic presentation fallback that never changes the authored Fact."""
    fact = str(fact_text or "").strip()
    style = sanitize_style_context(style_context)
    if not fact:
        return ""
    if (
        style.get("register") == "CASUAL"
        and style.get("warmth") == "WARM"
        and style.get("familiarity_band") in {"FAMILIAR", "ESTABLISHED"}
    ):
        return f"Mira, por lo que sé, {_lower_first(fact)}"
    return fact


def validate_style_delivery(text, style_context=None):
    """Require visible realization of high-signal style enums without judging factual content."""
    rendered = " ".join(str(text or "").split()).strip()
    style = sanitize_style_context(style_context)
    lower = rendered.lower()
    words = re.findall(r"\b[\wáéíóúüñÁÉÍÓÚÜÑ'-]+\b", rendered, flags=re.UNICODE)

    if style.get("verbosity") == "TERSE" and len(words) > 14:
        return {"valid": False, "status": "STYLE_TOO_VERBOSE", "word_count": len(words)}
    if style.get("verbosity") == "NORMAL" and len(words) > 28:
        return {"valid": False, "status": "STYLE_TOO_VERBOSE", "word_count": len(words)}

    if style.get("directness") == "DIRECT" and any(marker in lower for marker in _HEDGE_MARKERS):
        return {"valid": False, "status": "STYLE_NOT_DIRECT"}

    needs_warm_opener = (
        style.get("register") == "CASUAL"
        and style.get("warmth") == "WARM"
        and style.get("familiarity_band") in {"FAMILIAR", "ESTABLISHED"}
    )
    if needs_warm_opener and not lower.startswith(_SAFE_WARM_OPENERS):
        return {"valid": False, "status": "STYLE_WARM_OPENER_MISSING"}

    if style.get("register") == "FORMAL" and style.get("warmth") == "RESERVED":
        if lower.startswith(_SAFE_WARM_OPENERS):
            return {"valid": False, "status": "STYLE_TOO_CASUAL"}

    return {
        "valid": True,
        "status": "STYLE_DELIVERY_ACCEPTED",
        "word_count": len(words),
        "warm_opener": lower.startswith(_SAFE_WARM_OPENERS),
    }


def build_styled_grounded_dialogue_request(npc_name, topic, fact_text, style_context=None):
    """Expose only exact Fact text plus closed non-factual style enums/directives."""
    npc_name = str(npc_name or "NPC").strip() or "NPC"
    topic = str(topic or "").strip()
    fact_text = str(fact_text or "").strip()
    style = sanitize_style_context(style_context)
    directives = _style_directives(style)
    system = (
        "Eres un renderer de diálogo para un juego. Reescribe UNA sola respuesta breve y natural del NPC. "
        "La única información factual autorizada es FACTO_AUTORIZADO. ESTILO_AUTORIZADO y REALIZACION_ESTILO "
        "solo controlan forma verbal, tono, registro, ritmo y extensión: jamás son hechos del mundo. "
        "FAMILIARITY_BAND solo describe frecuencia previa de interacción; no implica confianza, afecto, hostilidad, "
        "parentesco ni secretos compartidos. No agregues nombres, lugares, cifras, fechas, causas, acciones o "
        "conclusiones ausentes del hecho autorizado. Cumple las instrucciones de REALIZACION_ESTILO cuando sean "
        "compatibles con el hecho. No expliques tu proceso. No uses JSON. Mantén el sentido exacto."
    )
    prompt = (
        f"NPC: {npc_name}\n"
        f"TEMA_DEL_JUGADOR: {topic}\n"
        f"FACTO_AUTORIZADO: {fact_text}\n"
        f"ESTILO_AUTORIZADO: {json.dumps(style, ensure_ascii=False, separators=(',', ':'))}\n"
        f"REALIZACION_ESTILO: {json.dumps(directives, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "Devuelve únicamente la frase que diría el NPC."
    )
    return {
        "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        "npc_name": npc_name,
        "topic": topic,
        "fact_text": fact_text,
        "safe_style": style,
        "style_directives": directives,
        "provider_payload": {"system": system, "prompt": prompt},
    }


def _validated_fallback(npc_name, topic, fact_text, style_context, fallback_text):
    candidate = build_safe_styled_fallback(fact_text, style_context=style_context)
    validation = validate_grounded_dialogue_text(
        candidate,
        npc_name=npc_name,
        topic=topic,
        fact_text=fact_text,
    )
    if bool(validation.get("valid")):
        return candidate, validation
    plain = str(fallback_text or fact_text or "").strip()
    plain_validation = validate_grounded_dialogue_text(
        plain,
        npc_name=npc_name,
        topic=topic,
        fact_text=fact_text,
    )
    return plain, plain_validation


def render_styled_grounded_dialogue_sync(
    npc_name,
    topic,
    fact_text,
    *,
    style_context=None,
    fallback_text="",
    provider_callable=None,
    **provider_options,
):
    """Render read-only prose, enforcing both factual grounding and visible style delivery."""
    style = sanitize_style_context(style_context)
    fallback, fallback_validation = _validated_fallback(
        npc_name,
        topic,
        fact_text,
        style,
        fallback_text,
    )
    request = build_styled_grounded_dialogue_request(
        npc_name,
        topic,
        fact_text,
        style_context=style,
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


def _render_job(npc_name, topic, fact_text, style_context, fallback_text, provider_callable, provider_options):
    return render_styled_grounded_dialogue_sync(
        npc_name,
        topic,
        fact_text,
        style_context=style_context,
        fallback_text=fallback_text,
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
    """Snapshot style before dispatch; async callback remains presentation-only."""
    safe_style = sanitize_style_context(style_context)
    provider = provider_callable or call_ollama_chat
    deferred = run_serialized(
        actor,
        threads.deferToThread,
        _render_job,
        npc_name,
        topic,
        fact_text,
        safe_style,
        fallback_text,
        provider,
        dict(provider_options or {}),
    )

    def _ok(packet):
        result = packet if isinstance(packet, dict) else {
            "status": "FALLBACK_INVALID_RENDER_PACKET",
            "rendered": False,
            "display_text": build_safe_styled_fallback(fact_text, safe_style),
            "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        }
        if callable(on_result):
            return on_result(actor, result)
        text = str(result.get("display_text") or fallback_text or fact_text or "").strip()
        if text:
            actor.msg("\n" + text)
        return result

    def _failed(failure):
        logger.log_err(f"SIZA styled grounded dialogue async failure: {failure}")
        text = build_safe_styled_fallback(fact_text, safe_style) or str(fallback_text or fact_text or "").strip()
        if text:
            actor.msg("\n" + text)
        return failure

    deferred.addCallbacks(_ok, _failed)
    return {
        "status": "STYLED_DIALOGUE_RENDER_QUEUED",
        "queued": True,
        "safe_style": safe_style,
        "deferred": deferred,
        "build": STYLED_GROUNDED_DIALOGUE_BUILD,
    }
