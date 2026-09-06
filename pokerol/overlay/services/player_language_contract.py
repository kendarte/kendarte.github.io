import re
import unicodedata


PLAYER_LANGUAGE_BUILD = "0.1.2-bilingual-player-turn-language-ui-event"
SUPPORTED_PLAYER_LANGUAGES = ("es", "en")
DEFAULT_PLAYER_LANGUAGE = "es"

_ES_MARKERS = {
    "ahora", "alrededor", "aqui", "abrir", "abro", "ataco", "atacar", "busca", "buscar", "busco",
    "caja", "cajon", "camino", "cerrar", "cierro", "con", "contra", "de", "del", "digo", "donde", "el",
    "ella", "en", "esa", "ese", "esto", "examino", "examinar", "faro", "golpeo", "hacia", "habla", "hablar",
    "hablo", "inspecciono", "inspeccionar", "intento", "la", "las", "le", "leo", "leer", "lo", "los",
    "mira", "mirar", "miro", "muevo", "para", "pateo", "por", "pregunto", "preguntar", "quiero", "robo",
    "salir", "sobre", "tomo", "una", "uno", "uso", "voy", "y",
}
_EN_MARKERS = {
    "about", "around", "ask", "attack", "box", "break", "close", "crate", "door", "drop", "examine",
    "find", "for", "from", "give", "go", "hide", "i", "in", "inside", "inspect", "into", "kick",
    "lighthouse", "look", "move", "now", "open", "read", "say", "search", "see", "steal", "take", "talk",
    "tell", "the", "there", "this", "to", "toward", "towards", "try", "use", "walk", "want", "with",
}
_ES_STRONG = {
    "quiero", "intento", "busco", "miro", "hablo", "pregunto", "pateo", "cierro", "abro", "tomo",
    "examino", "inspecciono", "leo", "digo", "donde", "hacia",
}
_EN_STRONG = {
    "i", "want", "try", "search", "look", "talk", "ask", "kick", "close", "open", "take", "examine",
    "inspect", "read", "tell", "say", "toward", "towards",
}

_MESSAGES = {
    "unsupported": {
        "es": "No entiendo esa acción todavía.",
        "en": "I don't understand that action yet.",
    },
    "narration_unavailable": {
        "es": "No puedo presentar esa información con seguridad ahora mismo.",
        "en": "I can't present that information safely right now.",
    },
    "dialogue_unavailable": {
        "es": "La respuesta no puede presentarse con seguridad ahora mismo.",
        "en": "The reply can't be presented safely right now.",
    },
    "no_new_information": {
        "es": "No obtienes información nueva de esa acción.",
        "en": "You gain no new information from that action.",
    },
    "nothing_stands_out": {
        "es": "Nada más destaca a simple vista.",
        "en": "Nothing else stands out at a glance.",
    },
    "search_nothing_new": {
        "es": "La búsqueda no revela nada nuevo.",
        "en": "The search reveals nothing new.",
    },
}


def _normalize(text):
    value = unicodedata.normalize("NFD", str(text or ""))
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.lower()


def _tokens(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", _normalize(text))


def normalize_player_language(language, default=DEFAULT_PLAYER_LANGUAGE):
    value = str(language or "").strip().lower()
    if value in SUPPORTED_PLAYER_LANGUAGES:
        return value
    fallback = str(default or DEFAULT_PLAYER_LANGUAGE).strip().lower()
    return fallback if fallback in SUPPORTED_PLAYER_LANGUAGES else DEFAULT_PLAYER_LANGUAGE


def detect_player_language(text, previous_language=None):
    """Detect English/Spanish deterministically; ambiguous input inherits the previous turn language."""
    raw = str(text or "")
    tokens = _tokens(raw)
    es_score = 0
    en_score = 0

    if any(ch in raw for ch in "¿¡áéíóúÁÉÍÓÚñÑüÜ"):
        es_score += 4
    lowered = raw.lower()
    if re.search(r"\b(?:i'm|i've|i'll|i'd|you're|we're|they're|don't|can't|won't|isn't|aren't|doesn't|didn't)\b", lowered):
        en_score += 4

    for token in tokens:
        if token in _ES_MARKERS:
            es_score += 1
        if token in _EN_MARKERS:
            en_score += 1
        if token in _ES_STRONG:
            es_score += 2
        if token in _EN_STRONG:
            en_score += 2

    if tokens:
        first = tokens[0]
        if first in {
            "look", "search", "ask", "talk", "take", "drop", "open", "close", "kick", "attack", "use",
            "go", "move", "examine", "inspect", "read", "tell", "say",
        }:
            en_score += 3
        if first in {
            "mira", "mirar", "busca", "buscar", "pregunta", "preguntar", "habla", "hablar", "toma", "tomar",
            "abre", "abrir", "cierra", "cerrar", "patea", "patear", "ataca", "atacar", "usa", "usar", "voy",
            "examina", "examinar", "inspecciona", "inspeccionar", "lee", "leer", "dime", "di",
        }:
            es_score += 3

    previous = normalize_player_language(previous_language) if previous_language else None
    if es_score == en_score:
        language = previous or DEFAULT_PLAYER_LANGUAGE
        source = "previous" if previous else "default"
    elif es_score > en_score:
        language = "es"
        source = "markers"
    else:
        language = "en"
        source = "markers"

    total = es_score + en_score
    confidence = 0.0 if total <= 0 else abs(es_score - en_score) / float(total)
    if source == "previous":
        confidence = 0.5
    elif source == "default":
        confidence = 0.0

    return {
        "language": language,
        "confidence": round(confidence, 3),
        "source": source,
        "scores": {"es": es_score, "en": en_score},
        "build": PLAYER_LANGUAGE_BUILD,
    }


def _read_attr(holder, key):
    if holder is None:
        return None
    try:
        return getattr(holder, key, None)
    except Exception:
        return None


def _write_attr(holder, key, value):
    if holder is None:
        return False
    try:
        setattr(holder, key, value)
        return True
    except Exception:
        return False


def get_actor_turn_language(actor, default=DEFAULT_PLAYER_LANGUAGE):
    if actor is None:
        return normalize_player_language(default)
    current = _read_attr(getattr(actor, "ndb", None), "siza_turn_language")
    if str(current or "").lower() in SUPPORTED_PLAYER_LANGUAGES:
        return normalize_player_language(current)
    previous = _read_attr(getattr(actor, "db", None), "siza_last_player_language")
    return normalize_player_language(previous, default=default)


def set_actor_turn_language(actor, language):
    value = normalize_player_language(language)
    if actor is not None:
        _write_attr(getattr(actor, "ndb", None), "siza_turn_language", value)
        _write_attr(getattr(actor, "db", None), "siza_last_player_language", value)
    return value


def _emit_player_language(actor, detection):
    if actor is None:
        return False
    msg = getattr(actor, "msg", None)
    if not callable(msg):
        return False
    packet = {
        "language": normalize_player_language((detection or {}).get("language")),
        "confidence": (detection or {}).get("confidence"),
        "source": (detection or {}).get("source"),
        "build": PLAYER_LANGUAGE_BUILD,
    }
    try:
        actor.msg(siza_player_language=((packet,), {}))
        return True
    except Exception:
        return False


def resolve_turn_language(actor, raw_player_input):
    previous = get_actor_turn_language(actor)
    detection = detect_player_language(raw_player_input, previous_language=previous)
    set_actor_turn_language(actor, detection.get("language"))
    _emit_player_language(actor, detection)
    return detection


def language_instruction(language):
    value = normalize_player_language(language)
    if value == "en":
        return "Write every player-visible natural-language sentence in English."
    return "Escribe toda frase de lenguaje natural visible para el jugador en español."


def localize(message_key, language, **values):
    value = normalize_player_language(language)
    row = _MESSAGES.get(str(message_key or ""), {})
    template = row.get(value) or row.get(DEFAULT_PLAYER_LANGUAGE) or str(message_key or "")
    try:
        return str(template).format(**values)
    except Exception:
        return str(template)
