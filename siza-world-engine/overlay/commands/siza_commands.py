import re
import unicodedata

from evennia import Command, search_tag

from services.interaction_engine import parse_interaction_intent, resolve_interaction
from services.npc_simulation import find_npc, npc_state, simstep
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


def _format_npc_state(state):
    if not state:
        return "NPC no encontrado."
    job = state.get("job") or {}
    routine = state.get("routine_entry") or {}
    return "\n".join(
        [
            f"NPC: {state.get('npc')} | npc_id={state.get('npc_id')}",
            f"Location: {state.get('location')} | room_id={state.get('room_id')}",
            f"Job: {job.get('name') or job.get('id') or 'NONE'}",
            f"Activity: {state.get('current_activity') or 'NONE'}",
            f"Destination: {state.get('destination_id') or 'NONE'}",
            f"Routine index: {state.get('routine_index')}",
            f"Routine target: {routine.get('room_key') or 'NONE'}",
            f"Simulation enabled: {state.get('simulation_enabled')}",
        ]
    )


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
        caller.msg("NPC simulation: manual simstep prototype")


class CmdSizaNPCState(Command):
    """Inspect persistent simulation state for one NPC."""

    key = "siza-npcstate"
    aliases = ["npcstate", "estado-npc"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return
        self.caller.msg(_format_npc_state(npc_state(npc)))


class CmdSizaSimStep(Command):
    """Advance one NPC simulation by a single real Room hop."""

    key = "siza-simstep"
    aliases = ["simstep"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza para avanzar.")
            return

        result = simstep(npc)
        status = result.get("status")

        if status in {"MOVED", "ARRIVED"}:
            self.caller.msg(
                f"[SIM] {npc.key}: {result.get('from')} -> {result.get('to')} "
                f"por '{result.get('used_exit')}'."
            )
            self.caller.msg(
                f"[SIM] target={result.get('target')} | activity={result.get('activity')}"
            )
            return

        if status == "NO_PATH":
            self.caller.msg(
                f"[SIM] {npc.key} no tiene ruta abierta desde {result.get('from')} "
                f"hasta {result.get('target')}."
            )
            return

        if status == "BLOCKED":
            self.caller.msg(
                f"[SIM] {npc.key} fue bloqueada al intentar '{result.get('attempted_exit')}'."
            )
            return

        if status == "DISABLED":
            self.caller.msg(f"[SIM] La simulación de {npc.key} está desactivada.")
            return

        self.caller.msg(f"[SIM] Resultado: {status} | {result}")


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
        if mara:
            caller.msg(
                f"Mara sim: enabled={bool(mara.db.simulation_enabled)} | "
                f"activity={mara.db.current_activity or 'NONE'} | "
                f"destination={mara.db.destination_id or 'NONE'} | "
                f"routine_index={mara.db.routine_index if mara.db.routine_index is not None else 'NONE'}"
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
