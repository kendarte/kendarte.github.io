from services.knowledge_context_engine import knowledge_levels
from services.skill_engine import check_task_skills, task_skill_requirements


ACTION_REQUIREMENT_BUILD = "0.42.0-action-requirement-gates"


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

    return {
        "build": ACTION_REQUIREMENT_BUILD,
        "eligible": not blockers,
        "skill_requirements": task_skill_requirements(action or {}),
        "skill_checks": list(skill_check.get("checks") or []),
        "missing_skills": missing_skills,
        "knowledge_requirements": knowledge_requirements(action or {}),
        "knowledge_checks": knowledge_checks,
        "missing_knowledge": missing_knowledge,
        "blockers": blockers,
    }
