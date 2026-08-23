from datetime import datetime, timezone

from evennia import search_tag


JOB_SITE_TAG = "siza_job_site"
JOB_SITE_CATEGORY = "siza_job"


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
    """Mark the persistent world task completed when the NPC reaches its job target."""
    timestamp = datetime.now(timezone.utc).isoformat()
    for site in job_sites():
        def updater(task):
            task["active"] = False
            task["status"] = "completed"
            task["completed_by_npc_id"] = str(npc.db.npc_id or "")
            task["completed_by_name"] = npc.key
            task["completed_at"] = timestamp
            return task

        if _rewrite_task(site, task_id, updater):
            return site
    return None


def set_job_task_active(task_id, active):
    """Admin/debug switch for an already-authored world task."""
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
                    "active": bool(task.get("active", False)),
                    "status": task.get("status"),
                    "priority": task.get("priority"),
                    "activity": task.get("activity"),
                    "eligible": bool(eligible),
                }
            )
    return rows
