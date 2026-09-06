from services.fact_share_rule_engine import (
    FACT_SHARE_RULE_BUILD,
    _cancel_rule_obligations,
    fact_share_rules,
    refresh_fact_share_obligations as _refresh_fact_share_obligations,
)
from services.knowledge_fact_engine import find_knowledge_fact


FACT_SHARE_HOLDER_ACQUISITION_BUILD = "1.00.0-holder-acquisition-aware-fact-sharing"


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


def _npc_id(npc):
    return str(getattr(npc.db, "npc_id", "") or "").strip() if npc else ""


def _parse_holder_acquisition(rule):
    value = str((rule or {}).get("holder_acquisition") or "ANY").strip().upper()
    if value not in {"ANY", "NONTRANSFERRED", "LOCAL_TRANSFER"}:
        return None, "BAD_HOLDER_ACQUISITION"
    return value, None


def fact_holder_acquisition(npc, fact):
    """Classify how this holder has acquired this stored Fact without rewriting origin provenance."""
    if not npc or not fact:
        return "NONTRANSFERRED"
    npc_id = _npc_id(npc)
    try:
        dbref = int(npc.id)
    except Exception:
        dbref = None

    for raw in _plain_list((fact or {}).get("transfer_history")):
        row = _record(raw) or {}
        if str(row.get("mode") or "").upper() != "DIRECT_LOCAL":
            continue
        target_npc_id = str(row.get("target_npc_id") or "").strip()
        try:
            target_dbref = int(row.get("target_dbref")) if row.get("target_dbref") is not None else None
        except (TypeError, ValueError):
            target_dbref = None
        if (npc_id and target_npc_id == npc_id) or (dbref is not None and target_dbref == dbref):
            return "LOCAL_TRANSFER"
    return "NONTRANSFERRED"


def _holder_gate(rule, npc):
    requested, error = _parse_holder_acquisition(rule)
    rule_id = str((rule or {}).get("id") or "").strip()
    fact_id = str((rule or {}).get("fact_id") or "").strip()
    if error:
        return {
            "eligible": False,
            "rule_id": rule_id,
            "fact_id": fact_id,
            "requested": None,
            "actual": None,
            "reason": error,
        }
    if requested == "ANY":
        return {
            "eligible": True,
            "rule_id": rule_id,
            "fact_id": fact_id,
            "requested": requested,
            "actual": None,
            "reason": "ANY",
        }

    fact = find_knowledge_fact(npc, fact_id) if fact_id else None
    if not fact:
        # Missing Fact remains the historical v0.91 source-awareness authority.
        return {
            "eligible": True,
            "rule_id": rule_id,
            "fact_id": fact_id,
            "requested": requested,
            "actual": None,
            "reason": "FACT_NOT_STORED_DEFER_TO_SOURCE_AWARENESS",
        }

    actual = fact_holder_acquisition(npc, fact)
    return {
        "eligible": actual == requested,
        "rule_id": rule_id,
        "fact_id": fact_id,
        "requested": requested,
        "actual": actual,
        "reason": "MATCH" if actual == requested else "HOLDER_ACQUISITION_MISMATCH",
    }


def refresh_holder_aware_fact_share_obligations(npc):
    """Apply holder acquisition policy before the historical SHARE_FACT refresh."""
    if not npc:
        packet = dict(_refresh_fact_share_obligations(npc) or {})
        packet["holder_acquisition_build"] = FACT_SHARE_HOLDER_ACQUISITION_BUILD
        packet["holder_acquisition_skipped"] = []
        return packet

    original_rules = [dict(row) for row in fact_share_rules(npc)]
    eligible_rules = []
    skipped = []

    for rule in original_rules:
        gate = _holder_gate(rule, npc)
        if gate.get("eligible"):
            eligible_rules.append(dict(rule))
            continue
        reason = str(gate.get("reason") or "HOLDER_ACQUISITION_MISMATCH")
        cancelled = _cancel_rule_obligations(npc, gate.get("rule_id"), reason=reason)
        skipped.append(
            {
                "rule_id": gate.get("rule_id"),
                "fact_id": gate.get("fact_id"),
                "reason": reason,
                "requested": gate.get("requested"),
                "actual": gate.get("actual"),
                "cancelled_obligations": cancelled,
            }
        )

    if len(eligible_rules) == len(original_rules):
        packet = dict(_refresh_fact_share_obligations(npc) or {})
    else:
        try:
            npc.db.fact_share_rules = eligible_rules
            packet = dict(_refresh_fact_share_obligations(npc) or {})
        finally:
            npc.db.fact_share_rules = original_rules

    packet["holder_acquisition_build"] = FACT_SHARE_HOLDER_ACQUISITION_BUILD
    packet["holder_acquisition_skipped"] = skipped
    packet["underlying_fact_share_build"] = FACT_SHARE_RULE_BUILD
    return packet
