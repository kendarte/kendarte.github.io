import re
import unicodedata
from uuid import uuid4

from evennia import Command

from services.dm_free_action_pipeline import dispatch_dm_unsupported_action_async
from services.interaction_engine import parse_interaction_intent
from services.npc_simulation import find_npc, npc_state, simstep
from services.ollama_narrator import NARRATOR_BUILD, narrate_perception_async
from services.perception_engine import parse_perception_intent, resolve_perception
from services.pokemon_battle_free_order_engine import submit_battle_free_order
from services.pokemon_battle_runtime import current_battle
from services.pokerol_oak_situation_engine import negotiate_rival_challenge
from services.pokerol_role_intent_router import classify_role_intent, diegetic_redirect, oak_challenge_free_intent
from services.pokerol_tutorial_progress import mark_oak_battle_started
from services.ranked_fact_conversation_engine import resolve_ranked_talk_with_disclosure_and_acquisition
from services.world_combat_handoff_engine import build_world_combat_encounter, emit_world_combat_encounter
from typeclasses.world_tick import DEFAULT_INTERVAL, pause_world_tick, start_world_tick, world_tick_state

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
COMBAT_PATTERNS = (
    re.compile(r"^(?:ataco|ataca|atacar|golpeo|golpea|golpear)(?:\s+(?:a|contra))?\s+(.+?)\s*[.!?]*$", re.I),
    re.compile(r"^(?:i\s+)?(?:attack|hit|fight)(?:\s+against)?\s+(.+?)\s*[.!?]*$", re.I),
)


def normalize(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
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


def looks_like_movement(raw):
    return bool(set(normalize(raw).split()) & MOVEMENT_WORDS)


def combat_target(raw):
    value = str(raw or "").strip()
    for pattern in COMBAT_PATTERNS:
        match = pattern.match(value)
        if match:
            return str(match.group(1) or "").strip(" \t\r\n.!?¿¡")
    return ""


def try_combat(actor, raw):
    name = combat_target(raw)
    if not name:
        return False
    target = actor.search(name, location=actor.location)
    if not target:
        return True
    if target is actor or getattr(target, "destination", None) or not bool(getattr(target.db, "is_npc", False)):
        actor.msg("Ese objetivo no puede iniciar un combate.")
        return True
    packet = build_world_combat_encounter(
        actor,
        target,
        source_action_id=f"POKEROL-COMBAT-{int(actor.id)}-{int(target.id)}-{uuid4().hex[:10].upper()}",
        stakes={"player_intent": str(raw or "").strip(), "input_route": "EXPLICIT_COMBAT"},
    )
    if not packet.get("accepted"):
        actor.msg(f"Combat handoff rechazado: {packet.get('status')}")
        return True
    emitted = emit_world_combat_encounter(actor, packet.get("encounter"))
    if not emitted.get("accepted"):
        actor.msg(f"Combat handoff no emitido: {emitted.get('status')}")
    return True


def format_roll(result):
    roll = (result or {}).get("roll")
    if not roll:
        return None
    return f"[PER TEST] {roll['stat_value']} + d{roll['die_sides']}({roll['die']}) = {roll['total']}"


def _route_role_boundary(caller, raw):
    role = classify_role_intent(raw)
    if str(role.get("kind") or "").upper() != "OFF_SCENE":
        return False
    redirect = diegetic_redirect(caller)
    speaker = str(redirect.get("speaker") or "NARRADOR").strip()
    text = str(redirect.get("text") or "").strip()
    if text:
        caller.msg("\n{}: {}".format(speaker, text) if speaker != "NARRADOR" else "\n" + text)
    return True


def _route_oak_free_challenge(caller, raw):
    intent = oak_challenge_free_intent(caller, raw)
    if not intent:
        return False
    result = negotiate_rival_challenge(caller, intent.get("choice"))
    if result.get("accepted") and str(result.get("status") or "").endswith("STARTED"):
        state = dict(result.get("tutorial_state") or {})
        mark_oak_battle_started(caller, state)
    elif not result.get("accepted"):
        caller.msg("\nEl reto no puede resolverse así ahora: {}.".format(result.get("status")))
    try:
        from commands.pokerol_ui_runtime_commands import emit_room_snapshot
        emit_room_snapshot(caller, visible_text=False)
    except Exception:
        pass
    return True


def _trigger_direct_dialogue_event(caller, location, raw):
    try:
        from services.interaction_engine import _find_npc
        from services.pokerol_event_trigger_bridge import trigger_npc_interaction

        npc = _find_npc(location, raw)
        if npc:
            return trigger_npc_interaction(caller, npc)
    except Exception:
        pass
    return []


class CmdPokerolStatus(Command):
    key = "pokerol-status"
    aliases = ["world-status"]
    locks = "cmd:all()"

    def func(self):
        location = getattr(self.caller, "location", None)
        tick = world_tick_state()
        self.caller.msg(f"POKEROL narrator build: {NARRATOR_BUILD}")
        if location:
            self.caller.msg(f"Room: {location.key} | room_id={getattr(location.db, 'room_id', None)}")
        self.caller.msg("World tick: " + (f"ON cada {tick['interval']}s" if tick.get("enabled") and tick.get("active") else "OFF"))


class CmdPokerolWorldCheck(Command):
    key = "pokerol-worldcheck"
    aliases = ["worldcheck"]
    locks = "cmd:all()"

    def func(self):
        location = getattr(self.caller, "location", None)
        tick = world_tick_state()
        self.caller.msg("=== POKEROL WORLD CHECK ===")
        if location:
            visible = [
                obj.key for obj in list(getattr(location, "contents", []) or [])
                if obj is not self.caller and not getattr(obj, "destination", None) and not bool(getattr(obj.db, "hidden", False))
            ]
            exits = [obj.key for obj in list(getattr(location, "exits", []) or [])]
            self.caller.msg(f"Location: {location.key} | room_id={getattr(location.db, 'room_id', None)}")
            self.caller.msg("Visible: " + (", ".join(visible) if visible else "-"))
            self.caller.msg("Exits: " + (", ".join(exits) if exits else "-"))
        else:
            self.caller.msg("Location: NONE")
        self.caller.msg(f"World tick: exists={tick.get('exists')} | enabled={tick.get('enabled')} | active={tick.get('active')} | count={tick.get('tick_count')}")
        self.caller.msg("===========================")


class CmdPokerolNPCState(Command):
    key = "pokerol-npcstate"
    aliases = ["npcstate", "estado-npc"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("NPC no encontrado.")
            return
        self.caller.msg(str(npc_state(npc)))


class CmdPokerolSimStep(Command):
    key = "pokerol-simstep"
    aliases = ["simstep"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC para avanzar.")
            return
        result = simstep(npc)
        self.caller.msg(f"[SIM] {npc.key}: {result.get('status')} | {result}")


class CmdPokerolSimStart(Command):
    key = "pokerol-sim-start"
    aliases = ["sim-start"]
    locks = "cmd:perm(Admin)"

    def func(self):
        raw = (self.args or "").strip()
        try:
            interval = int(raw) if raw else DEFAULT_INTERVAL
        except ValueError:
            self.caller.msg("Uso: pokerol-sim-start [segundos]")
            return
        _script, created = start_world_tick(interval)
        state = world_tick_state()
        self.caller.msg(f"World Tick {'creado' if created else 'reanudado'}: cada {state['interval']} segundos.")


class CmdPokerolSimStop(Command):
    key = "pokerol-sim-stop"
    aliases = ["sim-stop"]
    locks = "cmd:perm(Admin)"

    def func(self):
        self.caller.msg("World Tick pausado." if pause_world_tick() else "World Tick todavía no existe.")


class CmdPokerolSimStatus(Command):
    key = "pokerol-sim-status"
    aliases = ["sim-status"]
    locks = "cmd:all()"

    def func(self):
        self.caller.msg(f"POKEROL WORLD TICK | {world_tick_state()}")


class CmdPokerolNoMatch(Command):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()
        location = getattr(caller, "location", None)
        if not raw or not location:
            caller.msg("No entiendo esa acción.")
            return

        if _route_role_boundary(caller, raw):
            return

        active_battle = current_battle(caller)
        if str(active_battle.get("status") or "").upper() == "ACTIVE":
            submit_battle_free_order(caller, raw)
            return

        if _route_oak_free_challenge(caller, raw):
            return

        if try_combat(caller, raw):
            return

        if parse_interaction_intent(raw):
            packet = resolve_ranked_talk_with_disclosure_and_acquisition(caller, raw)
            text = str((packet or {}).get("response_text") or "").strip()
            if text:
                caller.msg("\n" + text)
            _trigger_direct_dialogue_event(caller, location, raw)
            return

        perception_intent = parse_perception_intent(raw)
        if perception_intent:
            result = resolve_perception(caller, perception_intent)
            roll_line = format_roll(result)
            if roll_line:
                caller.msg(roll_line)
            narrate_perception_async(caller, result)
            return

        exits = list(getattr(location, "exits", []) or [])
        scored = [(score_exit(raw, exit_obj), exit_obj) for exit_obj in exits]
        scored = [(score, exit_obj) for score, exit_obj in scored if score > 0]
        if scored and looks_like_movement(raw):
            scored.sort(key=lambda row: row[0], reverse=True)
            caller.execute_cmd(scored[0][1].key)
            return

        dispatch_dm_unsupported_action_async(caller, raw)
