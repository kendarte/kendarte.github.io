from services.action_resolution_engine import normalize_check_spec


DM_ADJUDICATOR_BUILD = "dm-0.1-free-action-adjudicator"
AUTHORED_EXECUTORS = {
    "OBJECT_ACTION",
    "INTERACTION",
    "MOVEMENT",
    "COMBAT",
    "CHECK_ONLY",
}
GENERIC_JUDGMENT_ACTIONS = {
    "OBSERVE",
    "SEARCH",
    "PERSUADE",
    "DECEIVE",
    "THREATEN",
    "GIVE",
    "USE",
    "MOVE_OBJECT",
    "OPEN",
    "CLOSE",
    "BREAK",
    "DEFEND",
    "STEAL",
    "HIDE",
    "CREATE",
    "COMBINE",
    "WAIT",
    "OTHER",
}


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


def _resolve_ref(actor, ref):
    wanted = str(ref or "").strip()
    if not actor or not wanted:
        return None
    if wanted == "SELF":
        return actor
    if wanted == "ROOM":
        return getattr(actor, "location", None)

    location = getattr(actor, "location", None)
    local = list(getattr(location, "contents", []) or []) if location else []
    inventory = list(getattr(actor, "contents", []) or [])
    exits = list(getattr(location, "exits", []) or []) if location else []

    if wanted.startswith("DBREF:"):
        try:
            dbref = int(wanted.split(":", 1)[1])
        except (TypeError, ValueError):
            return None
        for obj in [actor, location, *local, *inventory]:
            if obj is not None and getattr(obj, "id", None) == dbref:
                return obj
        return None

    if wanted.startswith("EXIT_DBREF:"):
        try:
            dbref = int(wanted.split(":", 1)[1])
        except (TypeError, ValueError):
            return None
        return next((obj for obj in exits if getattr(obj, "id", None) == dbref), None)

    if wanted.startswith("EXIT_ID:"):
        exit_id = wanted.split(":", 1)[1]
        return next((obj for obj in exits if str(getattr(obj.db, "exit_id", "") or "") == exit_id), None)
    return None


def _is_local(actor, obj):
    if not actor or not obj:
        return False
    return getattr(obj, "location", None) is getattr(actor, "location", None)


def _is_inventory(actor, obj):
    return bool(actor and obj and getattr(obj, "location", None) is actor)


def _verified_context(obj, actor):
    if not obj:
        return None
    location = getattr(actor, "location", None) if actor else None
    if obj is actor:
        kind = "SELF"
    elif obj is location:
        kind = "ROOM"
    elif getattr(obj, "destination", None):
        kind = "EXIT"
    elif bool(getattr(obj.db, "is_npc", False)):
        kind = "NPC"
    else:
        kind = "OBJECT"
    state = _plain_dict(getattr(obj.db, "state", {}))
    return {
        "name": str(getattr(obj, "key", "")),
        "dbref": int(obj.id) if getattr(obj, "id", None) is not None else None,
        "kind": kind,
        "is_local": _is_local(actor, obj),
        "in_inventory": _is_inventory(actor, obj),
        "portable": bool(getattr(obj.db, "portable", False)),
        "state": state,
    }


def _authored_affordance(target, action_type):
    if not target:
        return None
    wanted = str(action_type or "").upper().strip()
    for raw in _plain_list(getattr(target.db, "dm_affordances", [])):
        row = _plain_dict(raw)
        if not bool(row.get("enabled", True)):
            continue
        if str(row.get("action_type") or "").upper().strip() != wanted:
            continue
        executor = str(row.get("executor") or "").upper().strip()
        if executor not in AUTHORED_EXECUTORS:
            continue
        check = None
        if row.get("check"):
            checked = normalize_check_spec(row.get("check"))
            if not checked.get("valid"):
                continue
            check = checked
        return {
            "id": str(row.get("id") or ""),
            "action_type": wanted,
            "executor": executor,
            "object_action_id": str(row.get("object_action_id") or "") or None,
            "interaction_intent": str(row.get("interaction_intent") or "") or None,
            "check": check,
            "metadata": _plain_dict(row.get("metadata")),
        }
    return None


def _adjudicate_step(actor, step, index):
    row = _plain_dict(step)
    action_type = str(row.get("action_type") or "").upper().strip()
    primary_ref = str(row.get("primary_ref") or "").strip()
    secondary_ref = str(row.get("secondary_ref") or "").strip()
    unresolved = str(row.get("unresolved_target") or "").strip()
    primary = _resolve_ref(actor, primary_ref)
    secondary = _resolve_ref(actor, secondary_ref) if secondary_ref else None

    base = {
        "index": int(index),
        "action_type": action_type,
        "primary_ref": primary_ref,
        "secondary_ref": secondary_ref,
        "desired_effect": str(row.get("desired_effect") or ""),
        "model_resolution_hint": str(row.get("resolution_hint") or ""),
        "model_stat_hint": str(row.get("stat_hint") or ""),
    }

    if unresolved and not primary_ref:
        return {
            **base,
            "status": "NEEDS_CONTEXT",
            "admissible": False,
            "reason": "UNRESOLVED_TARGET",
            "unresolved_target": unresolved,
        }
    if primary_ref and not primary:
        return {**base, "status": "REJECTED", "admissible": False, "reason": "PRIMARY_REF_NOT_CURRENT"}
    if secondary_ref and not secondary:
        return {**base, "status": "REJECTED", "admissible": False, "reason": "SECONDARY_REF_NOT_CURRENT"}

    if action_type == "MOVE" and primary in list(getattr(getattr(actor, "location", None), "exits", []) or []):
        return {
            **base,
            "status": "ADMISSIBLE",
            "admissible": True,
            "executor": "MOVEMENT",
            "target_dbref": int(primary.id),
            "target_name": str(primary.key),
        }

    if action_type == "TAKE" and primary:
        if bool(getattr(primary.db, "is_npc", False)):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "TARGET_IS_CHARACTER"}
        if not _is_local(actor, primary):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "TARGET_NOT_LOCAL"}
        if not bool(getattr(primary.db, "portable", False)):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "TARGET_NOT_PORTABLE"}
        return {
            **base,
            "status": "ADMISSIBLE",
            "admissible": True,
            "executor": "GENERIC_TAKE",
            "target_dbref": int(primary.id),
            "target_name": str(primary.key),
        }

    if action_type == "DROP" and primary:
        if not _is_inventory(actor, primary):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "TARGET_NOT_IN_INVENTORY"}
        return {
            **base,
            "status": "ADMISSIBLE",
            "admissible": True,
            "executor": "GENERIC_DROP",
            "target_dbref": int(primary.id),
            "target_name": str(primary.key),
        }

    if action_type == "ATTACK" and primary:
        if not bool(getattr(primary.db, "is_npc", False)):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "COMBAT_TARGET_NOT_CHARACTER"}
        if not _is_local(actor, primary):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "COMBAT_TARGET_NOT_LOCAL"}
        return {
            **base,
            "status": "ADMISSIBLE",
            "admissible": True,
            "executor": "COMBAT",
            "target_dbref": int(primary.id),
            "target_name": str(primary.key),
        }

    if action_type == "TALK" and primary:
        if not bool(getattr(primary.db, "is_npc", False)) or not _is_local(actor, primary):
            return {**base, "status": "REJECTED", "admissible": False, "reason": "INTERACTION_TARGET_NOT_LOCAL_NPC"}
        return {
            **base,
            "status": "ADMISSIBLE",
            "admissible": True,
            "executor": "INTERACTION",
            "target_dbref": int(primary.id),
            "target_name": str(primary.key),
        }

    affordance_target = primary or getattr(actor, "location", None)
    affordance = _authored_affordance(affordance_target, action_type)
    if affordance:
        return {
            **base,
            "status": "ADMISSIBLE",
            "admissible": True,
            "executor": affordance.get("executor"),
            "target_dbref": int(affordance_target.id) if getattr(affordance_target, "id", None) is not None else None,
            "target_name": str(getattr(affordance_target, "key", "")),
            "affordance": affordance,
            "authoritative_check": affordance.get("check"),
        }

    if action_type in GENERIC_JUDGMENT_ACTIONS:
        if primary_ref and primary is None:
            return {**base, "status": "REJECTED", "admissible": False, "reason": "PRIMARY_REF_NOT_CURRENT"}
        if secondary_ref and secondary is None:
            return {**base, "status": "REJECTED", "admissible": False, "reason": "SECONDARY_REF_NOT_CURRENT"}
        return {
            **base,
            "status": "NEEDS_JUDGMENT",
            "admissible": False,
            "reason": "REQUIRES_BOUNDED_DM_JUDGMENT",
            "target_dbref": int(primary.id) if primary and getattr(primary, "id", None) is not None else None,
            "target_name": str(getattr(primary, "key", "")) if primary else None,
            "verified_context": {
                "primary": _verified_context(primary, actor),
                "secondary": _verified_context(secondary, actor),
            },
        }

    return {
        **base,
        "status": "REJECTED",
        "admissible": False,
        "reason": "NO_AUTHORIZED_EXECUTION_ROUTE",
    }


def adjudicate_dm_free_action(actor, interpreted_packet):
    """Revalidate model references against current world state and choose only authorized executors or bounded judgment."""
    packet = _plain_dict(interpreted_packet)
    if packet.get("status") != "INTERPRETED" or packet.get("accepted") is not True:
        return {"status": "NOT_INTERPRETED", "admissible": False, "steps": [], "build": DM_ADJUDICATOR_BUILD}
    intent = _plain_dict(packet.get("intent"))
    steps = [
        _adjudicate_step(actor, raw, index)
        for index, raw in enumerate(_plain_list(intent.get("steps")))
    ]
    if not steps:
        return {"status": "NO_STEPS", "admissible": False, "steps": [], "build": DM_ADJUDICATOR_BUILD}
    if any(row.get("status") == "NEEDS_CONTEXT" for row in steps):
        status = "NEEDS_CONTEXT"
    elif any(row.get("status") == "REJECTED" for row in steps):
        status = "NOT_ADMISSIBLE"
    elif any(row.get("status") == "NEEDS_JUDGMENT" for row in steps):
        status = "NEEDS_JUDGMENT"
    elif all(row.get("admissible") is True for row in steps):
        status = "ADMISSIBLE"
    else:
        status = "NOT_ADMISSIBLE"
    return {
        "status": status,
        "admissible": status == "ADMISSIBLE",
        "goal": str(intent.get("goal") or ""),
        "context_needs": list(intent.get("context_needs") or []),
        "steps": steps,
        "model_confidence": intent.get("confidence"),
        "authority": {
            "model_result_used": False,
            "model_difficulty_used": False,
            "references_revalidated": True,
            "execution_requires_separate_bridge": True,
        },
        "build": DM_ADJUDICATOR_BUILD,
    }
