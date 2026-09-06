from services.knowledge_context_engine import knowledge_levels
from services.skill_engine import check_task_skills, task_skill_requirements


ACTION_REQUIREMENT_BUILD = "0.44.0-world-state-gates"
STATE_REQUIREMENT_OPERATORS = {"EQ", "NE", "GTE", "LTE", "EXISTS", "NOT_EXISTS"}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def knowledge_requirements(action):
    output = []
    for raw in _plain_list((action or {}).get("knowledge_requirements")):
        item = _record(raw)
        if not item:
            continue
        key = str(item.get("knowledge_key") or "").strip()
        if not key:
            continue
        try:
            minimum = max(0, int(item.get("min_level", 1) or 1))
        except (TypeError, ValueError):
            minimum = 1
        output.append(
            {
                "knowledge_key": key,
                "min_level": minimum,
                "name": str(item.get("name") or key),
            }
        )
    return output


def state_requirements(action):
    """Explicit room world_state requirements. Missing fields never satisfy comparison operators."""
    output = []
    for raw in _plain_list((action or {}).get("state_requirements")):
        item = _record(raw)
        if not item:
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        op = str(item.get("op") or "EQ").strip().upper()
        if op not in STATE_REQUIREMENT_OPERATORS:
            continue
        output.append(
            {
                "field": field,
                "op": op,
                "value": item.get("value"),
                "name": str(item.get("name") or field),
            }
        )
    return output


def _compare_state(exists, current, op, expected):
    if op == "EXISTS":
        return bool(exists)
    if op == "NOT_EXISTS":
        return not bool(exists)
    if not exists:
        return False
    if op == "EQ":
        return current == expected
    if op == "NE":
        return current != expected
    if op in {"GTE", "LTE"}:
        try:
            left = float(current)
            right = float(expected)
        except (TypeError, ValueError):
            return False
        return left >= right if op == "GTE" else left <= right
    return False


def check_action_requirements(actor, action):
    """Hard eligibility only. Stats are deliberately excluded and belong to action resolution checks."""
    skill_check = check_task_skills(actor, action or {})
    levels = knowledge_levels(actor)

    knowledge_checks = []
    missing_knowledge = []
    for requirement in knowledge_requirements(action or {}):
        level = int(levels.get(requirement.get("knowledge_key"), 0) or 0)
        minimum = int(requirement.get("min_level", 1) or 1)
        row = {
            **requirement,
            "level": level,
            "met": level >= minimum,
        }
        knowledge_checks.append(row)
        if not row.get("met"):
            missing_knowledge.append(row)

    site = getattr(actor, "location", None) if actor else None
    world_state = _plain_dict(getattr(site.db, "world_state", {})) if site else {}
    state_checks = []
    missing_state = []
    for requirement in state_requirements(action or {}):
        field = requirement.get("field")
        exists = field in world_state
        current = world_state.get(field)
        met = _compare_state(
            exists,
            current,
            requirement.get("op"),
            requirement.get("value"),
        )
        row = {
            **requirement,
            "exists": exists,
            "current": current,
            "met": met,
            "site_dbref": int(site.id) if site else None,
            "site_room_id": str(getattr(site.db, "room_id", "") or "") if site else None,
        }
        state_checks.append(row)
        if not met:
            missing_state.append(row)

    missing_skills = list(skill_check.get("missing") or [])
    blockers = []
    for row in missing_skills:
        blockers.append(
            {
                "kind": "SKILL",
                "id": row.get("skill_id"),
                "name": row.get("name"),
                "level": row.get("level"),
                "required": row.get("min_level"),
            }
        )
    for row in missing_knowledge:
        blockers.append(
            {
                "kind": "KNOWLEDGE",
                "id": row.get("knowledge_key"),
                "name": row.get("name"),
                "level": row.get("level"),
                "required": row.get("min_level"),
            }
        )
    for row in missing_state:
        blockers.append(
            {
                "kind": "STATE",
                "id": row.get("field"),
                "name": row.get("name"),
                "op": row.get("op"),
                "current": row.get("current"),
                "exists": row.get("exists"),
                "required": row.get("value"),
                "site_dbref": row.get("site_dbref"),
                "site_room_id": row.get("site_room_id"),
            }
        )

    return {
        "build": ACTION_REQUIREMENT_BUILD,
        "eligible": not blockers,
        "skill_requirements": task_skill_requirements(action or {}),
        "skill_checks": list(skill_check.get("checks") or []),
        "missing_skills": missing_skills,
        "knowledge_requirements": knowledge_requirements(action or {}),
        "knowledge_checks": knowledge_checks,
        "missing_knowledge": missing_knowledge,
        "state_requirements": state_requirements(action or {}),
        "state_checks": state_checks,
        "missing_state": missing_state,
        "blockers": blockers,
    }
