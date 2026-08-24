SKILL_BUILD = "0.31.0-skills-competence"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def skill_records(npc):
    """Return normalized persistent skills keyed by skill id."""
    if not npc:
        return {}
    output = {}
    for skill_id, raw in _plain_dict(getattr(npc.db, "skills", {})).items():
        if hasattr(raw, "items"):
            item = _record(raw) or {}
            try:
                level = max(0, int(item.get("level", 0) or 0))
            except (TypeError, ValueError):
                level = 0
            item["level"] = level
            item.setdefault("name", str(skill_id))
            item.setdefault("canon_status", "prototype")
        else:
            try:
                level = max(0, int(raw or 0))
            except (TypeError, ValueError):
                level = 0
            item = {
                "level": level,
                "name": str(skill_id),
                "canon_status": "prototype",
            }
        output[str(skill_id)] = item
    return output


def skill_level(npc, skill_id):
    return int((skill_records(npc).get(str(skill_id)) or {}).get("level", 0) or 0)


def task_skill_requirements(task):
    output = []
    for raw in _plain_list((task or {}).get("skill_requirements")):
        item = _record(raw)
        if not item:
            continue
        skill_id = str(item.get("skill_id") or "").strip()
        if not skill_id:
            continue
        try:
            minimum = max(0, int(item.get("min_level", 1) or 1))
        except (TypeError, ValueError):
            minimum = 1
        output.append(
            {
                "skill_id": skill_id,
                "min_level": minimum,
                "name": str(item.get("name") or skill_id),
            }
        )
    return output


def check_task_skills(npc, task):
    """Hard eligibility gate: all authored skill requirements must be met."""
    requirements = task_skill_requirements(task)
    checks = []
    missing = []
    for requirement in requirements:
        actual = skill_level(npc, requirement.get("skill_id"))
        minimum = int(requirement.get("min_level", 1) or 1)
        row = {
            **requirement,
            "level": actual,
            "met": actual >= minimum,
        }
        checks.append(row)
        if not row["met"]:
            missing.append(row)
    return {
        "eligible": not missing,
        "requirements": requirements,
        "checks": checks,
        "missing": missing,
    }


def set_skill_level(npc, skill_id, level, name=None, canon_status=None):
    if not npc:
        return None
    key = str(skill_id or "").strip()
    if not key:
        return None
    try:
        new_level = max(0, int(level))
    except (TypeError, ValueError):
        return None

    records = skill_records(npc)
    current = dict(records.get(key) or {})
    before = int(current.get("level", 0) or 0)
    current["level"] = new_level
    current["name"] = str(name or current.get("name") or key)
    current["canon_status"] = str(canon_status or current.get("canon_status") or "prototype")
    records[key] = current
    npc.db.skills = records
    return {
        "skill_id": key,
        "name": current.get("name"),
        "before": before,
        "after": new_level,
        "canon_status": current.get("canon_status"),
    }


def inspect_skills(npc):
    return {
        "build": SKILL_BUILD,
        "npc": npc.key if npc else None,
        "npc_id": str(getattr(npc.db, "npc_id", "") or "") if npc else None,
        "skills": skill_records(npc),
    }
