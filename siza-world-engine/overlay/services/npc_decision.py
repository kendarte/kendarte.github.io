from evennia import search_object

from services.job_engine import collect_job_candidates, complete_job_task
from services.need_engine import collect_need_candidates, complete_need_goal
from services.npc_simulation import find_path, simstep


DECISION_BUILD = "0.9.0-needs"

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
    routine = _plain_list(npc.db.routine)
    if not routine:
        return None
    try:
        index = int(npc.db.routine_index or 0) % len(routine)
    except (TypeError, ValueError):
        index = 0

    try:
        entry = {str(key): value for key, value in routine[index].items()}
    except Exception:
        return None

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
    }


def collect_candidates(npc):
    """Collect authored, NEED, JOB and routine goals from their authoritative sources."""
    priorities = _priority_map(npc)
    candidates = []

    # Explicit authored goals such as world events/debug events attached to the NPC.
    for raw in _plain_list(npc.db.decision_goals):
        goal = _goal_from_raw(raw, priorities)
        if not goal or not goal.get("active"):
            continue
        candidates.append(goal)

    # NEED goals are derived from persistent NPC state and world affordances.
    candidates.extend(
        collect_need_candidates(npc, default_priority=priorities.get("NEED", 70))
    )

    # JOB goals are derived from persistent task records stored in the world.
    candidates.extend(
        collect_job_candidates(npc, default_priority=priorities.get("JOB", 60))
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
        evaluated.append(item)

    evaluated.sort(
        key=lambda item: (
            bool(item.get("reachable")),
            int(item.get("priority", 0)),
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
    """Preserve the proven v0.4 routine wait/advance semantics when routine wins."""
    result = dict(simstep(npc) or {})
    result["engine"] = "ROUTINE_FALLBACK"
    result["goal_id"] = goal.get("id")
    result["goal_type"] = "ROUTINE"
    result["priority"] = goal.get("priority")
    result["goal_source"] = goal.get("source")

    status_map = {
        "MOVED": "MOVED_GOAL",
        "ARRIVED": "ARRIVED_GOAL",
        "WAITING": "WAITING_GOAL",
        "AT_TARGET": "AT_GOAL",
    }
    result["status"] = status_map.get(result.get("status"), result.get("status"))
    return result


def _complete_selected_goal(npc, goal):
    """Commit completion back to the authoritative source that produced the goal."""
    source = str(goal.get("source") or "")

    if source == "NPC_NEED":
        return complete_need_goal(npc, goal)

    if source == "WORLD_JOB":
        site = complete_job_task(npc, goal.get("task_id"))
        return {
            "completed": bool(site),
            "completion_source": "WORLD_JOB",
            "completion_site": site.key if site else None,
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


def decision_step(npc):
    """Choose one authorized goal and execute at most one real Exit hop."""
    decision = choose_goal(npc)
    goal = decision.get("selected")
    if not goal:
        npc.db.current_goal = None
        return {
            "status": "NO_GOAL",
            "npc": npc.key,
            "engine": "DECISION",
            "decision": decision,
        }

    npc.db.current_goal = {
        "id": goal.get("id"),
        "type": goal.get("type"),
        "priority": goal.get("priority"),
        "target_room_id": goal.get("target_room_id"),
        "target_room_key": goal.get("target_room_key"),
        "activity": goal.get("activity"),
        "source": goal.get("source"),
        "task_id": goal.get("task_id"),
        "need_key": goal.get("need_key"),
        "need_rule_id": goal.get("need_rule_id"),
        "affordance": goal.get("affordance"),
        "affordance_id": goal.get("affordance_id"),
    }

    if goal.get("source") == "ROUTINE_FALLBACK":
        return _run_routine_fallback(npc, goal)

    target = _find_room(goal.get("target_room_key"), goal.get("target_room_id"))
    if not target:
        return {
            "status": "BAD_TARGET",
            "npc": npc.key,
            "engine": "DECISION",
            "goal": goal,
        }

    npc.db.destination_id = target.db.room_id

    if npc.location == target:
        npc.db.current_activity = goal.get("activity") or "cumpliendo un objetivo"
        completion = _complete_selected_goal(npc, goal)
        status = "GOAL_COMPLETED" if completion.get("completed") else "AT_GOAL"
        return {
            "status": status,
            "npc": npc.key,
            "engine": "DECISION",
            "goal_id": goal.get("id"),
            "goal_type": goal.get("type"),
            "priority": goal.get("priority"),
            "location": npc.location.key,
            "activity": npc.db.current_activity,
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
            "priority": goal.get("priority"),
            "from": npc.location.key,
            "target": target.key,
        }

    if not path:
        return {
            "status": "AT_GOAL",
            "npc": npc.key,
            "engine": "DECISION",
            "goal_id": goal.get("id"),
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
            "priority": goal.get("priority"),
            "from": source.key,
            "target": target.key,
            "attempted_exit": exit_obj.key,
        }

    completion = {
        "completed": False,
        "completion_source": None,
        "completion_site": None,
    }
    if npc.location == target:
        npc.db.current_activity = goal.get("activity") or "cumpliendo un objetivo"
        completion = _complete_selected_goal(npc, goal)
        status = "GOAL_COMPLETED" if completion.get("completed") else "ARRIVED_GOAL"
    else:
        npc.db.current_activity = f"en camino a {target.key}"
        status = "MOVED_GOAL"

    return {
        "status": status,
        "npc": npc.key,
        "engine": "DECISION",
        "goal_id": goal.get("id"),
        "goal_type": goal.get("type"),
        "priority": goal.get("priority"),
        "from": source.key,
        "to": npc.location.key,
        "target": target.key,
        "used_exit": exit_obj.key,
        "activity": npc.db.current_activity,
        **completion,
    }
