from evennia import search_object

from services.decision_personality import apply_decision_personality
from services.job_claims import (
    arbitrate_job_claims,
    claim_job_task,
    filter_job_candidates_for_claim,
    release_job_claim,
)
from services.job_engine import advance_job_task, collect_job_candidates
from services.need_engine import collect_need_candidates, complete_need_goal
from services.npc_simulation import find_path, routine_entry, simulated_npcs, simstep
from services.relationship_engine import (
    collect_relationship_candidates,
    resolve_relationship_goal,
)
from services.world_clock import schedule_label
from services.world_event_engine import (
    acknowledge_world_event,
    collect_event_candidates,
    refresh_world_event_rules,
)


DECISION_BUILD = "0.22.1-decision-personality-tick-arbitration"

DEFAULT_PRIORITIES = {
    "DANGER": 100,
    "EVENT": 80,
    "NEED": 70,
    "JOB": 60,
    "RELATIONSHIP": 50,
    "ROUTINE": 10,
}


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


def _find_room(room_key, room_id=None):
    if not room_key:
        return None
    for obj in search_object(room_key):
        if room_id is None or obj.db.room_id == room_id:
            return obj
    return None


def _priority_map(npc):
    priorities = dict(DEFAULT_PRIORITIES)
    configured = _plain_dict(npc.db.decision_priorities)
    for key, value in configured.items():
        try:
            priorities[str(key).upper()] = int(value)
        except (TypeError, ValueError):
            continue
    return priorities


def _priority_meta(goal):
    if not goal:
        return {}
    return {
        "priority": goal.get("priority"),
        "base_priority": goal.get("base_priority", goal.get("priority")),
        "personality_modifier": goal.get("personality_modifier", 0),
        "effective_priority": goal.get("effective_priority", goal.get("priority")),
        "priority_modifiers": list(goal.get("priority_modifiers") or []),
    }


def _goal_from_raw(raw, priorities):
    try:
        goal = {str(key): value for key, value in raw.items()}
    except Exception:
        return None

    goal_type = str(goal.get("type", "EVENT")).upper()
    goal["type"] = goal_type
    try:
        goal["priority"] = int(goal.get("priority", priorities.get(goal_type, 0)))
    except (TypeError, ValueError):
        goal["priority"] = priorities.get(goal_type, 0)
    goal["active"] = bool(goal.get("active", False))
    goal["source"] = "AUTHORED_GOAL"
    return goal


def _routine_candidate(npc, priorities):
    index, entry = routine_entry(npc)
    if entry is None:
        return None

    schedule = entry.get("schedule")
    return {
        "id": f"ROUTINE:{entry.get('id') or index}",
        "type": "ROUTINE",
        "priority": priorities.get("ROUTINE", 10),
        "active": True,
        "target_room_id": entry.get("room_id"),
        "target_room_key": entry.get("room_key"),
        "activity": entry.get("activity") or "siguiendo su rutina",
        "one_shot": False,
        "source": "ROUTINE_FALLBACK",
        "routine_index": index,
        "routine_schedule": schedule,
        "routine_schedule_label": schedule_label(schedule),
    }


def collect_candidates(npc):
    """Collect goals, then apply NPC-specific personality modifiers before sorting."""
    priorities = _priority_map(npc)
    candidates = []

    for raw in _plain_list(npc.db.decision_goals):
        goal = _goal_from_raw(raw, priorities)
        if not goal or not goal.get("active"):
            continue
        candidates.append(goal)

    candidates.extend(
        collect_event_candidates(npc, default_priority=priorities.get("EVENT", 80))
    )

    candidates.extend(
        collect_need_candidates(npc, default_priority=priorities.get("NEED", 70))
    )

    job_candidates = collect_job_candidates(
        npc, default_priority=priorities.get("JOB", 60)
    )
    candidates.extend(filter_job_candidates_for_claim(npc, job_candidates))

    candidates.extend(
        collect_relationship_candidates(
            npc, default_priority=priorities.get("RELATIONSHIP", 50)
        )
    )

    routine = _routine_candidate(npc, priorities)
    if routine:
        candidates.append(routine)

    evaluated = []
    for goal in candidates:
        target = _find_room(goal.get("target_room_key"), goal.get("target_room_id"))
        item = dict(goal)
        item["target_exists"] = bool(target)
        item["target_name"] = target.key if target else None
        item["at_target"] = bool(target and npc.location == target)

        if not target or not npc.location:
            item["reachable"] = False
            item["path_length"] = None
        elif npc.location == target:
            item["reachable"] = True
            item["path_length"] = 0
        else:
            path = find_path(npc.location, target)
            item["reachable"] = path is not None
            item["path_length"] = len(path) if path is not None else None

        item = apply_decision_personality(npc, item, base_priority=item.get("priority", 0))
        evaluated.append(item)

    evaluated.sort(
        key=lambda item: (
            bool(item.get("reachable")),
            int(item.get("effective_priority", item.get("priority", 0))),
            -int(item.get("path_length") or 0),
        ),
        reverse=True,
    )
    return evaluated


def choose_goal(npc):
    candidates = collect_candidates(npc)
    reachable = [item for item in candidates if item.get("reachable")]
    selected = reachable[0] if reachable else None
    return {
        "npc": npc.key if npc else None,
        "npc_id": npc.db.npc_id if npc else None,
        "location": npc.location.key if npc and npc.location else None,
        "decision_enabled": bool(npc.db.decision_enabled) if npc else False,
        "candidates": candidates,
        "selected": selected,
        "build": DECISION_BUILD,
    }


def _disable_goal(npc, goal_id):
    goals = _plain_list(npc.db.decision_goals)
    changed = False
    output = []
    for raw in goals:
        try:
            item = {str(key): value for key, value in raw.items()}
        except Exception:
            output.append(raw)
            continue
        if str(item.get("id")) == str(goal_id):
            item["active"] = False
            changed = True
        output.append(item)
    if changed:
        npc.db.decision_goals = output
    return changed


def set_goal_active(npc, goal_id, active):
    goals = _plain_list(npc.db.decision_goals)
    changed = False
    output = []
    for raw in goals:
        try:
            item = {str(key): value for key, value in raw.items()}
        except Exception:
            output.append(raw)
            continue
        if str(item.get("id")) == str(goal_id):
            item["active"] = bool(active)
            changed = True
        output.append(item)
    if changed:
        npc.db.decision_goals = output
    return changed


def _run_routine_fallback(npc, goal):
    """Preserve routine semantics and report the routine entry actually executed."""
    result = dict(simstep(npc) or {})
    result["engine"] = "ROUTINE_FALLBACK"

    executed_routine_id = result.get("routine_id")
    if executed_routine_id:
        result["goal_id"] = f"ROUTINE:{executed_routine_id}"
    else:
        result["goal_id"] = goal.get("id")

    result["goal_type"] = "ROUTINE"
    result["goal_source"] = goal.get("source")
    result.update(_priority_meta(goal))

    status_map = {
        "MOVED": "MOVED_GOAL",
        "ARRIVED": "ARRIVED_GOAL",
        "WAITING": "WAITING_GOAL",
        "AT_TARGET": "AT_GOAL",
    }
    result["status"] = status_map.get(result.get("status"), result.get("status"))
    return result


def _complete_selected_goal(npc, goal):
    source = str(goal.get("source") or "")

    if source == "WORLD_EVENT":
        packet = acknowledge_world_event(npc, goal.get("event_id"))
        return {
            "completed": bool(packet.get("completed")),
            "completion_source": "WORLD_EVENT",
            "completion_site": packet.get("event_site"),
            "event_id": packet.get("event_id"),
            "event_occurrence": packet.get("event_occurrence"),
            "event_acknowledged": bool(packet.get("acknowledged")),
            "event_ack_reason": packet.get("reason"),
        }

    if source == "NPC_NEED":
        return complete_need_goal(npc, goal)

    if source == "WORLD_JOB":
        packet = advance_job_task(
            npc,
            goal.get("task_id"),
            work_units=goal.get("work_per_action") or 1,
        )
        if not packet:
            return {
                "completed": False,
                "worked": False,
                "completion_source": "WORLD_JOB",
                "completion_site": None,
            }
        site = packet.get("site")
        completed = bool(packet.get("completed"))
        released = None
        if completed:
            released = release_job_claim(goal.get("task_id"), npc=npc, force=True)
        return {
            "completed": completed,
            "worked": bool(packet.get("worked")),
            "completion_source": "WORLD_JOB",
            "completion_site": site.key if site else None,
            "task_status": packet.get("status"),
            "work_done_before": packet.get("work_done_before"),
            "work_done": packet.get("work_done"),
            "work_required": packet.get("work_required"),
            "work_added": packet.get("work_added"),
            "job_completion_effects": packet.get("completion_effects") or [],
            "job_claim_released": bool(released),
        }

    if source == "RELATIONSHIP":
        packet = resolve_relationship_goal(
            npc,
            goal.get("relationship_obligation_id"),
            goal.get("relationship_target_npc_id"),
        )
        return {
            "completed": bool(packet.get("completed")),
            "completion_source": "RELATIONSHIP",
            "completion_site": packet.get("location"),
            "relationship_resolved": bool(packet.get("resolved")),
            "relationship_reason": packet.get("reason"),
            "relationship_obligation_id": packet.get("obligation_id")
            or goal.get("relationship_obligation_id"),
            "relationship_target_npc_id": packet.get("target_npc_id")
            or goal.get("relationship_target_npc_id"),
            "relationship_target_name": packet.get("target_name")
            or goal.get("relationship_target_name"),
        }

    if source == "AUTHORED_GOAL" and goal.get("one_shot"):
        changed = _disable_goal(npc, goal.get("id"))
        return {
            "completed": bool(changed),
            "completion_source": "AUTHORED_GOAL",
            "completion_site": None,
        }

    return {
        "completed": False,
        "completion_source": source or None,
        "completion_site": None,
    }


def _goal_action_kind(goal):
    source = str(goal.get("source") or "")
    goal_type = str(goal.get("type") or "").upper()

    if source == "NPC_NEED":
        return str(goal.get("affordance") or "NEED").upper()
    if source == "WORLD_JOB":
        return "WORK"
    if source == "WORLD_EVENT":
        return "DANGER" if goal_type == "DANGER" else "EVENT"
    if source == "RELATIONSHIP":
        return "SOCIAL"
    if goal_type == "DANGER":
        return "DANGER"
    if goal_type == "RELATIONSHIP":
        return "SOCIAL"
    if goal_type == "EVENT":
        return "EVENT"
    return "IDLE"


def _status_after_completion(goal, completion):
    if completion.get("completed"):
        return "GOAL_COMPLETED"
    if str(goal.get("source") or "") == "WORLD_JOB" and completion.get("worked"):
        return "WORKING_GOAL"
    return "AT_GOAL"


def _claim_meta(packet):
    if not packet:
        return {}
    return {
        "job_claim_acquired": bool(packet.get("acquired")),
        "job_claim_owner_id": packet.get("npc_id"),
        "job_claim_owner_name": packet.get("npc_name"),
        "job_claim_reason": packet.get("reason"),
        "job_claim_source": packet.get("claim_source"),
        "job_claim_policy": packet.get("claim_policy"),
        "job_claim_distance": packet.get("claim_distance"),
    }


def _claim_selected_job(npc, decision, goal):
    """Claim a selected WORLD_JOB; retry selection once if another NPC won the race."""
    if not goal or str(goal.get("source") or "") != "WORLD_JOB":
        return decision, goal, None

    claim = claim_job_task(npc, goal.get("task_id"))
    if claim.get("success"):
        return decision, goal, claim

    decision = choose_goal(npc)
    goal = decision.get("selected")
    if not goal or str(goal.get("source") or "") != "WORLD_JOB":
        return decision, goal, None

    claim = claim_job_task(npc, goal.get("task_id"))
    if claim.get("success"):
        return decision, goal, claim
    return decision, None, claim


def decision_step(npc, prepare_world_state=True):
    """Choose and execute one goal; manual calls may prepare producers/arbitration first."""
    if prepare_world_state:
        try:
            refresh_world_event_rules()
            arbitrate_job_claims(simulated_npcs())
        except Exception as exc:
            return {
                "status": "ARBITRATION_ERROR",
                "npc": npc.key if npc else "UNKNOWN",
                "engine": "DECISION",
                "action_kind": "IDLE",
                "error": str(exc),
            }

    decision = choose_goal(npc)
    goal = decision.get("selected")
    decision, goal, claim_packet = _claim_selected_job(npc, decision, goal)

    if not goal:
        npc.db.current_goal = None
        status = "CLAIM_CONFLICT" if claim_packet else "NO_GOAL"
        return {
            "status": status,
            "npc": npc.key,
            "engine": "DECISION",
            "action_kind": "IDLE",
            "decision": decision,
            **_claim_meta(claim_packet),
        }

    claim_meta = _claim_meta(claim_packet)

    npc.db.current_goal = {
        "id": goal.get("id"),
        "type": goal.get("type"),
        "priority": goal.get("priority"),
        "base_priority": goal.get("base_priority"),
        "personality_modifier": goal.get("personality_modifier"),
        "effective_priority": goal.get("effective_priority"),
        "priority_modifiers": list(goal.get("priority_modifiers") or []),
        "target_room_id": goal.get("target_room_id"),
        "target_room_key": goal.get("target_room_key"),
        "activity": goal.get("activity"),
        "source": goal.get("source"),
        "event_id": goal.get("event_id"),
        "event_occurrence": goal.get("occurrence"),
        "task_id": goal.get("task_id"),
        "work_done": goal.get("work_done"),
        "work_required": goal.get("work_required"),
        "claim_npc_id": claim_meta.get("job_claim_owner_id") or goal.get("claim_npc_id"),
        "claim_npc_name": claim_meta.get("job_claim_owner_name") or goal.get("claim_npc_name"),
        "relationship_obligation_id": goal.get("relationship_obligation_id"),
        "relationship_target_npc_id": goal.get("relationship_target_npc_id"),
        "relationship_target_name": goal.get("relationship_target_name"),
        "need_key": goal.get("need_key"),
        "need_rule_id": goal.get("need_rule_id"),
        "affordance": goal.get("affordance"),
        "affordance_id": goal.get("affordance_id"),
        "routine_schedule_label": goal.get("routine_schedule_label"),
    }

    if goal.get("source") == "ROUTINE_FALLBACK":
        return _run_routine_fallback(npc, goal)

    target = _find_room(goal.get("target_room_key"), goal.get("target_room_id"))
    if not target:
        return {
            "status": "BAD_TARGET",
            "npc": npc.key,
            "engine": "DECISION",
            "action_kind": "IDLE",
            "goal": goal,
            **_priority_meta(goal),
            **claim_meta,
        }

    npc.db.destination_id = target.db.room_id

    if npc.location == target:
        npc.db.current_activity = goal.get("activity") or "cumpliendo un objetivo"
        completion = _complete_selected_goal(npc, goal)
        return {
            "status": _status_after_completion(goal, completion),
            "npc": npc.key,
            "engine": "DECISION",
            "goal_id": goal.get("id"),
            "goal_type": goal.get("type"),
            "location": npc.location.key,
            "activity": npc.db.current_activity,
            "action_kind": _goal_action_kind(goal),
            **_priority_meta(goal),
            **claim_meta,
            **completion,
        }

    path = find_path(npc.location, target)
    if path is None:
        npc.db.current_activity = "esperando una ruta disponible"
        return {
            "status": "NO_PATH",
            "npc": npc.key,
            "engine": "DECISION",
            "goal_id": goal.get("id"),
            "goal_type": goal.get("type"),
            "from": npc.location.key,
            "target": target.key,
            "action_kind": "IDLE",
            **_priority_meta(goal),
            **claim_meta,
        }

    if not path:
        return {
            "status": "AT_GOAL",
            "npc": npc.key,
            "engine": "DECISION",
            "goal_id": goal.get("id"),
            "goal_type": goal.get("type"),
            "action_kind": _goal_action_kind(goal),
            **_priority_meta(goal),
            **claim_meta,
        }

    exit_obj = path[0]
    source = npc.location
    destination = exit_obj.destination
    exit_obj.at_traverse(npc, destination)

    if npc.location != destination:
        npc.db.current_activity = "detenida por una condición del camino"
        return {
            "status": "BLOCKED",
            "npc": npc.key,
            "engine": "DECISION",
            "goal_id": goal.get("id"),
            "goal_type": goal.get("type"),
            "from": source.key,
            "target": target.key,
            "attempted_exit": exit_obj.key,
            "action_kind": "IDLE",
            **_priority_meta(goal),
            **claim_meta,
        }

    completion = {
        "completed": False,
        "completion_source": None,
        "completion_site": None,
    }
    if npc.location == target:
        npc.db.current_activity = goal.get("activity") or "cumpliendo un objetivo"
        if str(goal.get("source") or "") == "WORLD_JOB":
            status = "ARRIVED_GOAL"
            action_kind = "MOVE"
        else:
            completion = _complete_selected_goal(npc, goal)
            status = _status_after_completion(goal, completion)
            action_kind = _goal_action_kind(goal)
    else:
        npc.db.current_activity = f"en camino a {target.key}"
        status = "MOVED_GOAL"
        action_kind = "MOVE"

    return {
        "status": status,
        "npc": npc.key,
        "engine": "DECISION",
        "goal_id": goal.get("id"),
        "goal_type": goal.get("type"),
        "from": source.key,
        "to": npc.location.key,
        "target": target.key,
        "used_exit": exit_obj.key,
        "activity": npc.db.current_activity,
        "action_kind": action_kind,
        **_priority_meta(goal),
        **claim_meta,
        **completion,
    }
