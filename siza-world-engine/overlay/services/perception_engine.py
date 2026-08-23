import os
import random
import re
import unicodedata


# Prototype-only die. Kept configurable so this does not freeze Siza's final dice math.
PERCEPTION_DIE_SIDES = int(os.getenv("SIZA_PERCEPTION_DIE_SIDES", "6"))

SENSE_WORDS = {
    "hearing": {"escucho", "escuchar", "oigo", "oir", "oír", "sonido", "ruido"},
    "smell": {"huelo", "oler", "olfateo", "olfatear", "olor"},
    "touch": {"toco", "tocar", "palpo", "palpar", "tacto"},
    "taste": {"pruebo", "probar", "saboreo", "saborear", "sabor"},
}

SEARCH_WORDS = {
    "busco", "buscar", "encuentro", "encontrar", "localizo", "localizar",
    "reviso", "revisar", "examino", "examinar", "inspecciono", "inspeccionar",
    "investigo", "investigar", "miro", "mirar", "observo", "observar",
    "escucho", "escuchar", "oigo", "oir", "huelo", "oler", "olfateo", "olfatear",
    "toco", "tocar", "palpo", "palpar", "pruebo", "probar",
}

BROAD_OBSERVE_PHRASES = {
    "miro alrededor", "mirar alrededor", "observo alrededor", "observar alrededor",
    "observo el lugar", "observar el lugar", "miro el lugar", "mirar el lugar",
    "miro la habitacion", "mirar la habitacion", "observo la habitacion",
}

TARGET_STOPWORDS = {
    "a", "al", "el", "la", "los", "las", "de", "del", "en", "por", "para",
    "un", "una", "unos", "unas", "que", "si", "hay", "donde", "esta", "este",
    "esta", "ese", "esa", "algo", "alguien", "lugar", "habitacion", "alrededor",
    "debajo", "detras", "dentro", "encima", "cerca", "entre", "hacia",
} | SEARCH_WORDS


def normalize(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _tokens(text):
    return [token for token in normalize(text).split() if token]


def _sense_from_tokens(tokens):
    token_set = set(tokens)
    for sense, words in SENSE_WORDS.items():
        if token_set & {normalize(word) for word in words}:
            return sense
    return "sight"


def parse_perception_intent(raw):
    normalized = normalize(raw)
    tokens = _tokens(raw)
    token_set = set(tokens)
    normalized_search_words = {normalize(word) for word in SEARCH_WORDS}

    if not (token_set & normalized_search_words):
        return None

    broad_observe = normalized in {normalize(item) for item in BROAD_OBSERVE_PHRASES}
    sense = _sense_from_tokens(tokens)
    target_tokens = [token for token in tokens if token not in {normalize(w) for w in TARGET_STOPWORDS}]
    target = " ".join(target_tokens).strip()

    return {
        "intent": "PERCEIVE",
        "sense": sense,
        "active_search": not broad_observe,
        "target": target,
        "raw": raw,
    }


def _plain_dict(value):
    if not value:
        return {}
    try:
        return {str(k): v for k, v in value.items()}
    except Exception:
        return {}


def _plain_list(value):
    if not value:
        return []
    try:
        return list(value)
    except Exception:
        return []


def _fact_matches_target(fact, target):
    if not target:
        return True
    target_tokens = set(_tokens(target))
    if not target_tokens:
        return True
    haystack = " ".join(
        [
            str(fact.get("fact", "")),
            str(fact.get("target", "")),
            " ".join(str(item) for item in fact.get("keywords", []) or []),
        ]
    )
    return bool(target_tokens & set(_tokens(haystack)))


def _visible_matching_objects(location, target):
    if not location or not target:
        return [], []

    target_tokens = set(_tokens(target))
    names = []
    details = []

    for obj in location.contents:
        if getattr(obj, "destination", None):
            continue
        if getattr(obj.db, "hidden", False):
            continue

        object_names = [obj.key]
        try:
            object_names.extend(obj.aliases.all())
        except Exception:
            pass
        object_tokens = set(_tokens(" ".join(str(name) for name in object_names if name)))
        if not (target_tokens and target_tokens & object_tokens):
            continue

        names.append(obj.key)
        details.append(
            {
                "name": obj.key,
                "desc": str(obj.db.desc or "").strip(),
                "object_id": obj.db.object_id,
                "npc_id": obj.db.npc_id,
                "is_npc": bool(obj.db.is_npc),
                "state": _plain_dict(obj.db.state),
            }
        )

    return names, details


def _get_per_value(character):
    stats = _plain_dict(character.db.adventure_stats)
    try:
        return int(stats.get("PER", 0))
    except (TypeError, ValueError):
        return 0


def _known_fact_ids(character):
    return set(str(item) for item in _plain_list(character.db.discovered_facts))


def _remember_fact_ids(character, fact_ids):
    known = _known_fact_ids(character)
    known.update(str(item) for item in fact_ids if item)
    character.db.discovered_facts = sorted(known)


def resolve_perception(character, intent):
    location = getattr(character, "location", None)
    if not location:
        return {"status": "NO_LOCATION", "intent": intent}

    sense = intent.get("sense", "sight")
    active_search = bool(intent.get("active_search"))
    target = intent.get("target", "")

    sensory = _plain_dict(location.db.sensory_facts)
    obvious = _plain_list(sensory.get(sense, []))
    visible_targets, visible_target_details = _visible_matching_objects(location, target)

    facts = []
    for raw_fact in _plain_list(location.db.perception_facts):
        try:
            fact = {str(k): v for k, v in raw_fact.items()}
        except Exception:
            continue
        if str(fact.get("sense", "sight")) != sense:
            continue
        if not _fact_matches_target(fact, target):
            continue
        facts.append(fact)

    known_ids = _known_fact_ids(character)
    already_known = [
        fact for fact in facts if str(fact.get("id", "")) in known_ids
    ]

    result = {
        "status": "OBSERVED" if not active_search else "SEARCHED",
        "intent": intent,
        "room_id": location.db.room_id,
        "room_name": location.key,
        "sense": sense,
        "target": target,
        "obvious_facts": obvious,
        "visible_targets": visible_targets,
        "visible_target_details": visible_target_details,
        "already_known": [fact.get("fact") for fact in already_known if fact.get("fact")],
        "discovered": [],
        "roll": None,
    }

    if not active_search:
        return result

    if visible_targets:
        result["status"] = "AUTO_SUCCESS"
        return result

    undiscovered = [
        fact for fact in facts if str(fact.get("id", "")) not in known_ids
    ]

    if not undiscovered:
        result["status"] = "NO_AUTHORIZED_DISCOVERY"
        return result

    per_value = _get_per_value(character)
    die = random.randint(1, max(1, PERCEPTION_DIE_SIDES))
    total = per_value + die

    discovered = []
    discovered_ids = []
    for fact in undiscovered:
        try:
            difficulty = int(fact.get("difficulty", 0))
        except (TypeError, ValueError):
            difficulty = 0
        if total >= difficulty:
            text = fact.get("fact")
            if text:
                discovered.append(text)
            fact_id = fact.get("id")
            if fact_id:
                discovered_ids.append(str(fact_id))

    if discovered_ids:
        _remember_fact_ids(character, discovered_ids)

    result["roll"] = {
        "stat": "PER",
        "stat_value": per_value,
        "die_sides": PERCEPTION_DIE_SIDES,
        "die": die,
        "total": total,
    }
    result["discovered"] = discovered
    result["status"] = "DISCOVERY" if discovered else "NO_DISCOVERY"
    return result
