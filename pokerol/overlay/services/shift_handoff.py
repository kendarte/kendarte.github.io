from services.actor_registry import find_npc_by_id

from services.job_claims import inspect_job_claims, release_job_claim
from services.job_engine import inspect_job_tasks
from services.world_clock import schedule_is_active, schedule_label, world_clock_state


SHIFT_HANDOFF_BUILD = "0.17.0-shift-handoff"
POLICY_KEEP = "KEEP"
POLICY_RELEASE = "RELEASE"


def _plain_dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _find_npc(npc_id):
    return find_npc_by_id(npc_id)


def _job_schedule(npc):
    if not npc:
        return {}
    schedule = _plain_dict(getattr(npc.db, "job_schedule", {}))
    if schedule:
        return schedule
    job = _plain_dict(getattr(npc.db, "job", {}))
    return _plain_dict(job.get("schedule"))


def _offshift_policy(schedule):
    return str((schedule or {}).get("offshift_claim_policy") or POLICY_KEEP).upper()


def release_offshift_claims():
    """Release active JOB claims whose owner shift ended and authored policy is RELEASE.

    Task progress remains untouched. KEEP is the backward-compatible default.
    """
    state = world_clock_state()
    task_rows = {str(row.get("id")): row for row in inspect_job_tasks()}
    released = []

    for claim in inspect_job_claims():
        task_id = str(claim.get("task_id") or "")
        owner = _find_npc(claim.get("npc_id"))
        if not owner:
            continue

        schedule = _job_schedule(owner)
        if not schedule:
            continue

        policy = _offshift_policy(schedule)
        if policy != POLICY_RELEASE:
            continue
        if schedule_is_active(schedule, state=state):
            continue

        packet = release_job_claim(task_id, npc=owner, force=False)
        if not packet:
            continue

        task = task_rows.get(task_id) or {}
        released.append(
            {
                "status": "RELEASED",
                "reason": "SHIFT_ENDED",
                "task_id": task_id,
                "site": claim.get("site"),
                "npc_id": claim.get("npc_id"),
                "npc_name": claim.get("npc_name"),
                "policy": policy,
                "shift": schedule_label(schedule),
                "day": state.get("day"),
                "time": state.get("time"),
                "work_done": task.get("work_done"),
                "work_required": task.get("work_required"),
                "build": SHIFT_HANDOFF_BUILD,
            }
        )

    return released
