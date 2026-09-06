import json

from services.action_resolution_engine import ADVENTURE_STATS, CHECK_MODES
from services.player_language_contract import detect_player_language, language_instruction


DM_FREE_ACTION_BUILD = "dm-0.1-structured-free-action-intent-bilingual"
DM_ACTION_TYPES = (
    "OBSERVE",
    "SEARCH",
    "MOVE",
    "TALK",
    "PERSUADE",
    "DECEIVE",
    "THREATEN",
    "TAKE",
    "DROP",
    "GIVE",
    "USE",
    "MOVE_OBJECT",
    "OPEN",
    "CLOSE",
    "BREAK",
    "ATTACK",
    "DEFEND",
    "STEAL",
    "HIDE",
    "CREATE",
    "COMBINE",
    "WAIT",
    "OTHER",
)
RESOLUTION_HINTS = tuple(CHECK_MODES) + ("COMBAT", "NONE", "UNKNOWN")
CONTEXT_NEEDS = (
    "WORLD_OBJECT_STATE",
    "TARGET_STATE",
    "WORLD_BOOK_CANON",
    "KNOWLEDGE",
    "RELATIONSHIP",
    "FACTION_AUTHORITY",
    "LOCATION_TOPOLOGY",
    "EVENT_STATE",
    "INVENTORY",
    "OTHER",
)
MAX_STEPS = 3


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


def _append_entity_refs(rows, seen, entities, scope):
    for entity in _plain_list(entities):
        row = _plain_dict(entity)
        dbref = row.get("dbref")
        if dbref is None:
            continue
        ref = f"DBREF:{int(dbref)}"
        if ref in seen:
            continue
        seen.add(ref)
        rows.append({
            "ref": ref,
            "kind": "NPC" if bool(row.get("is_npc")) else "OBJECT",
            "scope": str(scope or ""),
            "name": str(row.get("name") or ref),
            "npc_id": row.get("npc_id"),
            "object_id": row.get("object_id"),
            "portable": bool(row.get("portable", False)),
        })


def build_reference_catalog(world_snapshot):
    """Return the only authoritative references Qwen may bind directly."""
    snapshot = _plain_dict(world_snapshot)
    rows = [
        {"ref": "SELF", "kind": "SELF", "scope": "SELF", "name": "player"},
        {
            "ref": "ROOM",
            "kind": "ROOM",
            "scope": "LOCAL",
            "name": str((_plain_dict(snapshot.get("location"))).get("name") or "current location"),
        },
    ]
    seen = {"SELF", "ROOM"}

    _append_entity_refs(rows, seen, snapshot.get("local_entities"), "LOCAL")
    _append_entity_refs(rows, seen, snapshot.get("inventory"), "INVENTORY")

    for exit_row in _plain_list(snapshot.get("local_exits")):
        row = _plain_dict(exit_row)
        exit_dbref = row.get("exit_dbref")
        exit_id = str(row.get("exit_id") or "").strip()
        if exit_dbref is not None:
            ref = f"EXIT_DBREF:{int(exit_dbref)}"
        elif exit_id:
            ref = f"EXIT_ID:{exit_id}"
        else:
            continue
        if ref in seen:
            continue
        seen.add(ref)
        rows.append({
            "ref": ref,
            "kind": "EXIT",
            "scope": "LOCAL",
            "name": str(row.get("name") or ref),
            "exit_id": exit_id or None,
            "destination_name": row.get("destination_name"),
            "destination_room_id": row.get("destination_room_id"),
        })

    return rows


def _safe_known_facts(world_snapshot):
    player = _plain_dict((_plain_dict(world_snapshot)).get("player"))
    output = []
    for raw in _plain_list(player.get("known_facts")):
        fact = _plain_dict(raw)
        output.append({
            "id": str(fact.get("id") or ""),
            "topic": str(fact.get("topic") or ""),
            "text": str(fact.get("text") or ""),
            "knowledge_level": fact.get("knowledge_level"),
        })
    return output


def build_dm_free_action_request(raw_player_input, dm_plan, world_snapshot, player_language=None):
    """Build a bounded interpretation request. The request contains no mutation API."""
    language = str(player_language or "").strip().lower()
    if language not in {"es", "en"}:
        language = detect_player_language(raw_player_input).get("language") or "es"

    refs = build_reference_catalog(world_snapshot)
    allowed_refs = [row.get("ref") for row in refs]
    plan = _plain_dict(dm_plan)
    snapshot = _plain_dict(world_snapshot)
    active_beat = _plain_dict(plan.get("active_beat"))
    selected_cards = []
    for raw in _plain_list(plan.get("selected_cards")):
        card = _plain_dict(raw)
        selected_cards.append({
            "id": str(card.get("id") or ""),
            "type": str(card.get("type") or ""),
            "name": str(card.get("name") or ""),
            "director_intent": str(card.get("director_intent") or ""),
        })

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["intent", "goal", "steps", "context_needs", "confidence"],
        "properties": {
            "intent": {"type": "string", "enum": list(DM_ACTION_TYPES)},
            "goal": {"type": "string", "maxLength": 240},
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_STEPS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "action_type",
                        "verb",
                        "primary_ref",
                        "secondary_ref",
                        "unresolved_target",
                        "desired_effect",
                        "resolution_hint",
                        "stat_hint",
                    ],
                    "properties": {
                        "action_type": {"type": "string", "enum": list(DM_ACTION_TYPES)},
                        "verb": {"type": "string", "maxLength": 80},
                        "primary_ref": {"type": "string", "enum": [""] + allowed_refs},
                        "secondary_ref": {"type": "string", "enum": [""] + allowed_refs},
                        "unresolved_target": {"type": "string", "maxLength": 120},
                        "desired_effect": {"type": "string", "maxLength": 240},
                        "resolution_hint": {"type": "string", "enum": list(RESOLUTION_HINTS)},
                        "stat_hint": {"type": "string", "enum": [""] + list(ADVENTURE_STATS)},
                    },
                },
            },
            "context_needs": {
                "type": "array",
                "maxItems": 8,
                "uniqueItems": True,
                "items": {"type": "string", "enum": list(CONTEXT_NEEDS)},
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }

    system = (
        "You are SIZA's invisible free-action interpreter. Translate the player's literal intent into the required structured frame. "
        "You do NOT decide whether it works. You do NOT narrate. You do NOT produce outcomes. You do NOT mutate the world. "
        "Do NOT invent objects, NPCs, places, Facts, IDs, capabilities, or conditions. "
        "Use primary_ref/secondary_ref only when the exact ref exists in REFERENCE CATALOG. "
        "scope distinguishes LOCAL references from INVENTORY references; preserve that distinction. "
        "If the player mentions something without a ref, leave the ref empty and copy a short description into unresolved_target. "
        "resolution_hint and stat_hint are classification suggestions, never authority. "
        "Split a compound action into at most three ordered steps. "
        "Keep schema keys, enum values, refs, stat codes, and resolution codes exactly as defined. "
        "Write only the natural-language string values goal, verb, unresolved_target, and desired_effect in the player's language. "
        f"{language_instruction(language)} "
        "Use only information included in this request. Return only valid JSON matching the schema."
    )
    user = {
        "PLAYER_LANGUAGE": language,
        "PLAYER INPUT": str(raw_player_input or ""),
        "CAMPAIGN": {
            "id": plan.get("campaign_id"),
            "objective": _plain_dict(plan.get("objective")).get("text"),
            "active_beat": {
                "id": active_beat.get("id"),
                "state_goal": active_beat.get("state_goal"),
            },
            "relevant_master_cards": selected_cards,
        },
        "WORLD SNAPSHOT": {
            "location": snapshot.get("location"),
            "reference_catalog": refs,
            "active_local_events": _plain_list(snapshot.get("active_local_events")),
            "player_known_facts": _safe_known_facts(snapshot),
        },
    }
    return {
        "raw_player_input": str(raw_player_input or ""),
        "player_language": language,
        "reference_catalog": refs,
        "allowed_refs": allowed_refs,
        "schema": schema,
        "ollama_payload": {
            "stream": False,
            "think": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
            ],
            "options": {"temperature": 0, "num_predict": 480},
        },
        "build": DM_FREE_ACTION_BUILD,
    }


def _extract_model_content(raw_response):
    if isinstance(raw_response, bytes):
        raw_response = raw_response.decode("utf-8", errors="strict")
    outer = json.loads(raw_response) if isinstance(raw_response, str) else _plain_dict(raw_response)
    message = _plain_dict(outer.get("message"))
    content = message.get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("MISSING_MODEL_CONTENT")
    return json.loads(content)


def validate_dm_free_action_intent(intent, allowed_refs):
    packet = _plain_dict(intent)
    errors = []
    top_keys = set(packet)
    expected_top = {"intent", "goal", "steps", "context_needs", "confidence"}
    if top_keys != expected_top:
        errors.append("BAD_TOP_LEVEL_KEYS")

    if str(packet.get("intent") or "") not in DM_ACTION_TYPES:
        errors.append("BAD_INTENT")
    goal = str(packet.get("goal") or "").strip()
    if not goal or len(goal) > 240:
        errors.append("BAD_GOAL")

    steps = _plain_list(packet.get("steps"))
    if not 1 <= len(steps) <= MAX_STEPS:
        errors.append("BAD_STEP_COUNT")
    valid_refs = {"", *[str(value) for value in allowed_refs]}
    normalized_steps = []
    for index, raw_step in enumerate(steps):
        step = _plain_dict(raw_step)
        expected_step = {
            "action_type", "verb", "primary_ref", "secondary_ref", "unresolved_target",
            "desired_effect", "resolution_hint", "stat_hint",
        }
        if set(step) != expected_step:
            errors.append(f"BAD_STEP_KEYS:{index}")
        if str(step.get("action_type") or "") not in DM_ACTION_TYPES:
            errors.append(f"BAD_ACTION_TYPE:{index}")
        for field in ("primary_ref", "secondary_ref"):
            if str(step.get(field) or "") not in valid_refs:
                errors.append(f"INVENTED_REF:{index}:{field}")
        if str(step.get("resolution_hint") or "") not in RESOLUTION_HINTS:
            errors.append(f"BAD_RESOLUTION_HINT:{index}")
        stat = str(step.get("stat_hint") or "")
        if stat and stat not in ADVENTURE_STATS:
            errors.append(f"BAD_STAT_HINT:{index}")
        if len(str(step.get("verb") or "")) > 80:
            errors.append(f"VERB_TOO_LONG:{index}")
        if len(str(step.get("unresolved_target") or "")) > 120:
            errors.append(f"UNRESOLVED_TARGET_TOO_LONG:{index}")
        if len(str(step.get("desired_effect") or "")) > 240:
            errors.append(f"DESIRED_EFFECT_TOO_LONG:{index}")
        normalized_steps.append(step)

    needs = [str(value) for value in _plain_list(packet.get("context_needs"))]
    if len(needs) > 8 or len(set(needs)) != len(needs) or any(value not in CONTEXT_NEEDS for value in needs):
        errors.append("BAD_CONTEXT_NEEDS")
    try:
        confidence = float(packet.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1
    if confidence < 0 or confidence > 1:
        errors.append("BAD_CONFIDENCE")

    return {
        "valid": not errors,
        "errors": errors,
        "intent": str(packet.get("intent") or ""),
        "goal": goal,
        "steps": normalized_steps,
        "context_needs": needs,
        "confidence": confidence,
        "build": DM_FREE_ACTION_BUILD,
    }


def parse_dm_free_action_response(raw_response, allowed_refs, http_status=200):
    if int(http_status or 0) < 200 or int(http_status or 0) >= 300:
        return {"status": "HTTP_ERROR", "accepted": False, "http_status": int(http_status or 0), "build": DM_FREE_ACTION_BUILD}
    try:
        content = _extract_model_content(raw_response)
    except Exception as exc:
        return {"status": "INVALID_MODEL_JSON", "accepted": False, "error": str(exc), "build": DM_FREE_ACTION_BUILD}
    checked = validate_dm_free_action_intent(content, allowed_refs)
    if not checked.get("valid"):
        return {"status": "INVALID_INTENT", "accepted": False, "validation": checked, "build": DM_FREE_ACTION_BUILD}
    return {
        "status": "INTERPRETED",
        "accepted": True,
        "intent": checked,
        "build": DM_FREE_ACTION_BUILD,
    }
