"""POKEROL free-chat role boundary and scene-intent fast paths.

This layer never answers out-of-world questions. It keeps NPCs and the Director
inside the fiction and only recognizes a few high-confidence scene intents that
must be deterministic (such as the first rival challenge negotiation).
Everything else continues into the existing AI DM pipeline.
"""

import re
import unicodedata


ROLE_INTENT_BUILD = "0.1.0-role-bound-free-chat"


def _norm(value):
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _contains_any(text, phrases):
    return any(phrase in text for phrase in phrases)


# Deliberately narrow. These are clear requests for a general assistant/tool,
# not ordinary in-world vocabulary. Ambiguous text stays IN_WORLD and is sent
# to the DM rather than being rejected by keyword matching.
_OFF_SCENE_PATTERNS = (
    r"\b(?:haz|haga|crea|crear|genera|generar)\b.{0,35}\b(?:hoja de calculo|excel|spreadsheet|powerpoint|presentacion|codigo|programa|script)\b",
    r"\b(?:programa|programame|codifica|escribe codigo|write code|make a spreadsheet|create a spreadsheet)\b",
    r"\b(?:guerra de irak|iraq war|segunda guerra mundial|world war ii)\b",
    r"\b(?:chatgpt|openai|modelo de lenguaje|language model)\b",
)


def classify_role_intent(raw_player_input):
    text = _norm(raw_player_input)
    if not text:
        return {"kind": "IN_WORLD", "confidence": 0.0, "build": ROLE_INTENT_BUILD}
    for pattern in _OFF_SCENE_PATTERNS:
        if re.search(pattern, text, flags=re.I | re.S):
            return {
                "kind": "OFF_SCENE",
                "confidence": 1.0,
                "reason": "GENERAL_ASSISTANT_REQUEST",
                "build": ROLE_INTENT_BUILD,
            }
    return {"kind": "IN_WORLD", "confidence": 0.75, "build": ROLE_INTENT_BUILD}


def diegetic_redirect(actor):
    """Return a short in-fiction redirect without pretending to answer the request."""
    room = getattr(actor, "location", None) if actor else None
    room_name = str(getattr(room, "key", "") or "este lugar").strip()
    # Prefer an actually present speaking NPC, never invent one.
    for obj in list(getattr(room, "contents", []) or []) if room else []:
        if obj is actor or not bool(getattr(getattr(obj, "db", None), "is_npc", False)):
            continue
        name = str(getattr(obj, "key", "") or "").strip()
        if name:
            return {
                "speaker": name,
                "text": "Eso no tiene que ver con lo que está pasando aquí. ¿Qué vas a hacer?",
                "room": room_name,
                "build": ROLE_INTENT_BUILD,
            }
    return {
        "speaker": "NARRADOR",
        "text": "La escena sigue aquí. ¿Qué haces dentro de este momento?",
        "room": room_name,
        "build": ROLE_INTENT_BUILD,
    }


def oak_challenge_free_intent(actor, raw_player_input):
    """Recognize only high-confidence negotiation intents for Oak's rival event."""
    try:
        from services.pokerol_tutorial_engine import LAB_ROOM_ID, tutorial_state
    except Exception:
        return None
    state = tutorial_state(actor)
    if str(state.get("stage") or "").upper() != "RIVAL_CHALLENGE":
        return None
    room = getattr(actor, "location", None)
    room_id = str(getattr(getattr(room, "db", None), "room_id", "") or "").strip()
    # The challenge can remain pending outside after the player asked to relocate.
    if room_id != LAB_ROOM_ID and str(state.get("challenge_status") or "").upper() not in {"RELOCATING", "READY_OUTSIDE"}:
        return None

    text = _norm(raw_player_input)
    if not text:
        return None

    outside = (
        "vamos afuera", "vayamos afuera", "peleemos afuera", "pelear afuera",
        "mejor afuera", "salgamos", "fuera del laboratorio", "outside", "fight outside",
    )
    here = (
        "aqui mismo", "peleemos aqui", "pelear aqui", "te reto aqui", "reto aqui",
        "ahora mismo", "aqui y ahora", "fight here", "right here",
    )
    decline = (
        "no voy a pelear", "no quiero pelear", "no peleare", "rechazo", "me niego",
        "no battle", "i refuse", "i won't fight", "i dont want to fight",
    )
    postpone = (
        "ahora no", "despues", "mas tarde", "luego peleamos", "posponer",
        "not now", "later", "maybe later",
    )

    if _contains_any(text, outside):
        choice = "OUTSIDE"
    elif _contains_any(text, decline):
        choice = "DECLINE"
    elif _contains_any(text, postpone):
        choice = "POSTPONE"
    elif _contains_any(text, here):
        choice = "HERE"
    else:
        return None

    return {
        "kind": "OAK_RIVAL_CHALLENGE",
        "choice": choice,
        "confidence": 1.0,
        "build": ROLE_INTENT_BUILD,
    }
