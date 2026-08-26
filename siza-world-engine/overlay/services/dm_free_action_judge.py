import json

from services.action_resolution_engine import ADVENTURE_STATS


DM_JUDGE_BUILD = "dm-0.1-bounded-difficulty-judge"
JUDGMENT_MODES = ("DIRECT", "CONFRONT", "NONE", "UNSUPPORTED")
DIFFICULTY_TIERS = {
    "EASY": 5,
    "STANDARD": 7,
    "HARD": 9,
    "EXTREME": 11,
}
MAX_JUDGMENTS = 3


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


def difficulty_value(tier):
    return DIFFICULTY_TIERS.get(str(tier or "").upper().strip())


def _judgable_steps(adjudication):
    rows = []
    for raw in _plain_list((_plain_dict(adjudication)).get("steps")):
        step = _plain_dict(raw)
        if str(step.get("status") or "") != "NEEDS_JUDGMENT":
            continue
        rows.append({
            "index": int(step.get("index", len(rows))),
            "action_type": str(step.get("action_type") or ""),
            "primary_ref": str(step.get("primary_ref") or ""),
            "secondary_ref": str(step.get("secondary_ref") or ""),
            "desired_effect": str(step.get("desired_effect") or ""),
            "model_resolution_hint": str(step.get("model_resolution_hint") or ""),
            "model_stat_hint": str(step.get("model_stat_hint") or ""),
            "verified_context": _plain_dict(step.get("verified_context")),
        })
    return rows


def build_dm_judge_request(raw_player_input, adjudication, dm_plan=None):
    """Ask the DM to select a bounded resolution profile, never an outcome or world mutation."""
    steps = _judgable_steps(adjudication)
    indexes = [row["index"] for row in steps]
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["judgments"],
        "properties": {
            "judgments": {
                "type": "array",
                "minItems": len(steps),
                "maxItems": len(steps),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "step_index",
                        "mode",
                        "actor_stat",
                        "target_stat",
                        "difficulty_tier",
                        "reason",
                    ],
                    "properties": {
                        "step_index": {"type": "integer", "enum": indexes},
                        "mode": {"type": "string", "enum": list(JUDGMENT_MODES)},
                        "actor_stat": {"type": "string", "enum": [""] + list(ADVENTURE_STATS)},
                        "target_stat": {"type": "string", "enum": [""] + list(ADVENTURE_STATS)},
                        "difficulty_tier": {"type": "string", "enum": [""] + list(DIFFICULTY_TIERS)},
                        "reason": {"type": "string", "maxLength": 240},
                    },
                },
            }
        },
    }
    plan = _plain_dict(dm_plan)
    active_beat = _plain_dict(plan.get("active_beat"))
    system = (
        "Eres el juez mecánico invisible de SIZA. Recibes una acción que YA fue interpretada y cuyas referencias YA fueron verificadas. "
        "Tu trabajo es elegir cómo medir el intento, no decidir el resultado. "
        "NO tires dados, NO escribas SUCCESS/FAILURE, NO narres, NO cambies estado, NO inventes Facts, objetos, NPC, propiedades o modificadores. "
        "Usa DIRECT cuando la dificultad proviene principalmente del obstáculo o ejecución del actor. "
        "Usa CONFRONT cuando un personaje objetivo se opone directamente y existe secondary_ref verificado. "
        "Usa NONE solo cuando el intento es razonablemente automático con el contexto verificado. "
        "Usa UNSUPPORTED si la acción no puede medirse responsablemente con el contexto suministrado. "
        "Para DIRECT elige exactamente un difficulty_tier: EASY, STANDARD, HARD o EXTREME. "
        "Para CONFRONT deja difficulty_tier vacío y elige actor_stat y target_stat. "
        "Los hints del intérprete son sugerencias, nunca obligación. Devuelve únicamente JSON según el schema."
    )
    user = {
        "PLAYER_INPUT": str(raw_player_input or ""),
        "CAMPAIGN_CONTEXT": {
            "campaign_id": plan.get("campaign_id"),
            "active_beat_id": active_beat.get("id"),
            "active_beat_goal": active_beat.get("state_goal"),
        },
        "VERIFIED_STEPS": steps,
        "DIFFICULTY_PRESETS": dict(DIFFICULTY_TIERS),
        "STAT_KEYS": list(ADVENTURE_STATS),
    }
    return {
        "steps": steps,
        "schema": schema,
        "ollama_payload": {
            "stream": False,
            "think": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
            ],
            "options": {"temperature": 0, "num_predict": 320},
        },
        "build": DM_JUDGE_BUILD,
    }


def _extract_model_content(raw_response):
    if isinstance(raw_response, bytes):
        raw_response = raw_response.decode("utf-8", errors="strict")
    outer = json.loads(raw_response) if isinstance(raw_response, str) else _plain_dict(raw_response)
    message = _plain_dict(outer.get("message"))
    content = message.get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("MISSING_MODEL_CONTENT")
    return json.loads(content)


def validate_dm_judgment(content, expected_steps):
    packet = _plain_dict(content)
    errors = []
    if set(packet) != {"judgments"}:
        errors.append("BAD_TOP_LEVEL_KEYS")
    expected = {int(row.get("index")) for row in _plain_list(expected_steps)}
    judgments = _plain_list(packet.get("judgments"))
    if len(judgments) != len(expected):
        errors.append("BAD_JUDGMENT_COUNT")
    seen = set()
    normalized = []
    for raw in judgments:
        row = _plain_dict(raw)
        required = {"step_index", "mode", "actor_stat", "target_stat", "difficulty_tier", "reason"}
        if set(row) != required:
            errors.append("BAD_JUDGMENT_KEYS")
        try:
            index = int(row.get("step_index"))
        except (TypeError, ValueError):
            index = -1
        if index not in expected or index in seen:
            errors.append(f"BAD_STEP_INDEX:{index}")
        seen.add(index)
        mode = str(row.get("mode") or "").upper().strip()
        actor_stat = str(row.get("actor_stat") or "").upper().strip()
        target_stat = str(row.get("target_stat") or "").upper().strip()
        tier = str(row.get("difficulty_tier") or "").upper().strip()
        if mode not in JUDGMENT_MODES:
            errors.append(f"BAD_MODE:{index}")
        if actor_stat and actor_stat not in ADVENTURE_STATS:
            errors.append(f"BAD_ACTOR_STAT:{index}")
        if target_stat and target_stat not in ADVENTURE_STATS:
            errors.append(f"BAD_TARGET_STAT:{index}")
        if tier and tier not in DIFFICULTY_TIERS:
            errors.append(f"BAD_DIFFICULTY_TIER:{index}")
        if mode == "DIRECT":
            if not actor_stat:
                errors.append(f"DIRECT_REQUIRES_ACTOR_STAT:{index}")
            if tier not in DIFFICULTY_TIERS:
                errors.append(f"DIRECT_REQUIRES_TIER:{index}")
            if target_stat:
                errors.append(f"DIRECT_TARGET_STAT_NOT_ALLOWED:{index}")
        elif mode == "CONFRONT":
            if not actor_stat or not target_stat:
                errors.append(f"CONFRONT_REQUIRES_STATS:{index}")
            if tier:
                errors.append(f"CONFRONT_TIER_NOT_ALLOWED:{index}")
        elif mode in {"NONE", "UNSUPPORTED"}:
            if actor_stat or target_stat or tier:
                errors.append(f"{mode}_MUST_NOT_DEFINE_CHECK:{index}")
        normalized.append({
            "step_index": index,
            "mode": mode,
            "actor_stat": actor_stat or None,
            "target_stat": target_stat or None,
            "difficulty_tier": tier or None,
            "difficulty": difficulty_value(tier),
            "reason": str(row.get("reason") or "").strip(),
        })
    if seen != expected:
        errors.append("MISSING_OR_DUPLICATE_STEP_INDEX")
    normalized.sort(key=lambda row: row["step_index"])
    return {
        "valid": not errors,
        "errors": errors,
        "judgments": normalized,
        "build": DM_JUDGE_BUILD,
    }


def parse_dm_judge_response(raw_response, expected_steps, http_status=200):
    if int(http_status or 0) < 200 or int(http_status or 0) >= 300:
        return {"status": "HTTP_ERROR", "accepted": False, "build": DM_JUDGE_BUILD}
    try:
        content = _extract_model_content(raw_response)
    except Exception as exc:
        return {"status": "INVALID_MODEL_JSON", "accepted": False, "error": str(exc), "build": DM_JUDGE_BUILD}
    checked = validate_dm_judgment(content, expected_steps)
    if not checked.get("valid"):
        return {"status": "INVALID_JUDGMENT", "accepted": False, "validation": checked, "build": DM_JUDGE_BUILD}
    return {
        "status": "JUDGED",
        "accepted": True,
        "judgments": checked.get("judgments"),
        "build": DM_JUDGE_BUILD,
    }
