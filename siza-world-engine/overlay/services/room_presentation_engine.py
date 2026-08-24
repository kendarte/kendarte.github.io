ROOM_PRESENTATION_BUILD = "0.45.0-state-driven-room-presentation"
STATE_PRESENTATION_OPERATORS = {"EQ", "NE", "GTE", "LTE", "EXISTS", "NOT_EXISTS"}


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


def _normalize_requirement(raw):
    item = _record(raw)
    if not item:
        return None
    field = str(item.get("field") or "").strip()
    if not field:
        return None
    op = str(item.get("op") or "EQ").strip().upper()
    if op not in STATE_PRESENTATION_OPERATORS:
        return None
    return {
        "field": field,
        "op": op,
        "value": item.get("value"),
        "name": str(item.get("name") or field),
    }


def _compare(exists, current, op, expected):
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


def authored_state_presentations(site):
    """Return normalized authored presentation fragments declared on one site."""
    output = []
    if not site:
        return output
    for raw in _plain_list(getattr(site.db, "state_presentations", [])):
        item = _record(raw)
        if not item:
            continue
        presentation_id = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").strip()
        if not presentation_id or not text:
            continue
        normalized_requirements = []
        malformed = False
        for raw_requirement in _plain_list(item.get("state_requirements")):
            normalized = _normalize_requirement(raw_requirement)
            if not normalized:
                malformed = True
                break
            normalized_requirements.append(normalized)
        item["id"] = presentation_id
        item["text"] = text
        item["enabled"] = bool(item.get("enabled", True))
        item["canon_status"] = str(item.get("canon_status") or "prototype")
        item["state_requirements"] = normalized_requirements
        item["valid"] = not malformed
        output.append(item)
    return output


def inspect_state_presentations(site):
    """Evaluate every authored fragment against the site's current persistent world_state."""
    world_state = _plain_dict(getattr(site.db, "world_state", {})) if site else {}
    output = []
    for presentation in authored_state_presentations(site):
        item = dict(presentation)
        checks = []
        for requirement in presentation.get("state_requirements") or []:
            field = requirement.get("field")
            exists = field in world_state
            current = world_state.get(field)
            met = _compare(exists, current, requirement.get("op"), requirement.get("value"))
            checks.append(
                {
                    **requirement,
                    "exists": exists,
                    "current": current,
                    "met": met,
                }
            )
        item["state_checks"] = checks
        item["active"] = bool(
            item.get("enabled", True)
            and item.get("valid", True)
            and all(row.get("met") for row in checks)
        )
        output.append(item)
    return output


def active_state_presentations(site):
    return [row for row in inspect_state_presentations(site) if bool(row.get("active"))]


def render_room_state_text(site):
    """Render only active authored fragments. Empty state adds nothing to the base room appearance."""
    return "\n".join(str(row.get("text") or "").strip() for row in active_state_presentations(site) if str(row.get("text") or "").strip())
