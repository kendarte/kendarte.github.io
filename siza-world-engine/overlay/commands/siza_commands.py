import re
import unicodedata

from evennia import Command


STOPWORDS = {
    "a", "al", "el", "la", "los", "las", "de", "del", "hacia", "para", "por",
    "voy", "ve", "vamos", "quiero", "quisiera", "ir", "irme", "camino", "caminar",
    "moverme", "muevo", "dirigirme", "dirijo", "entrar", "entro", "salir", "salgo",
}


def normalize(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def content_tokens(text):
    return {token for token in normalize(text).split() if token not in STOPWORDS and len(token) > 2}


def exit_phrases(exit_obj):
    phrases = [exit_obj.key]
    try:
        phrases.extend(exit_obj.aliases.all())
    except Exception:
        pass
    if exit_obj.destination:
        phrases.append(exit_obj.destination.key)
    return [phrase for phrase in phrases if phrase]


def score_exit(raw, exit_obj):
    raw_n = normalize(raw)
    raw_tokens = content_tokens(raw)
    best = 0

    for phrase in exit_phrases(exit_obj):
        phrase_n = normalize(phrase)
        if not phrase_n:
            continue
        if raw_n == phrase_n:
            best = max(best, 1000 + len(phrase_n))
        elif phrase_n in raw_n:
            best = max(best, 700 + len(phrase_n))

        phrase_tokens = content_tokens(phrase)
        overlap = raw_tokens & phrase_tokens
        if overlap:
            coverage = len(overlap) / max(1, len(phrase_tokens))
            best = max(best, int(100 * coverage) + len(overlap) * 10)

    return best


class CmdSizaNoMatch(Command):
    """Prototype natural-language fallback for movement intents."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()
        location = getattr(caller, "location", None)

        if not raw or not location:
            caller.msg("No entiendo esa accion.")
            return

        exits = list(getattr(location, "exits", []) or [])
        scored = [(score_exit(raw, exit_obj), exit_obj) for exit_obj in exits]
        scored = [(score, exit_obj) for score, exit_obj in scored if score > 0]

        if not scored:
            caller.msg("No encuentro una salida valida para esa accion. Usa 'look' para ver las salidas fisicas disponibles.")
            return

        scored.sort(key=lambda item: item[0], reverse=True)
        top_score = scored[0][0]
        winners = [exit_obj for score, exit_obj in scored if score == top_score]

        if len(winners) > 1:
            caller.msg("La direccion es ambigua. Opciones: " + ", ".join(exit_obj.key for exit_obj in winners))
            return

        chosen = winners[0]
        caller.execute_cmd(chosen.key)
