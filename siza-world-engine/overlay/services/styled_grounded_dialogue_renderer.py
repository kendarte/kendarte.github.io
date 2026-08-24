import json

from evennia.utils import logger
from twisted.internet import threads

from services.grounded_dialogue_renderer import validate_grounded_dialogue_text
from services.narration_queue import run_serialized
from services.ollama_narration_provider import call_ollama_chat


STYLED_GROUNDED_DIALOGUE_BUILD = "0.82.0-style-aware-grounded-dialogue-render"

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


def build_styled_grounded_dialogue_request(npc_name, topic, fact_text, style_context=None):
    """Expose only exact Fact text plus closed non-factual style enums."""
    npc_name = str(npc_name or "NPC").strip() or "NPC"
    topic = str(topic or "").strip()
    fact_text = str(fact_text or "").strip()
    style = sanitize_style_context(style_context)
    system = (
        "Eres un renderer de diálogo para un juego. Reescribe UNA sola respuesta breve y natural del NPC. "
        "La única información factual autorizada es FACTO_AUTORIZADO. ESTILO_AUTORIZADO solo controla tono, "
        "registro, ritmo y extensión: jamás lo trates como información sobre el mundo, historia, motivos o hechos. "
        "FAMILIARITY_BAND solo describe frecuencia previa de interacción; no implica confianza, afecto, hostilidad, "
        "parentesco ni secretos compartidos. No agregues nombres, lugares, cifras, fechas, causas, acciones o "
        "conclusiones ausentes del hecho autorizado. No expliques tu proceso. No uses JSON. Mantén el sentido exacto."
    )
    prompt = (
        f"NPC: {npc_name}\n"
        f"TEMA_DEL_JUGADOR: {topic}\n"
        f"FACTO_AUTORIZADO: {fact_text}\n"
        f"ESTILO_AUTORIZADO: {json.dumps(style, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "Devuelve únicamente la frase que diría el NPC."
    )
    return {
        "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        "npc_name": npc_name,
        "topic": topic,
        "fact_text": fact_text,
        "safe_style": style,
        "provider_payload": {"system": system, "prompt": prompt},
    }


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
    """Render read-only prose with style enums; factual grounding still uses the exact v0.81 guard."""
    fallback = str(fallback_text or fact_text or "").strip()
    request = build_styled_grounded_dialogue_request(
        npc_name,
        topic,
        fact_text,
        style_context=style_context,
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
            "validation": None,
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
            "build": STYLED_GROUNDED_DIALOGUE_BUILD,
        }

    return {
        "status": "STYLED_GROUNDED_DIALOGUE_RENDERED",
        "rendered": True,
        "display_text": validation.get("text"),
        "request": request,
        "provider_result": packet,
        "validation": validation,
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
            "display_text": str(fallback_text or fact_text or "").strip(),
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
        text = str(fallback_text or fact_text or "").strip()
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
