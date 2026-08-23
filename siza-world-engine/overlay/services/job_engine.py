from datetime import datetime, timezone

from evennia import search_tag


JOB_SITE_TAG = "siza_job_site"
JOB_SITE_CATEGORY = "siza_job"
JOB_ENGINE_BUILD = "0.8.0-worksite-rules"


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


def _npc_job_id(npc):
    job = _plain_dict(getattr(npc.db, "job", {}))
    return str(job.get("id") or "").strip()


def job_sites():
    """Return persistent Rooms/objects explicitly tagged as authored job-task sources."""
    return list(search_tag(JOB_SITE_TAG, category=JOB_SITE_CATEGORY))


def _task_dict(raw):
    try:
        return {str(key): value for key, value in raw.items()}
    except Exception:
        return None


def _rule_dict(raw):
    try:
        return {str(key): value for key, value in raw.items()}
    except Exception:
        return None


def _coerce_number(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        if "." in text:
            return float(text)
        return int(text)
    except (TypeError, ValueError):
        return value


def _compare(actual, operator, expected):
    actual = _coerce_number(actual)
    expected = _coerce_number(expected)
    op = str(operator or "eq").lower()
    try:
        if op in {"lt", "<"}:
            return actual < expected
        if op in {"lte", "<=", "le"}:
            return actual <= expected
        if op in {"gt", ">"}:
            return actual > expected
        if op in {"gte", ">=", "ge"}:
            return actual >= expected
        if op in {"ne", "!=", "neq"}:
            return actual != expected
        return actual == expected
    except TypeError:
        return False


def _find_rule_for_task(site, task_id):
    for raw in _plain_list(site.db.job_rules):
        rule = _rule_dict(raw)
        if rule and str(rule.get("task_id")) == str(task_id):
            return rule
    return None


def _apply_completion_effects(site, task_id):
    rule = _find_rule_for_task(site, task_id)
    if not rule:
        return []

    state = _plain_dict(site.db.work_state)
    applied = []
    for raw_effect in _plain_list(rule.get("completion_effects", [])):
        effect = _rule_dict(raw_effect)
        if not effect:
            continue
        field = str(effect.get("field") or "").strip()
        if not field:
            continue
        operation = str(effect.get("op") or "set").lower()
        value = _coerce_number(effect.get("value"))
        before = state.get(field)

        if operation == "add":
            try:
                state[field] = _coerce_number(before or 0) + value
            except TypeError:
                continue
        elif operation == "subtract":
            try:
                state[field] = _coerce_number(before or 0) - value
            except TypeError:
                continue
        else:
            state[field] = value

        applied.append(
            {
                "field": field,
                "op": operation,
                "before": before,
                "after": state.get(field),
            }
        )

    if applied:
        site.db.work_state = state
    return applied


def refresh_world_job_rules():
    """Evaluate persistent worksite state and activate/deactivate derived JOB tasks."""
    results = []
    for site in job_sites():
        state = _plain_dict(site.db.work_state)
        tasks = _plain_list(site.db.job_tasks)
        rules = _plain_list(site.db.job_rules)
        changed = False

        task_map = {}
        for index, raw in enumerate(tasks):
            task = _task_dict(raw)
            if task is not None and task.get("id"):
                task_map[str(task.get("id"))] = (index, task)

        for raw_rule in rules:
            rule = _rule_dict(raw_rule)
            if not rule or not bool(rule.get("enabled", True)):
                continue

            task_id = str(rule.get("task_id") or "").strip()
            field = str(rule.get("field") or "").strip()
            if not task_id or not field or task_id not in task_map:
                continue

            index, task = task_map[task_id]
            actual = state.get(field)
            expected = rule.get("value")
            condition_met = _compare(actual, rule.get("op"), expected)
            was_active = bool(task.get("active", False))
            previous_status = str(task.get("status") or "inactive")

            if condition_met:
                task["active"] = True
                task["status"] = "available"
                task["rule_id"] = rule.get("id")
                if not was_active:
                    task.pop("completed_by_npc_id", None)
                    task.pop("completed_by_name", None)
                    task.pop("completed_at", None)
                    task.pop("completion_effects_applied", None)
            else:
                task["active"] = False
                # Preserve completed as history until the condition becomes true again.
                if previous_status != "completed":
                    task["status"] = "inactive"

            if bool(task.get("active")) != was_active or str(task.get("status")) != previous_status:
                changed = True

            tasks[index] = task
            task_map[task_id] = (index, task)
            results.append(
                {
                    "site": site.key,
                    "room_id": getattr(site.db, "room_id", None),
                    "rule_id": rule.get("id"),
                    "task_id": task_id,
                    "field": field,
                    "actual": actual,
                    "op": rule.get("op"),
                    "expected": expected,
                    "condition_met": condition_met,
                    "task_active": bool(task.get("active")),
                    "task_status": task.get("status"),
                }
            )

        if changed:
            site.db.job_tasks = tasks

    return results


def collect_job_candidates(npc, default_priority=60):
    """Derive JOB goals from persistent tasks stored in the world, not on the NPC."""
    if not npc:
        return []

    npc_job_id = _npc_job_id(npc)
    npc_id = str(npc.db.npc_id or "")
    if not npc_job_id:
        return []

    candidates = []
    for site in job_sites():
        for raw in _plain_list(site.db.job_tasks):
            task = _task_dict(raw)
            if not task or not bool(task.get("active", False)):
                continue

            required_job = str(task.get("job_id") or "").strip()
            assigned_npc = str(task.get("assigned_npc_id") or "").strip()
            if required_job and required_job != npc_job_id:
                continue
            if assigned_npc and assigned_npc != npc_id:
                continue

            try:
                priority = int(task.get("priority", default_priority))
            except (TypeError, ValueError):
                priority = int(default_priority)

            task_id = str(task.get("id") or "").strip()
            if not task_id:
                continue

            candidates.append(
                {
                    "id": f"JOB:{task_id}",
                    "task_id": task_id,
                    "type": "JOB",
                    "priority": priority,
                    "active": True,
                    "target_room_id": getattr(site.db, "room_id", None),
                    "target_room_key": site.key,
                    "activity": str(task.get("activity") or "atendiendo una tarea de trabajo"),
                    "one_shot": bool(task.get("one_shot", True)),
                    "source": "WORLD_JOB",
                    "job_id": required_job or npc_job_id,
                    "job_site_dbid": site.id,
                    "task_status": str(task.get("status") or "available"),
                    "canon_status": str(task.get("canon_status") or "prototype"),
                }
            )

    return candidates


def _rewrite_task(site, task_id, updater):
    tasks = _plain_list(site.db.job_tasks)
    output = []
    changed = False
    for raw in tasks:
        task = _task_dict(raw)
        if task is None:
            output.append(raw)
            continue
        if str(task.get("id")) == str(task_id):
            task = updater(task)
            changed = True
        output.append(task)
    if changed:
        site.db.job_tasks = output
    return changed


def complete_job_task(npc, task_id):
    """Complete a world task and apply its authored effects back to the worksite state."""
    timestamp = datetime.now(timezone.utc).isoformat()
    for site in job_sites():
        matched = [
            task for task in (_task_dict(raw) for raw in _plain_list(site.db.job_tasks))
            if task and str(task.get("id")) == str(task_id)
        ]
        if not matched:
            continue

        effects = _apply_completion_effects(site, task_id)

        def updater(task):
            task["active"] = False
            task["status"] = "completed"
            task["completed_by_npc_id"] = str(npc.db.npc_id or "")
            task["completed_by_name"] = npc.key
            task["completed_at"] = timestamp
            task["completion_effects_applied"] = effects
            return task

        if _rewrite_task(site, task_id, updater):
            return site
    return None


def set_job_task_active(task_id, active):
    """Admin/debug switch for tasks without a producer; producer-owned tasks may be overwritten next refresh."""
    desired = bool(active)
    for site in job_sites():
        def updater(task):
            task["active"] = desired
            task["status"] = "available" if desired else "inactive"
            if desired:
                task.pop("completed_by_npc_id", None)
                task.pop("completed_by_name", None)
                task.pop("completed_at", None)
            return task

        if _rewrite_task(site, task_id, updater):
            return site
    return None


def set_work_state(site, field, value):
    state = _plain_dict(site.db.work_state)
    state[str(field)] = _coerce_number(value)
    site.db.work_state = state
    return state


def inspect_worksites():
    rows = []
    for site in job_sites():
        rows.append(
            {
                "site": site,
                "name": site.key,
                "room_id": getattr(site.db, "room_id", None),
                "work_state": _plain_dict(site.db.work_state),
                "job_rules": [
                    rule for rule in (_rule_dict(raw) for raw in _plain_list(site.db.job_rules)) if rule
                ],
            }
        )
    return rows


def inspect_job_tasks(npc=None):
    """Return persistent job tasks with eligibility metadata for debugging."""
    npc_job_id = _npc_job_id(npc) if npc else ""
    npc_id = str(npc.db.npc_id or "") if npc else ""
    rows = []
    for site in job_sites():
        for raw in _plain_list(site.db.job_tasks):
            task = _task_dict(raw)
            if task is None:
                continue
            required_job = str(task.get("job_id") or "")
            assigned_npc = str(task.get("assigned_npc_id") or "")
            eligible = True
            if npc:
                eligible = (not required_job or required_job == npc_job_id) and (
                    not assigned_npc or assigned_npc == npc_id
                )
            rows.append(
                {
                    "site": site.key,
                    "room_id": getattr(site.db, "room_id", None),
                    "id": task.get("id"),
                    "job_id": required_job,
                    "rule_id": task.get("rule_id"),
                    "active": bool(task.get("active", False)),
                    "status": task.get("status"),
                    "priority": task.get("priority"),
                    "activity": task.get("activity"),
                    "eligible": bool(eligible),
                    "completion_effects_applied": task.get("completion_effects_applied"),
                }
            )
    return rows
