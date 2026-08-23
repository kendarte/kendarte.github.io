import re
import unicodedata

from evennia import Command, search_tag

from services.interaction_engine import parse_interaction_intent, resolve_interaction
from services.ollama_narrator import NARRATOR_BUILD, narrate_perception_async
from services.perception_engine import parse_perception_intent, resolve_perception


STOPWORDS = {
    "a", "al", "el", "la", "los", "las", "de", "del", "hacia", "para", "por",
    "voy", "ve", "vamos", "quiero", "quisiera", "ir", "irme", "camino", "caminar",
    "moverme", "muevo", "dirigirme", "dirijo", "entrar", "entro", "salir", "salgo",
    "me", "puedo",
}

MOVEMENT_WORDS = {
    "voy", "ve", "vamos", "ir", "irme", "camino", "caminar", "moverme", "muevo",
    "dirigirme", "dirijo", "entrar", "entro", "salir", "salgo", "regreso", "regresar",
    "vuelvo", "volver", "cruzo", "cruzar",
}

ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
DOOR_GROUP = "DOOR-KAL-DAR-TRASTIENDA"
DOOR_CATEGORY = "siza_door"


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


def _looks_like_movement(raw):
    tokens = set(normalize(raw).split())
    return bool(tokens & MOVEMENT_WORDS)


def _format_roll(result):
    roll = result.get("roll")
    if not roll:
        return None
    return (
        f"[PER TEST] {roll['stat_value']} + d{roll['die_sides']}({roll['die']}) "
        f"= {roll['total']}"
    )


def _plain_list(value):
    if not value:
        return []
    try:
        return list(value)
    except Exception:
        return []


def _plain_dict(value):
    if not value:
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


class CmdSizaStatus(Command):
    """Show the Siza runtime build currently loaded by Evennia."""

    key = "siza-status"
    aliases = ["sizastatus"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        location = getattr(caller, "location", None)
        caller.msg(f"SIZA narrator build: {NARRATOR_BUILD}")
        if location:
            caller.msg(f"Room: {location.key} | room_id={location.db.room_id}")
        caller.msg("Intent order: interaction -> perception -> movement")
        caller.msg("Room/perception prose: deterministic | persistent state: Evennia")


class CmdSizaWorldCheck(Command):
    """Inspect the pilot persistent world state after a restart."""

    key = "siza-worldcheck"
    aliases = ["sizaworldcheck", "worldcheck"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        location = getattr(caller, "location", None)
        entities = list(search_tag(ENTITY_TAG, category=ENTITY_CATEGORY))
        mara = next((obj for obj in entities if obj.db.npc_id == "NPC-KAL-DAR-MARA-001"), None)
        board = next((obj for obj in entities if obj.db.object_id == "OBJ-KAL-DAR-CANTINA-001"), None)
        doors = list(search_tag(DOOR_GROUP, category=DOOR_CATEGORY))

        caller.msg("=== SIZA WORLD CHECK ===")
        caller.msg(
            f"Player location: {location.key if location else 'NONE'}"
            + (f" | {location.db.room_id}" if location else "")
        )
        caller.msg(
            f"Mara: {'OK' if mara else 'MISSING'}"
            + (f" | location={mara.location.key if mara.location else 'NONE'} | npc_id={mara.db.npc_id}" if mara else "")
        )
        caller.msg(
            f"Tablilla: {'OK' if board else 'MISSING'}"
            + (f" | location={board.location.key if board.location else 'NONE'} | object_id={board.db.object_id}" if board else "")
        )

        if doors:
            states = [str(exit_obj.db.door_state or "open") for exit_obj in doors]
            unique_states = sorted(set(states))
            sync = "OK" if len(unique_states) == 1 else "MISMATCH"
            caller.msg(
                f"Puerta trastienda: {sync} | sides={len(doors)} | states={','.join(states)}"
            )
        else:
            caller.msg("Puerta trastienda: MISSING")

        memories = _plain_list(caller.db.memories)
        relationships = _plain_dict(caller.db.relationships)
        caller.msg(f"Player memories: {len(memories)}")
        caller.msg(f"Player relationships: {len(relationships)}")
        caller.msg(f"Narrator build: {NARRATOR_BUILD}")
        caller.msg("========================")


class CmdSizaNoMatch(Command):
    """Natural-language fallback for Siza intents not handled by hard commands."""

    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()
        location = getattr(caller, "location", None)

        if not raw or not location:
            caller.msg("No entiendo esa acción.")
            return

        interaction_intent = parse_interaction_intent(raw)
        if interaction_intent:
            text = resolve_interaction(caller, interaction_intent)
            if text:
                caller.msg("\n" + text)
            return

        perception_intent = parse_perception_intent(raw)
        if perception_intent:
            result = resolve_perception(caller, perception_intent)
            roll_line = _format_roll(result)
            if roll_line:
                caller.msg(roll_line)
            narrate_perception_async(caller, result)
            return

        exits = list(getattr(location, "exits", []) or [])
        scored = [(score_exit(raw, exit_obj), exit_obj) for exit_obj in exits]
        scored = [(score, exit_obj) for score, exit_obj in scored if score > 0]

        if not scored or (not _looks_like_movement(raw) and scored[0][0] < 700):
            caller.msg("No entiendo esa acción todavía.")
            return

        scored.sort(key=lambda item: item[0], reverse=True)
        top_score = scored[0][0]
        winners = [exit_obj for score, exit_obj in scored if score == top_score]

        if len(winners) > 1:
            caller.msg("La dirección es ambigua. Opciones: " + ", ".join(exit_obj.key for exit_obj in winners))
            return

        chosen = winners[0]
        caller.execute_cmd(chosen.key)
