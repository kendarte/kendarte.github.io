from services.conversation_fact_acquisition_engine import resolve_interaction_with_fact_acquisition
from services.interaction_engine import _extract_topic, _find_npc
from services.interaction_proposal_execution_bridge import extract_player_authored_topic
from services.npc_fact_disclosure_engine import (
    _first_shareable_topic_fact,
    _relationship_familiarity,
    _visible_local_npc_by_dbref,
)


NPC_FACT_DISCLOSURE_STATE_BUILD = "0.85.0-holder-local-npc-state-fact-disclosure"
_ALLOWED_DISCLOSURE_KEYS = {"min_familiarity", "npc_state_requirements"}
_STATE_OPERATORS = {"EQ", "NE", "GTE", "LTE", "EXISTS", "NOT_EXISTS"}


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


def _normalize_state_requirements(raw):
    if raw is None or isinstance(raw, (str, bytes)) or hasattr(raw, "items"):
        return [], True
    try:
        rows = list(raw)
    except Exception:
        return [], True
    if not rows:
        return [], True

    output = []
    for raw_row in rows:
        row = _record(raw_row)
        if not row:
            return [], True
        field = str(row.get("field") or "").strip()
        op = str(row.get("op") or "EQ").strip().upper()
        if not field or op not in _STATE_OPERATORS:
            return [], True
        output.append(
            {
                "field": field,
                "op": op,
                "value": row.get("value"),
                "name": str(row.get("name") or field),
            }
        )
    return output, False


def _holder_policy(npc, fact):
    """Prefer holder-local policy; keep inline disclosure only as v0.84 compatibility."""
    fact_id = str((fact or {}).get("id") or "").strip()
    policies = _plain_dict(getattr(npc.db, "fact_disclosure_policies", {})) if npc else {}
    if fact_id and fact_id in policies:
        return _record(policies.get(fact_id)), "NPC_LOCAL_POLICY"
    if fact and "disclosure" in fact:
        return _record(fact.get("disclosure")), "LEGACY_INLINE_FACT"
    return None, None


def _malformed_gate(npc, actor, policy_source=None):
    return {
        "status": "DISCLOSURE_MALFORMED_BLOCKED",
        "allowed": False,
        "restricted": True,
        "familiarity": _relationship_familiarity(npc, actor),
        "required_familiarity": None,
        "state_checks": [],
        "blockers": [{"kind": "MALFORMED_DISCLOSURE"}],
        "policy_source": policy_source,
        "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
    }


def evaluate_fact_disclosure_v85(npc, actor, fact):
    """Evaluate holder-local familiarity/state disclosure policy without exposing Fact contents."""
    disclosure, policy_source = _holder_policy(npc, fact)
    if disclosure is None and policy_source is None:
        return {
            "status": "DISCLOSURE_PUBLIC",
            "allowed": True,
            "restricted": False,
            "familiarity": _relationship_familiarity(npc, actor),
            "required_familiarity": 0,
            "state_checks": [],
            "blockers": [],
            "policy_source": None,
            "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
        }

    if disclosure is None or not disclosure or set(disclosure) - _ALLOWED_DISCLOSURE_KEYS:
        return _malformed_gate(npc, actor, policy_source=policy_source)

    familiarity = _relationship_familiarity(npc, actor)
    has_familiarity = "min_familiarity" in disclosure
    has_state = "npc_state_requirements" in disclosure
    if not has_familiarity and not has_state:
        return _malformed_gate(npc, actor, policy_source=policy_source)

    required_familiarity = 0
    if has_familiarity:
        raw_required = disclosure.get("min_familiarity")
        if isinstance(raw_required, bool):
            return _malformed_gate(npc, actor, policy_source=policy_source)
        try:
            required_familiarity = int(raw_required)
        except (TypeError, ValueError):
            return _malformed_gate(npc, actor, policy_source=policy_source)
        if required_familiarity < 0:
            return _malformed_gate(npc, actor, policy_source=policy_source)

    state_requirements = []
    if has_state:
        state_requirements, malformed = _normalize_state_requirements(
            disclosure.get("npc_state_requirements")
        )
        if malformed:
            return _malformed_gate(npc, actor, policy_source=policy_source)

    blockers = []
    if familiarity < required_familiarity:
        blockers.append(
            {
                "kind": "FAMILIARITY",
                "current": familiarity,
                "required": required_familiarity,
            }
        )

    npc_state = _plain_dict(getattr(npc.db, "state", {})) if npc else {}
    state_checks = []
    for requirement in state_requirements:
        field = requirement.get("field")
        exists = field in npc_state
        current = npc_state.get(field)
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
        }
        state_checks.append(row)
        if not met:
            blockers.append(
                {
                    "kind": "NPC_STATE",
                    "id": field,
                    "name": requirement.get("name"),
                    "op": requirement.get("op"),
                    "current": current,
                    "exists": exists,
                    "required": requirement.get("value"),
                }
            )

    allowed = not blockers
    return {
        "status": "DISCLOSURE_ALLOWED" if allowed else "DISCLOSURE_BLOCKED",
        "allowed": allowed,
        "restricted": bool(required_familiarity > 0 or state_requirements),
        "familiarity": familiarity,
        "required_familiarity": required_familiarity,
        "state_checks": state_checks,
        "blockers": blockers,
        "policy_source": policy_source,
        "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
    }


def preflight_talk_disclosure_v85(actor, raw, *, expected_target_dbref=None):
    """Check the exact known Fact the closed TALK engine would share first."""
    location = getattr(actor, "location", None) if actor else None
    if not actor or not location:
        return {
            "status": "DISCLOSURE_NOT_APPLICABLE",
            "allowed": True,
            "applicable": False,
            "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
        }

    npc = (
        _visible_local_npc_by_dbref(actor, expected_target_dbref)
        if expected_target_dbref is not None
        else _find_npc(location, raw)
    )
    if not npc:
        return {
            "status": "DISCLOSURE_TARGET_UNRESOLVED",
            "allowed": True,
            "applicable": False,
            "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
        }

    topic = str(
        extract_player_authored_topic(raw)
        or _extract_topic(raw, npc=npc)
        or ""
    ).strip()
    if not topic:
        return {
            "status": "DISCLOSURE_NO_TOPIC",
            "allowed": True,
            "applicable": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
        }

    fact = _first_shareable_topic_fact(npc, topic)
    if not fact:
        return {
            "status": "DISCLOSURE_NO_MATCHING_KNOWN_FACT",
            "allowed": True,
            "applicable": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic,
            "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
        }

    gate = evaluate_fact_disclosure_v85(npc, actor, fact)
    packet = {
        **gate,
        "applicable": True,
        "target_dbref": int(npc.id),
        "target_name": str(npc.key),
        "topic": topic,
    }
    if not bool(gate.get("allowed")):
        packet["response_text"] = f"{npc.key} evita dar detalles sobre {topic}."
    return packet


def resolve_interaction_with_disclosure_and_acquisition_v85(
    actor,
    intent,
    *,
    expected_target_dbref=None,
):
    """Block gated Fact disclosure before the existing interaction/transfer engine runs."""
    payload = dict(intent or {})
    if str(payload.get("intent") or "") != "TALK":
        return resolve_interaction_with_fact_acquisition(actor, payload)

    preflight = preflight_talk_disclosure_v85(
        actor,
        payload.get("raw") or "",
        expected_target_dbref=expected_target_dbref,
    )
    if not bool(preflight.get("allowed", True)):
        return {
            "status": "INTERACTION_EXECUTED",
            "executed": True,
            "response_text": str(preflight.get("response_text") or "").strip(),
            "knowledge_acquisition": {
                "status": "DISCLOSURE_BLOCKED",
                "acquired": False,
                "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
            },
            "disclosure": preflight,
            "build": NPC_FACT_DISCLOSURE_STATE_BUILD,
        }

    base = resolve_interaction_with_fact_acquisition(actor, payload)
    return {**dict(base or {}), "disclosure": preflight}
