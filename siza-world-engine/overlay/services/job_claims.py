from datetime import datetime, timezone

from evennia import search_tag

from services.job_engine import job_sites
from services.npc_simulation import find_path


CLAIM_BUILD = "0.14.0-job-arbitration"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
POLICY_FIRST_SELECTED = "FIRST_SELECTED"
POLICY_NEAREST_REACHABLE = "NEAREST_REACHABLE"


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


def _npc_job_id(npc):
    try:
        job = dict(npc.db.job or {})
    except Exception:
        job = {}
    return str(job.get("id") or "").strip()


def _npc_exists(npc_id):
    wanted = str(npc_id or "").strip()
    if not wanted:
        return False
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == wanted:
            return True
    return False


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


def refresh_job_claims():
    """Remove claims whose task vanished/became inactive or whose owner no longer exists."""
    released = []
    for site in job_sites():
        tasks = _site_tasks(site)
        claims = _site_claims(site)
        changed = False
        for task_id in list(claims.keys()):
            task = tasks.get(task_id)
            claim = claims.get(task_id) or {}
            owner_id = str(claim.get("npc_id") or "")
            invalid_task = (
                task is None
                or not bool(task.get("active", False))
                or str(task.get("status") or "") in {"inactive", "completed"}
            )
            invalid_owner = not _npc_exists(owner_id)
            if invalid_task or invalid_owner:
                released.append(
                    {
                        "task_id": task_id,
                        "site": site.key,
                        "npc_id": owner_id,
                        "npc_name": claim.get("npc_name"),
                        "reason": "TASK_INACTIVE" if invalid_task else "OWNER_MISSING",
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
    """Atomically claim one active task for an eligible NPC.

    Existing ownership by the same NPC is idempotent. Ownership by another NPC
    rejects the claim. The task remains authoritative for work progress.
    """
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
            return {"success": False, "acquired": False, "reason": "TASK_INACTIVE", "site": site}

        required_job = str(task.get("job_id") or "").strip()
        assigned_npc = str(task.get("assigned_npc_id") or "").strip()
        if required_job and required_job != npc_job_id:
            return {"success": False, "acquired": False, "reason": "WRONG_JOB", "site": site}
        if assigned_npc and assigned_npc != npc_id:
            return {"success": False, "acquired": False, "reason": "ASSIGNED_OTHER", "site": site}

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
    """Pre-assign unclaimed tasks whose authored policy is NEAREST_REACHABLE.

    Distance uses the same passable Exit graph as NPC movement. Ties resolve by
    stable npc_id, so list/loop order cannot decide ownership.
    """
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
            for npc in npcs:
                if not _eligible_for_task(npc, task):
                    continue
                path = find_path(npc.location, site)
                if path is None:
                    continue
                npc_id = str(npc.db.npc_id or "")
                candidates.append(
                    {
                        "npc": npc,
                        "npc_id": npc_id,
                        "npc_name": npc.key,
                        "distance": len(path),
                    }
                )

            candidates.sort(key=lambda row: (int(row.get("distance", 0)), str(row.get("npc_id") or "")))
            public_candidates = [
                {
                    "npc_id": row.get("npc_id"),
                    "npc_name": row.get("npc_name"),
                    "distance": row.get("distance"),
                }
                for row in candidates
            ]

            if not candidates:
                results.append(
                    {
                        "status": "NO_ELIGIBLE",
                        "site": site.key,
                        "task_id": task_id,
                        "policy": policy,
                        "winner_id": None,
                        "winner_name": None,
                        "distance": None,
                        "candidates": [],
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
    """Hide tasks claimed by another NPC while retaining own/unclaimed tasks."""
    refresh_job_claims()
    npc_id = str(getattr(npc.db, "npc_id", "") or "") if npc else ""
    output = []
    for item in list(candidates or []):
        task_id = str(item.get("task_id") or "")
        claim = get_job_claim(task_id) if task_id else None
        if claim and str(claim.get("npc_id") or "") != npc_id:
            continue
        candidate = dict(item)
        if claim:
            candidate["claim_npc_id"] = claim.get("npc_id")
            candidate["claim_npc_name"] = claim.get("npc_name")
            candidate["claim_source"] = claim.get("claim_source")
            candidate["claim_policy"] = claim.get("claim_policy")
            candidate["claim_distance"] = claim.get("claim_distance")
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
