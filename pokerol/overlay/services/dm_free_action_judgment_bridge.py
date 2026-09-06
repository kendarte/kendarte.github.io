from copy import deepcopy


DM_JUDGMENT_BRIDGE_BUILD = "dm-0.1-judgment-to-execution-plan"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def apply_dm_judgment(adjudication, judge_result):
    """Attach bounded judgment to already verified steps without creating outcomes."""
    adjudicated = _plain_dict(adjudication)
    judged = _plain_dict(judge_result)
    if adjudicated.get("status") != "NEEDS_JUDGMENT":
        return {
            "status": "ADJUDICATION_NOT_WAITING_FOR_JUDGMENT",
            "admissible": False,
            "build": DM_JUDGMENT_BRIDGE_BUILD,
        }
    if judged.get("status") != "JUDGED" or judged.get("accepted") is not True:
        return {
            "status": "JUDGMENT_NOT_ACCEPTED",
            "admissible": False,
            "build": DM_JUDGMENT_BRIDGE_BUILD,
        }

    judgment_map = {
        int(row.get("step_index")): _plain_dict(row)
        for row in _plain_list(judged.get("judgments"))
    }
    output_steps = []
    errors = []
    for raw in _plain_list(adjudicated.get("steps")):
        step = deepcopy(_plain_dict(raw))
        if step.get("status") != "NEEDS_JUDGMENT":
            output_steps.append(step)
            continue
        index = int(step.get("index", -1))
        judgment = judgment_map.get(index)
        if not judgment:
            errors.append(f"MISSING_JUDGMENT:{index}")
            output_steps.append(step)
            continue
        mode = str(judgment.get("mode") or "").upper().strip()
        if mode == "UNSUPPORTED":
            step.update({
                "status": "REJECTED",
                "admissible": False,
                "reason": "DM_JUDGE_UNSUPPORTED",
                "judgment": judgment,
            })
        elif mode == "NONE":
            step.update({
                "status": "ADMISSIBLE",
                "admissible": True,
                "executor": "DM_AUTO",
                "judgment": judgment,
            })
        elif mode in {"DIRECT", "CONFRONT"}:
            step.update({
                "status": "ADMISSIBLE",
                "admissible": True,
                "executor": "DM_CHECK",
                "judgment": judgment,
            })
        else:
            errors.append(f"INVALID_JUDGMENT_MODE:{index}:{mode}")
        output_steps.append(step)

    if errors:
        status = "INVALID_JUDGMENT_MERGE"
    elif all(row.get("admissible") is True for row in output_steps):
        status = "ADMISSIBLE"
    else:
        status = "NOT_ADMISSIBLE"

    return {
        **adjudicated,
        "status": status,
        "admissible": status == "ADMISSIBLE",
        "steps": output_steps,
        "judgment_errors": errors,
        "judge_build": judged.get("build"),
        "authority": {
            **_plain_dict(adjudicated.get("authority")),
            "dm_selected_resolution_profile": True,
            "dm_selected_outcome": False,
            "dm_mutated_world": False,
        },
        "build": DM_JUDGMENT_BRIDGE_BUILD,
    }
