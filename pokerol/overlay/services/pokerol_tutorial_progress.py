"""Authoritative reconciliation for the Oak starter event.

The tutorial UI is not the source of truth.  This module reconstructs progress
from persistent facts (owned starter, flags, battle result and event lifecycle)
and writes missing memories/history exactly once.
"""

from copy import deepcopy

from services.pokerol_event_progress import (
    complete_event,
    event_progress,
    mark_event_active,
    snooze_event,
)
from services.pokerol_player_progress import event_history, memories, record_event, remember
from services.pokemon_party_engine import party_state, set_party_slot_profile
from services.pokerol_event_editor_service import OAK_TUTORIAL_EVENT_ID
from services.pokerol_tutorial_engine import (
    LAB_ROOM_ID,
    RIVAL_PICK,
    SPECIES_NAMES,
    TUTORIAL_BATTLE_SOURCE,
    tutorial_state,
)


OAK_PROGRESS_BUILD = "0.1.0-authoritative-reconcile"
STARTER_IDS = set(RIVAL_PICK.keys())
STARTER_IMAGES = {
    "PKMN-001": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
    "PKMN-004": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png",
    "PKMN-007": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/7.png",
}


def _text(value):
    return str(value or "").strip()


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _flags(actor):
    return _dict(getattr(actor.db, "pokerol_flags", {})) if actor else {}


def _write_flags(actor, **updates):
    if not actor:
        return {}
    flags = _flags(actor)
    flags.update(updates)
    actor.db.pokerol_flags = flags
    return flags


def _markers(actor):
    return _dict(getattr(actor.db, "pokerol_tutorial_progress_markers", {})) if actor else {}


def _set_marker(actor, key, value=True):
    if not actor:
        return
    rows = _markers(actor)
    rows[str(key)] = value
    actor.db.pokerol_tutorial_progress_markers = rows


def _has_event(actor, event_id):
    return any(_text(row.get("event_id")) == event_id for row in event_history(actor))


def _has_memory(actor, event_id):
    return any(_text(row.get("event_id")) == event_id for row in memories(actor))


def _party_rows(actor):
    return list(party_state(actor).get("party") or []) if actor else []


def _storage_rows(actor):
    try:
        return [dict(row or {}) for row in list(getattr(actor.db, "pokerol_pc_storage", []) or []) if isinstance(row, dict)]
    except Exception:
        return []


def _find_starter(actor, state, flags):
    party = _party_rows(actor)
    storage = _storage_rows(actor)
    wanted = _text(state.get("starter_id") or flags.get("starter_id"))
    wanted = wanted if wanted in STARTER_IDS else ""

    slot = state.get("starter_slot")
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        slot = None
    if slot is not None and 0 <= slot < len(party):
        row = party[slot]
        species_id = _text(row.get("species_id"))
        if species_id in STARTER_IDS and (not wanted or species_id == wanted):
            return {"pokemon": row, "slot": slot, "species_id": species_id, "source": "STATE_SLOT"}

    for index, row in enumerate(party):
        if _text(row.get("origin_event_id")) == OAK_TUTORIAL_EVENT_ID:
            species_id = _text(row.get("species_id"))
            if species_id in STARTER_IDS:
                return {"pokemon": row, "slot": index, "species_id": species_id, "source": "ORIGIN_EVENT"}

    if wanted:
        for index, row in enumerate(party):
            if _text(row.get("species_id")) == wanted:
                return {"pokemon": row, "slot": index, "species_id": wanted, "source": "PERSISTED_ID"}
        for row in storage:
            if _text(row.get("species_id")) == wanted:
                return {"pokemon": row, "slot": None, "species_id": wanted, "source": "STORAGE"}

    return None


def _tag_starter(actor, found):
    if not actor or not found or found.get("slot") is None:
        return False
    row = deepcopy(found.get("pokemon") or {})
    changed = False
    tags = {
        "origin_event_id": OAK_TUTORIAL_EVENT_ID,
        "obtained_via": "PROFESSOR_OAK",
        "starter_pokemon": True,
        "obtained_room_id": LAB_ROOM_ID,
    }
    for key, value in tags.items():
        if row.get(key) != value:
            row[key] = value
            changed = True
    if not changed:
        return True
    return bool(set_party_slot_profile(actor, found["slot"], row).get("accepted"))


def _ensure_starter_memory(actor, state):
    starter_id = _text(state.get("starter_id"))
    if starter_id not in STARTER_IDS:
        return
    rival_id = _text(state.get("rival_starter_id")) or RIVAL_PICK.get(starter_id, "")
    event_id = OAK_TUTORIAL_EVENT_ID + ":STARTER"
    starter_name = SPECIES_NAMES.get(starter_id, starter_id)
    rival_name = SPECIES_NAMES.get(rival_id, rival_id or "Pokémon")
    result = "Elegí a {}. El rival eligió a {}.".format(starter_name, rival_name)
    memory_text = "El Profesor Oak me entregó a {} como mi primer compañero. Mi rival eligió a {}.".format(starter_name, rival_name)

    if not _has_event(actor, event_id):
        record_event(
            actor,
            event_id=event_id,
            title="Mi primer Pokémon",
            result=result,
            room_id=LAB_ROOM_ID,
            data={"starter_id": starter_id, "rival_starter_id": rival_id},
            create_memory=False,
        )
    if not _has_memory(actor, event_id):
        remember(
            actor,
            memory_id="MEM-OAK-STARTER",
            title="Mi primer Pokémon",
            text=memory_text,
            category="HITO",
            event_id=event_id,
            room_id=LAB_ROOM_ID,
            image=STARTER_IMAGES.get(starter_id, ""),
            importance=9,
        )
    _set_marker(actor, "starter:" + starter_id)


def _ensure_battle_start_event(actor, state):
    event_id = OAK_TUTORIAL_EVENT_ID + ":RIVAL-CHALLENGE"
    if _has_event(actor, event_id):
        return
    record_event(
        actor,
        event_id=event_id,
        title="Primer reto del rival",
        result="La primera batalla contra el rival comenzó.",
        room_id=LAB_ROOM_ID,
        data={
            "battle_id": state.get("battle_id"),
            "starter_id": state.get("starter_id"),
            "rival_starter_id": state.get("rival_starter_id"),
        },
        create_memory=False,
    )


def _ensure_battle_finish_memory(actor, state):
    outcome = _text(state.get("outcome")).upper() or "COMPLETE"
    event_id = OAK_TUTORIAL_EVENT_ID + ":FIRST-BATTLE"
    label = {
        "PLAYER_WIN": "Gané mi primera batalla contra el rival.",
        "PLAYER_LOSS": "Perdí mi primera batalla contra el rival.",
        "DRAW": "Mi primera batalla contra el rival terminó en empate.",
    }.get(outcome, "Mi primera batalla contra el rival terminó.")
    if not _has_event(actor, event_id):
        record_event(
            actor,
            event_id=event_id,
            title="Mi primera batalla",
            result=outcome,
            room_id=LAB_ROOM_ID,
            data={
                "outcome": outcome,
                "starter_id": state.get("starter_id"),
                "rival_starter_id": state.get("rival_starter_id"),
            },
            create_memory=False,
        )
    if not _has_memory(actor, event_id):
        remember(
            actor,
            memory_id="MEM-OAK-FIRST-BATTLE",
            title="Mi primera batalla",
            text=label,
            category="HITO",
            event_id=event_id,
            room_id=LAB_ROOM_ID,
            importance=8,
        )
    _set_marker(actor, "battle-finish:" + outcome)


def _ensure_completion_memory(actor, state):
    event_id = OAK_TUTORIAL_EVENT_ID + ":COMPLETE"
    starter_id = _text(state.get("starter_id"))
    starter_name = SPECIES_NAMES.get(starter_id, "mi primer Pokémon")
    outcome = _text(state.get("outcome")).upper()
    text = "Después de elegir a {} y enfrentar a mi rival en el laboratorio del Profesor Oak, mi aventura como entrenador comenzó.".format(starter_name)
    if not _has_event(actor, event_id):
        record_event(
            actor,
            event_id=event_id,
            title="El comienzo de mi aventura",
            result="COMPLETED",
            room_id=LAB_ROOM_ID,
            data={"starter_id": starter_id, "outcome": outcome},
            create_memory=False,
        )
    if not _has_memory(actor, event_id):
        remember(
            actor,
            memory_id="MEM-OAK-COMPLETE",
            title="El comienzo de mi aventura",
            text=text,
            category="EVENTO COMPLETADO",
            event_id=event_id,
            room_id=LAB_ROOM_ID,
            image=STARTER_IMAGES.get(starter_id, ""),
            importance=10,
        )


def reconcile_oak_progress(actor, state=None):
    if not actor:
        return {}
    state = dict(state or tutorial_state(actor))
    flags = _flags(actor)
    progress = event_progress(actor, OAK_TUTORIAL_EVENT_ID)
    stage = _text(state.get("stage")).upper() or "MEET_OAK"

    last = _dict(getattr(actor.db, "last_pokemon_battle", {}))
    last_source = _text(last.get("source_event_id"))
    last_outcome = _text(last.get("outcome")).upper()
    completed_by_battle = last_source == TUTORIAL_BATTLE_SOURCE and last_outcome in {"PLAYER_WIN", "PLAYER_LOSS", "DRAW"}
    completed = bool(
        state.get("completed")
        or flags.get("oak_tutorial_complete")
        or progress.get("status") == "COMPLETED"
        or completed_by_battle
    )

    found = _find_starter(actor, state, flags)
    starter_id = _text((found or {}).get("species_id") or state.get("starter_id") or flags.get("starter_id"))
    if starter_id not in STARTER_IDS:
        starter_id = ""
    starter_confirmed = bool(found or flags.get("starter_chosen") or (starter_id and stage in {"RIVAL_CHALLENGE", "BATTLE", "COMPLETE"}))

    if starter_confirmed and starter_id:
        state["starter_id"] = starter_id
        if found and found.get("slot") is not None:
            state["starter_slot"] = int(found["slot"])
            _tag_starter(actor, found)
        state["rival_starter_id"] = _text(state.get("rival_starter_id")) or RIVAL_PICK.get(starter_id, "")
        if not completed and stage in {"MEET_OAK", "CHOOSE_STARTER", ""}:
            stage = "RIVAL_CHALLENGE"
            state["stage"] = stage
        _write_flags(
            actor,
            oak_intro_done=True,
            starter_chosen=True,
            starter_id=starter_id,
            rival_starter_id=state.get("rival_starter_id"),
            rival_starter_taken=True,
        )
        _ensure_starter_memory(actor, state)

    if completed:
        stage = "COMPLETE"
        state["stage"] = "COMPLETE"
        state["completed"] = True
        if completed_by_battle:
            state["outcome"] = last_outcome
        outcome = _text(state.get("outcome")).upper()
        _ensure_battle_finish_memory(actor, state)
        _ensure_completion_memory(actor, state)
        _write_flags(
            actor,
            rival_battle_done=True,
            rival_battle_outcome=outcome,
            oak_tutorial_complete=True,
        )
        complete_event(
            actor,
            OAK_TUTORIAL_EVENT_ID,
            stage="COMPLETE",
            reason="FIRST_RIVAL_BATTLE_FINISHED" if outcome else "PERSISTENT_COMPLETION_FACT",
            facts={
                "starter_id": state.get("starter_id"),
                "rival_starter_id": state.get("rival_starter_id"),
                "outcome": outcome,
            },
        )
    else:
        state["completed"] = False
        progress = event_progress(actor, OAK_TUTORIAL_EVENT_ID)
        if progress.get("status") != "SNOOZED":
            mark_event_active(
                actor,
                OAK_TUTORIAL_EVENT_ID,
                stage=stage,
                facts={
                    "starter_id": state.get("starter_id"),
                    "rival_starter_id": state.get("rival_starter_id"),
                },
            )

    state["build"] = state.get("build") or OAK_PROGRESS_BUILD
    actor.db.pokerol_tutorial = deepcopy(state)
    return state


def snooze_oak_event(actor):
    state = reconcile_oak_progress(actor)
    if state.get("completed"):
        return event_progress(actor, OAK_TUTORIAL_EVENT_ID)
    return snooze_event(
        actor,
        OAK_TUTORIAL_EVENT_ID,
        stage=_text(state.get("stage")) or "RIVAL_CHALLENGE",
        facts={"starter_id": state.get("starter_id"), "rival_starter_id": state.get("rival_starter_id")},
    )


def resume_oak_event(actor):
    state = reconcile_oak_progress(actor)
    if state.get("completed"):
        return event_progress(actor, OAK_TUTORIAL_EVENT_ID)
    return mark_event_active(
        actor,
        OAK_TUTORIAL_EVENT_ID,
        stage=_text(state.get("stage")) or "MEET_OAK",
        facts={"starter_id": state.get("starter_id"), "rival_starter_id": state.get("rival_starter_id")},
    )


def mark_oak_battle_started(actor, state=None):
    state = dict(state or reconcile_oak_progress(actor))
    _ensure_battle_start_event(actor, state)
    _write_flags(actor, rival_challenge_started=True)
    _set_marker(actor, "battle-start:" + (_text(state.get("battle_id")) or "tutorial"))
    return mark_event_active(
        actor,
        OAK_TUTORIAL_EVENT_ID,
        stage="BATTLE",
        facts={
            "battle_id": state.get("battle_id"),
            "starter_id": state.get("starter_id"),
            "rival_starter_id": state.get("rival_starter_id"),
        },
    )
