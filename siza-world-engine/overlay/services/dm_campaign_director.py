from copy import deepcopy
from datetime import datetime, timezone


DM_DIRECTOR_BUILD = "dm-0.1-campaign-director"
CAMPAIGN_STATE_ATTR = "dm_campaign_state"
CARD_TYPES = {"BEAT", "OPPORTUNITY", "PRESSURE", "CONSEQUENCE"}


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate_campaign_definition(definition):
    """Validate campaign structure only. This never reads or mutates world state."""
    data = _plain_dict(definition)
    errors = []
    campaign_id = str(data.get("id") or "").strip()
    if not campaign_id:
        errors.append("MISSING_CAMPAIGN_ID")

    beats = _plain_list(data.get("beats"))
    beat_ids = []
    for beat in beats:
        row = _plain_dict(beat)
        beat_id = str(row.get("id") or "").strip()
        if not beat_id:
            errors.append("BEAT_WITHOUT_ID")
            continue
        if beat_id in beat_ids:
            errors.append(f"DUPLICATE_BEAT:{beat_id}")
        beat_ids.append(beat_id)

    card_ids = []
    for card in _plain_list(data.get("deck")):
        row = _plain_dict(card)
        card_id = str(row.get("id") or "").strip()
        card_type = str(row.get("type") or "").upper().strip()
        if not card_id:
            errors.append("CARD_WITHOUT_ID")
            continue
        if card_id in card_ids:
            errors.append(f"DUPLICATE_CARD:{card_id}")
        card_ids.append(card_id)
        if card_type not in CARD_TYPES:
            errors.append(f"INVALID_CARD_TYPE:{card_id}:{card_type}")
        for required in _plain_list(row.get("requires_beats")):
            if str(required) not in beat_ids:
                errors.append(f"UNKNOWN_REQUIRED_BEAT:{card_id}:{required}")
        for blocked in _plain_list(row.get("blocks_after_beats")):
            if str(blocked) not in beat_ids:
                errors.append(f"UNKNOWN_BLOCK_BEAT:{card_id}:{blocked}")

    return {
        "status": "VALID" if not errors else "INVALID",
        "valid": not errors,
        "campaign_id": campaign_id,
        "beat_ids": beat_ids,
        "card_ids": card_ids,
        "errors": errors,
        "build": DM_DIRECTOR_BUILD,
    }


def _initial_state(definition):
    data = _plain_dict(definition)
    beats = _plain_list(data.get("beats"))
    first_beat = str((_plain_dict(beats[0]).get("id") if beats else "") or "")
    return {
        "campaign_id": str(data.get("id") or ""),
        "status": "ACTIVE",
        "started_at": _now(),
        "active_beat_id": first_beat or None,
        "completed_beats": [],
        "signals": {},
        "card_history": [],
        "director_turn": 0,
    }


def get_campaign_state(actor):
    if not actor:
        return {}
    return _plain_dict(getattr(actor.db, CAMPAIGN_STATE_ATTR, {}))


def start_campaign(actor, definition, force=False):
    """Create player-local campaign bookkeeping. It does not mutate world truth."""
    checked = validate_campaign_definition(definition)
    if not checked.get("valid"):
        return {"status": "INVALID_CAMPAIGN", "started": False, "validation": checked, "build": DM_DIRECTOR_BUILD}
    current = get_campaign_state(actor)
    wanted = str(definition.get("id") or "")
    if current and str(current.get("campaign_id") or "") == wanted and not force:
        return {"status": "ALREADY_ACTIVE", "started": False, "state": current, "build": DM_DIRECTOR_BUILD}
    state = _initial_state(definition)
    actor.db.dm_campaign_state = state
    return {"status": "STARTED", "started": True, "state": deepcopy(state), "build": DM_DIRECTOR_BUILD}


def set_campaign_signal(actor, key, value):
    """Record director bookkeeping supplied by an authoritative system. The DM does not infer truth here."""
    state = get_campaign_state(actor)
    if not state:
        return {"status": "NO_ACTIVE_CAMPAIGN", "updated": False, "build": DM_DIRECTOR_BUILD}
    signal = str(key or "").strip()
    if not signal:
        return {"status": "INVALID_SIGNAL", "updated": False, "build": DM_DIRECTOR_BUILD}
    signals = _plain_dict(state.get("signals"))
    signals[signal] = value
    state["signals"] = signals
    actor.db.dm_campaign_state = state
    return {"status": "UPDATED", "updated": True, "signal": signal, "value": value, "build": DM_DIRECTOR_BUILD}


def _beat_ids(definition):
    return [str(_plain_dict(row).get("id") or "") for row in _plain_list(definition.get("beats")) if str(_plain_dict(row).get("id") or "")]


def complete_active_beat(actor, definition, evidence=None):
    """Advance campaign bookkeeping only after an external authoritative system supplies evidence."""
    state = get_campaign_state(actor)
    if not state:
        return {"status": "NO_ACTIVE_CAMPAIGN", "advanced": False, "build": DM_DIRECTOR_BUILD}
    current = str(state.get("active_beat_id") or "")
    if not current:
        return {"status": "NO_ACTIVE_BEAT", "advanced": False, "build": DM_DIRECTOR_BUILD}
    ids = _beat_ids(definition)
    if current not in ids:
        return {"status": "UNKNOWN_ACTIVE_BEAT", "advanced": False, "active_beat_id": current, "build": DM_DIRECTOR_BUILD}

    completed = [str(value) for value in _plain_list(state.get("completed_beats"))]
    if current not in completed:
        completed.append(current)
    index = ids.index(current)
    next_beat = ids[index + 1] if index + 1 < len(ids) else None
    state["completed_beats"] = completed
    state["active_beat_id"] = next_beat
    state["last_beat_evidence"] = deepcopy(evidence)
    state["last_beat_completed_at"] = _now()
    if next_beat is None:
        state["status"] = "COMPLETED"
        state["completed_at"] = _now()
    actor.db.dm_campaign_state = state
    return {
        "status": "ADVANCED" if next_beat else "CAMPAIGN_COMPLETED",
        "advanced": True,
        "completed_beat_id": current,
        "active_beat_id": next_beat,
        "state": deepcopy(state),
        "build": DM_DIRECTOR_BUILD,
    }


def _read_path(source, path):
    current = source
    for part in str(path or "").split("."):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _compare(actual, op, expected):
    operator = str(op or "eq").lower()
    if operator in {"contains", "in"}:
        try:
            return expected in actual
        except Exception:
            return False
    if operator in {"not_contains", "notin"}:
        try:
            return expected not in actual
        except Exception:
            return True
    try:
        if operator in {"gt", ">"}:
            return actual > expected
        if operator in {"gte", ">="}:
            return actual >= expected
        if operator in {"lt", "<"}:
            return actual < expected
        if operator in {"lte", "<="}:
            return actual <= expected
        if operator in {"ne", "!="}:
            return actual != expected
    except TypeError:
        return False
    return actual == expected


def _condition_matches(condition, state, world_snapshot):
    row = _plain_dict(condition)
    source_name = str(row.get("source") or "CAMPAIGN").upper()
    source = state if source_name == "CAMPAIGN" else _plain_dict(world_snapshot).get(source_name.lower(), {})
    if source_name == "WORLD":
        source = _plain_dict(world_snapshot)
    actual = _read_path(source, row.get("path"))
    return _compare(actual, row.get("op"), row.get("value"))


def card_is_eligible(card, state, world_snapshot=None):
    row = _plain_dict(card)
    if not bool(row.get("enabled", True)):
        return False
    completed = {str(value) for value in _plain_list(state.get("completed_beats"))}
    if any(str(value) not in completed for value in _plain_list(row.get("requires_beats"))):
        return False
    if any(str(value) in completed for value in _plain_list(row.get("blocks_after_beats"))):
        return False
    active_beat = str(state.get("active_beat_id") or "")
    allowed_beats = {str(value) for value in _plain_list(row.get("active_beats"))}
    if allowed_beats and active_beat not in allowed_beats:
        return False
    return all(_condition_matches(condition, state, world_snapshot or {}) for condition in _plain_list(row.get("conditions")))


def _input_relevance(raw, card):
    text = str(raw or "").lower()
    score = 0
    matched = []
    for term in _plain_list(card.get("relevance_terms")):
        value = str(term or "").strip().lower()
        if value and value in text:
            score += 15
            matched.append(value)
    return score, matched


def rank_master_deck(definition, state, raw_player_input="", world_snapshot=None):
    """Rank eligible cards. Ranking is advisory; no event is spawned here."""
    output = []
    for raw_card in _plain_list(definition.get("deck")):
        card = _plain_dict(raw_card)
        if not card_is_eligible(card, state, world_snapshot=world_snapshot):
            continue
        try:
            base = int(card.get("priority", 50) or 50)
        except (TypeError, ValueError):
            base = 50
        relevance, matched_terms = _input_relevance(raw_player_input, card)
        active_bonus = 20 if str(state.get("active_beat_id") or "") in {str(value) for value in _plain_list(card.get("active_beats"))} else 0
        output.append({
            **card,
            "director_score": base + relevance + active_bonus,
            "matched_terms": matched_terms,
        })
    output.sort(key=lambda row: (-int(row.get("director_score", 0)), str(row.get("id") or "")))
    return output


def build_dm_turn_plan(actor, definition, raw_player_input, world_snapshot=None, max_cards=4):
    """Build the DM's read/ordering plan for one player input. This is intentionally non-authoritative."""
    state = get_campaign_state(actor)
    campaign_id = str(definition.get("id") or "")
    if not state or str(state.get("campaign_id") or "") != campaign_id:
        return {"status": "CAMPAIGN_NOT_ACTIVE", "build": DM_DIRECTOR_BUILD}

    snapshot = _plain_dict(world_snapshot)
    ranked = rank_master_deck(definition, state, raw_player_input=raw_player_input, world_snapshot=snapshot)
    selected = ranked[: max(0, int(max_cards or 0))]
    topics = []
    world_queries = []
    for card in selected:
        for topic in _plain_list(card.get("worldbook_topics")):
            value = str(topic or "").strip()
            if value and value not in topics:
                topics.append(value)
        for query in _plain_list(card.get("world_queries")):
            value = str(query or "").strip()
            if value and value not in world_queries:
                world_queries.append(value)

    beat = next((deepcopy(_plain_dict(row)) for row in _plain_list(definition.get("beats")) if str(_plain_dict(row).get("id") or "") == str(state.get("active_beat_id") or "")), None)
    state["director_turn"] = int(state.get("director_turn", 0) or 0) + 1
    state["last_player_input"] = str(raw_player_input or "")
    state["last_director_turn_at"] = _now()
    actor.db.dm_campaign_state = state

    return {
        "status": "PLANNED",
        "campaign_id": campaign_id,
        "objective": deepcopy(definition.get("objective")),
        "active_beat": beat,
        "player_input": str(raw_player_input or ""),
        "location": deepcopy(snapshot.get("location")),
        "selected_cards": selected,
        "retrieval_requests": {
            "world_engine": world_queries,
            "world_book": topics,
        },
        "authority": {
            "dm_may_interpret_input": True,
            "dm_may_rank_cards": True,
            "dm_may_request_context": True,
            "dm_may_mutate_world": False,
            "dm_may_resolve_actions": False,
            "dm_may_invent_facts": False,
            "dm_may_narrate_as_truth": False,
        },
        "state": deepcopy(state),
        "build": DM_DIRECTOR_BUILD,
    }
