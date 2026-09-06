from datetime import datetime, timezone

from services.actor_registry import find_npc_by_id

from services.decision_personality import apply_decision_personality
from services.job_engine import job_sites
from services.need_engine import collect_need_candidates
from services.npc_simulation import find_path, find_room, routine_entry
from services.relationship_engine import collect_relationship_candidates
from services.skill_engine import check_task_skills
from services.world_clock import schedule_is_active, schedule_label, world_clock_state
from services.world_event_engine import collect_event_candidates, danger_blocks_room


CLAIM_BUILD = "0.31.0-skills-competence"
POLICY_FIRST_SELECTED = "FIRST_SELECTED"
POLICY_NEAREST_REACHABLE = "NEAREST_REACHABLE"

DEFAULT_PRIORITIES = {
    "DANGER": 100,
    "EVENT": 80,
    "NEED": 70,
    "JOB": 60,
    "RELATIONSHIP": 50,
    "ROUTINE": 10,
}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _task_dict(raw):
    try:
        return {str(key): value for key, value in raw.items()}
    except Exception:
        return None


def _npc_job(npc):
    try:
        return dict(npc.db.job or {})
    except Exception:
        return {}


def _npc_job_id(npc):
    return str(_npc_job(npc).get("id") or "").strip()


def _job_schedule(npc):
    schedule = _plain_dict(getattr(npc.db, "job_schedule", {}))
    if schedule:
        return schedule
    job = _npc_job(npc)
    return _plain_dict(job.get("schedule"))


def _shift_status(npc):
    schedule = _job_schedule(npc)
    if not schedule:
        return {
            "scheduled": False,
            "active": True,
            "label": "ALWAYS",
            "schedule": {},
        }
    state = world_clock_state()
    return {
        "scheduled": True,
        "active": bool(schedule_is_active(schedule, state=state)),
        "label": schedule_label(schedule),
        "schedule": schedule,
        "day": state.get("day"),
        "minute": state.get("minute"),
        "time": state.get("time"),
    }


def _priority_map(npc):
    priorities = dict(DEFAULT_PRIORITIES)
    configured = _plain_dict(getattr(npc.db, "decision_priorities", {}))
    for key, value in configured.items():
        try:
            priorities[str(key).upper()] = int(value)
        except (TypeError, ValueError):
            continue
    return priorities


def _npc_by_id(npc_id):
    return find_npc_by_id(npc_id)


def _npc_exists(npc_id):
    return _npc_by_id(npc_id) is not None


def _site_tasks(site):
    tasks = {}
    for raw in _plain_list(site.db.job_tasks):
        task = _task_dict(raw)
        if task and task.get("id"):
            tasks[str(task.get("id"))] = task
    return tasks


def _site_claims(site):
    claims = _plain_dict(site.db.job_claims)
    output = {}
    for task_id, raw in claims.items():
        try:
            output[str(task_id)] = {str(key): value for key, value in raw.items()}
        except Exception:
            continue
    return output


def _task_site(task_id):
    wanted = str(task_id or "")
    if not wanted:
        return None
    for site in job_sites():
        if wanted in _site_tasks(site):
            return site
    return None


def _task_policy(task):
    return str((task or {}).get("claim_policy") or POLICY_FIRST_SELECTED).upper()


def _eligible_for_task(npc, task):
    if not npc or not bool(npc.db.simulation_enabled) or not bool(npc.db.decision_enabled):
        return False
    npc_id = str(getattr(npc.db, "npc_id", "") or "")
    if not npc_id or not npc.location:
        return False

    required_job = str((task or {}).get("job_id") or "").strip()
    assigned_npc = str((task or {}).get("assigned_npc_id") or "").strip()
    if required_job and required_job != _npc_job_id(npc):
        return False
    if assigned_npc and assigned_npc != npc_id:
        return False
    return True


def _goal_reachable(npc, goal):
    target_key = str((goal or {}).get("target_room_key") or "").strip()
    target_id = (goal or {}).get("target_room_id")
    if not target_key or not npc or not npc.location:
        return False
    target = find_room(target_key, target_id)
    if not target:
        return False
    if npc.location == target:
        return True
    return find_path(npc.location, target) is not None


def _decorate_goal(npc, goal, fallback_priority, source=None, goal_type=None):
    item = dict(goal or {})
    if goal_type:
        item["type"] = str(goal_type).upper()
    else:
        item["type"] = str(item.get("type") or "EVENT").upper()
    if source:
        item["source"] = source
    try:
        base = int(item.get("priority", fallback_priority))
    except (TypeError, ValueError):
        base = int(fallback_priority)
    item["priority"] = base
    return apply_decision_personality(npc, item, base_priority=base)


def _blocker_row(goal):
    return {
        "id": goal.get("id"),
        "type": goal.get("type"),
        "priority": goal.get("priority"),
        "base_priority": goal.get("base_priority"),
        "personality_modifier": goal.get("personality_modifier", 0),
        "source": goal.get("source"),
    }


def _routine_goal(npc, priorities):
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
        "source": "ROUTINE_FALLBACK",
        "routine_index": index,
        "routine_schedule": schedule,
        "routine_schedule_label": schedule_label(schedule),
    }


def _higher_priority_blockers(npc, job_priority):
    """Return every reachable effective goal that outranks this NPC's effective JOB."""
    priorities = _priority_map(npc)
    blockers = []

    for raw in _plain_list(getattr(npc.db, "decision_goals", [])):
        try:
            goal = {str(key): value for key, value in raw.items()}
        except Exception:
            continue
        if not bool(goal.get("active", False)):
            continue
        goal_type = str(goal.get("type") or "EVENT").upper()
        decorated = _decorate_goal(
            npc,
            goal,
            priorities.get(goal_type, 0),
            source="AUTHORED_GOAL",
            goal_type=goal_type,
        )
        if int(decorated.get("priority", 0)) <= int(job_priority):
            continue
        if not _goal_reachable(npc, decorated):
            continue
        blockers.append(_blocker_row(decorated))

    for goal in collect_event_candidates(npc, default_priority=priorities.get("EVENT", 80)):
        goal_type = str(goal.get("type") or "EVENT").upper()
        fallback = priorities.get(goal_type, priorities.get("EVENT", 80))
        decorated = _decorate_goal(
            npc,
            goal,
            fallback,
            source="WORLD_EVENT",
            goal_type=goal_type,
        )
        if int(decorated.get("priority", 0)) <= int(job_priority):
            continue
        if not _goal_reachable(npc, decorated):
            continue
        blockers.append(_blocker_row(decorated))

    for goal in collect_need_candidates(npc, default_priority=priorities.get("NEED", 70)):
        decorated = _decorate_goal(
            npc,
            goal,
            priorities.get("NEED", 70),
            source="NPC_NEED",
            goal_type="NEED",
        )
        if int(decorated.get("priority", 0)) <= int(job_priority):
            continue
        if not _goal_reachable(npc, decorated):
            continue
        blockers.append(_blocker_row(decorated))

    for goal in collect_relationship_candidates(
        npc, default_priority=priorities.get("RELATIONSHIP", 50)
    ):
        decorated = _decorate_goal(
            npc,
            goal,
            priorities.get("RELATIONSHIP", 50),
            source="RELATIONSHIP",
            goal_type="RELATIONSHIP",
        )
        if int(decorated.get("priority", 0)) <= int(job_priority):
            continue
        if not _goal_reachable(npc, decorated):
            continue
        blockers.append(_blocker_row(decorated))

    routine = _routine_goal(npc, priorities)
    if routine:
        decorated = _decorate_goal(
            npc,
            routine,
            priorities.get("ROUTINE", 10),
            source="ROUTINE_FALLBACK",
            goal_type="ROUTINE",
        )
        if int(decorated.get("priority", 0)) > int(job_priority) and _goal_reachable(npc, decorated):
            blockers.append(_blocker_row(decorated))

    blockers.sort(key=lambda row: int(row.get("priority", 0)), reverse=True)
    return blockers


def _owned_other_claim(npc_id, task_id):
    wanted_npc = str(npc_id or "")
    wanted_task = str(task_id or "")
    if not wanted_npc:
        return None
    for site in job_sites():
        for other_task_id, claim in _site_claims(site).items():
            if str(other_task_id) == wanted_task:
                continue
            if str(claim.get("npc_id") or "") == wanted_npc:
                return {
                    "task_id": other_task_id,
                    "site": site.key,
                    "npc_id": wanted_npc,
                    "npc_name": claim.get("npc_name"),
                }
    return None


def _availability_for_task(npc, task_id, task):
    if not _eligible_for_task(npc, task):
        return {
            "available": False,
            "reason": "NOT_ELIGIBLE",
            "blocker": None,
        }

    skill_check = check_task_skills(npc, task)
    if not skill_check.get("eligible", True):
        missing = (skill_check.get("missing") or [{}])[0]
        return {
            "available": False,
            "reason": "SKILL_REQUIREMENT",
            "blocker": {
                "id": missing.get("skill_id"),
                "type": "SKILL",
                "priority": None,
                "source": "SKILL_GATE",
                "level": missing.get("level"),
                "required_level": missing.get("min_level"),
            },
            "skill_check": skill_check,
        }

    shift = _shift_status(npc)
    if shift.get("scheduled") and not shift.get("active"):
        return {
            "available": False,
            "reason": "SHIFT_INACTIVE",
            "blocker": {
                "id": shift.get("label"),
                "type": "SHIFT",
                "priority": None,
                "source": "WORLD_CLOCK",
            },
            "shift": shift,
        }

    site = _task_site(task_id)
    danger = danger_blocks_room(site, npc=npc) if site else None
    if danger:
        return {
            "available": False,
            "reason": "DANGER_TARGET",
            "blocker": {
                "id": danger.get("event_id"),
                "type": "DANGER",
                "priority": danger.get("priority"),
                "source": "WORLD_EVENT",
            },
            "shift": shift,
        }

    priorities = _priority_map(npc)
    try:
        base_job_priority = int((task or {}).get("priority", priorities.get("JOB", 60)))
    except (TypeError, ValueError):
        base_job_priority = int(priorities.get("JOB", 60))

    job_goal = dict(task or {})
    job_goal.update(
        {
            "id": f"JOB:{task_id}",
            "task_id": task_id,
            "type": "JOB",
            "source": "WORLD_JOB",
            "priority": base_job_priority,
            "target_room_id": getattr(site.db, "room_id", None) if site else None,
            "target_room_key": site.key if site else None,
        }
    )
    decorated_job = apply_decision_personality(
        npc, job_goal, base_priority=base_job_priority
    )
    job_priority = int(decorated_job.get("priority", base_job_priority))

    blockers = _higher_priority_blockers(npc, job_priority)
    if blockers:
        blocker = blockers[0]
        return {
            "available": False,
            "reason": "HIGHER_PRIORITY_GOAL",
            "blocker": blocker,
            "shift": shift,
            "job_priority": job_priority,
            "job_base_priority": base_job_priority,
            "job_personality_modifier": decorated_job.get("personality_modifier", 0),
        }

    npc_id = str(getattr(npc.db, "npc_id", "") or "")
    other_claim = _owned_other_claim(npc_id, task_id)
    if other_claim:
        return {
            "available": False,
            "reason": "BUSY_OTHER_JOB",
            "blocker": {
                "id": other_claim.get("task_id"),
                "type": "JOB",
                "priority": None,
                "source": "JOB_CLAIM",
            },
            "shift": shift,
        }

    return {
        "available": True,
        "reason": "AVAILABLE",
        "blocker": None,
        "shift": shift,
        "job_priority": job_priority,
        "job_base_priority": base_job_priority,
        "job_personality_modifier": decorated_job.get("personality_modifier", 0),
    }


def refresh_job_claims():
    """Remove claims invalidated by task state, owner existence or lost skill eligibility."""
    released = []
    for site in job_sites():
        tasks = _site_tasks(site)
        claims = _site_claims(site)
        changed = False
        for task_id in list(claims.keys()):
            task = tasks.get(task_id)
            claim = claims.get(task_id) or {}
            owner_id = str(claim.get("npc_id") or "")
            owner = _npc_by_id(owner_id)
            invalid_task = (
                task is None
                or not bool(task.get("active", False))
                or str(task.get("status") or "") in {"inactive", "completed"}
            )
            invalid_owner = owner is None
            invalid_skill = bool(
                task is not None
                and owner is not None
                and not check_task_skills(owner, task).get("eligible", True)
            )
            if invalid_task or invalid_owner or invalid_skill:
                reason = "TASK_INACTIVE" if invalid_task else "OWNER_MISSING" if invalid_owner else "SKILL_REQUIREMENT"
                released.append(
                    {
                        "task_id": task_id,
                        "site": site.key,
                        "npc_id": owner_id,
                        "npc_name": claim.get("npc_name"),
                        "reason": reason,
                    }
                )
                claims.pop(task_id, None)
                changed = True
        if changed:
            site.db.job_claims = claims
    return released


def get_job_claim(task_id):
    refresh_job_claims()
    wanted = str(task_id or "")
    for site in job_sites():
        claim = _site_claims(site).get(wanted)
        if claim:
            packet = dict(claim)
            packet["site"] = site
            packet["task_id"] = wanted
            return packet
    return None


def claim_job_task(
    npc,
    task_id,
    claim_source="DECISION",
    claim_policy=None,
    claim_distance=None,
):
    """Atomically claim one active task for an eligible, on-shift, available NPC."""
    refresh_job_claims()
    wanted = str(task_id or "")
    npc_id = str(getattr(npc.db, "npc_id", "") or "") if npc else ""
    npc_job_id = _npc_job_id(npc) if npc else ""
    if not npc or not npc_id:
        return {"success": False, "acquired": False, "reason": "NO_NPC"}

    for site in job_sites():
        task = _site_tasks(site).get(wanted)
        if not task:
            continue
        if not bool(task.get("active", False)):
            return {
                "success": False,
                "acquired": False,
                "reason": "TASK_INACTIVE",
                "site": site,
            }

        required_job = str(task.get("job_id") or "").strip()
        assigned_npc = str(task.get("assigned_npc_id") or "").strip()
        if required_job and required_job != npc_job_id:
            return {
                "success": False,
                "acquired": False,
                "reason": "WRONG_JOB",
                "site": site,
            }
        if assigned_npc and assigned_npc != npc_id:
            return {
                "success": False,
                "acquired": False,
                "reason": "ASSIGNED_OTHER",
                "site": site,
            }

        claims = _site_claims(site)
        existing = claims.get(wanted)
        if existing:
            owner_id = str(existing.get("npc_id") or "")
            if owner_id == npc_id:
                return {
                    "success": True,
                    "acquired": False,
                    "reason": "ALREADY_OWNER",
                    "site": site,
                    "task_id": wanted,
                    "npc_id": npc_id,
                    "npc_name": npc.key,
                    "claim_source": existing.get("claim_source"),
                    "claim_policy": existing.get("claim_policy"),
                    "claim_distance": existing.get("claim_distance"),
                }
            return {
                "success": False,
                "acquired": False,
                "reason": "CLAIMED_OTHER",
                "site": site,
                "task_id": wanted,
                "npc_id": owner_id,
                "npc_name": existing.get("npc_name"),
            }

        availability = _availability_for_task(npc, wanted, task)
        if not availability.get("available"):
            return {
                "success": False,
                "acquired": False,
                "reason": availability.get("reason"),
                "site": site,
                "task_id": wanted,
                "npc_id": npc_id,
                "npc_name": npc.key,
                "blocker": availability.get("blocker"),
            }

        policy = str(claim_policy or _task_policy(task)).upper()
        claims[wanted] = {
            "npc_id": npc_id,
            "npc_name": npc.key,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "claim_source": str(claim_source or "DECISION").upper(),
            "claim_policy": policy,
            "claim_distance": claim_distance,
            "canon_status": "prototype",
        }
        site.db.job_claims = claims
        return {
            "success": True,
            "acquired": True,
            "reason": "CLAIMED",
            "site": site,
            "task_id": wanted,
            "npc_id": npc_id,
            "npc_name": npc.key,
            "claim_source": str(claim_source or "DECISION").upper(),
            "claim_policy": policy,
            "claim_distance": claim_distance,
        }

    return {"success": False, "acquired": False, "reason": "TASK_NOT_FOUND"}


def arbitrate_job_claims(npcs):
    """Pre-assign unclaimed NEAREST_REACHABLE tasks to actually available NPCs."""
    refresh_job_claims()
    npcs = list(npcs or [])
    results = []

    for site in job_sites():
        tasks = _site_tasks(site)
        claims = _site_claims(site)
        for task_id, task in tasks.items():
            if not bool(task.get("active", False)):
                continue
            policy = _task_policy(task)
            if policy != POLICY_NEAREST_REACHABLE:
                continue
            if task_id in claims:
                continue

            candidates = []
            excluded = []
            for npc in npcs:
                if not _eligible_for_task(npc, task):
                    continue

                availability = _availability_for_task(npc, task_id, task)
                if not availability.get("available"):
                    blocker = availability.get("blocker") or {}
                    excluded.append(
                        {
                            "npc_id": str(npc.db.npc_id or ""),
                            "npc_name": npc.key,
                            "reason": availability.get("reason"),
                            "blocker_id": blocker.get("id"),
                            "blocker_type": blocker.get("type"),
                            "blocker_priority": blocker.get("priority"),
                            "blocker_base_priority": blocker.get("base_priority"),
                            "blocker_personality_modifier": blocker.get("personality_modifier", 0),
                            "job_priority": availability.get("job_priority"),
                            "job_base_priority": availability.get("job_base_priority"),
                            "job_personality_modifier": availability.get("job_personality_modifier", 0),
                        }
                    )
                    continue

                path = find_path(npc.location, site)
                if path is None:
                    excluded.append(
                        {
                            "npc_id": str(npc.db.npc_id or ""),
                            "npc_name": npc.key,
                            "reason": "UNREACHABLE",
                            "blocker_id": None,
                            "blocker_type": None,
                            "blocker_priority": None,
                        }
                    )
                    continue
                npc_id = str(npc.db.npc_id or "")
                candidates.append(
                    {
                        "npc": npc,
                        "npc_id": npc_id,
                        "npc_name": npc.key,
                        "distance": len(path),
                        "job_priority": availability.get("job_priority"),
                    }
                )

            candidates.sort(
                key=lambda row: (
                    int(row.get("distance", 0)),
                    str(row.get("npc_id") or ""),
                )
            )
            public_candidates = [
                {
                    "npc_id": row.get("npc_id"),
                    "npc_name": row.get("npc_name"),
                    "distance": row.get("distance"),
                    "job_priority": row.get("job_priority"),
                }
                for row in candidates
            ]

            if not candidates:
                results.append(
                    {
                        "status": "NO_AVAILABLE",
                        "site": site.key,
                        "task_id": task_id,
                        "policy": policy,
                        "winner_id": None,
                        "winner_name": None,
                        "distance": None,
                        "candidates": [],
                        "excluded": excluded,
                    }
                )
                continue

            winner = candidates[0]
            claim = claim_job_task(
                winner.get("npc"),
                task_id,
                claim_source="ARBITRATOR",
                claim_policy=policy,
                claim_distance=winner.get("distance"),
            )
            results.append(
                {
                    "status": "ASSIGNED" if claim.get("success") else "CLAIM_FAILED",
                    "site": site.key,
                    "task_id": task_id,
                    "policy": policy,
                    "winner_id": winner.get("npc_id") if claim.get("success") else None,
                    "winner_name": winner.get("npc_name") if claim.get("success") else None,
                    "distance": winner.get("distance") if claim.get("success") else None,
                    "candidates": public_candidates,
                    "excluded": excluded,
                    "reason": claim.get("reason"),
                }
            )

    return results


def release_job_claim(task_id, npc=None, force=False):
    wanted = str(task_id or "")
    npc_id = str(getattr(npc.db, "npc_id", "") or "") if npc else ""
    for site in job_sites():
        claims = _site_claims(site)
        existing = claims.get(wanted)
        if not existing:
            continue
        owner_id = str(existing.get("npc_id") or "")
        if not force and npc_id and owner_id != npc_id:
            return None
        claims.pop(wanted, None)
        site.db.job_claims = claims
        return {
            "site": site,
            "task_id": wanted,
            "npc_id": owner_id,
            "npc_name": existing.get("npc_name"),
        }
    return None


def filter_job_candidates_for_claim(npc, candidates):
    """Hide tasks blocked by ownership, shifts, skills, other JOBs or active target danger."""
    refresh_job_claims()
    npc_id = str(getattr(npc.db, "npc_id", "") or "") if npc else ""
    output = []
    for item in list(candidates or []):
        task_id = str(item.get("task_id") or "")
        claim = get_job_claim(task_id) if task_id else None
        if claim and str(claim.get("npc_id") or "") != npc_id:
            continue
        if _owned_other_claim(npc_id, task_id):
            continue

        site = _task_site(task_id)
        if site and danger_blocks_room(site, npc=npc):
            continue

        task = _site_tasks(site).get(task_id) if site else None
        if task and not check_task_skills(npc, task).get("eligible", True):
            continue

        if not claim and task:
            shift = _shift_status(npc)
            if shift.get("scheduled") and not shift.get("active"):
                continue

        candidate = dict(item)
        shift = _shift_status(npc)
        candidate["shift_active"] = bool(shift.get("active"))
        candidate["shift_schedule"] = shift.get("label")
        if claim:
            candidate["claim_npc_id"] = claim.get("npc_id")
            candidate["claim_npc_name"] = claim.get("npc_name")
        output.append(candidate)
    return output


def inspect_job_claims():
    refresh_job_claims()
    rows = []
    for site in job_sites():
        for task_id, claim in _site_claims(site).items():
            rows.append(
                {
                    "site": site.key,
                    "room_id": getattr(site.db, "room_id", None),
                    "task_id": task_id,
                    "npc_id": claim.get("npc_id"),
                    "npc_name": claim.get("npc_name"),
                    "claimed_at": claim.get("claimed_at"),
                    "claim_source": claim.get("claim_source"),
                    "claim_policy": claim.get("claim_policy"),
                    "claim_distance": claim.get("claim_distance"),
                }
            )
    return rows
