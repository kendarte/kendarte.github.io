from services.fact_share_rule_engine import _cancel_rule_obligations, fact_share_rules
from services.faction_engine import faction_definition, membership_authority, npc_memberships
from services.knowledge_context_engine import knowledge_facts


FACTION_FACT_SHARE_POLICY_BUILD = "0.96.0-inherited-faction-fact-share-policies"
FACTION_FACT_TYPE_POLICY_BUILD = "0.97.0-fact-type-inherited-faction-policies"
FACTION_FACT_SEVERITY_POLICY_BUILD = "0.98.0-severity-filtered-faction-fact-policies"
POLICY_FIELD = "fact_share_policies"
MANAGED_FIELD = "managed_by"
RULE_SCOPE = "FACTION_INHERITED"


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


def _is_managed_rule(rule):
    return str((rule or {}).get(MANAGED_FIELD) or "") == FACTION_FACT_SHARE_POLICY_BUILD


def _normalize_fact_type(value):
    return str(value or "").strip().upper()


def _severity_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _severity_filter(policy):
    raw_min = (policy or {}).get("min_severity")
    raw_max = (policy or {}).get("max_severity")
    if raw_min is None and raw_max is None:
        return None, None, None
    minimum = _severity_value(raw_min) if raw_min is not None else None
    maximum = _severity_value(raw_max) if raw_max is not None else None
    if (raw_min is not None and minimum is None) or (raw_max is not None and maximum is None):
        return None, None, "BAD_SEVERITY_FILTER"
    if minimum is not None and maximum is not None and minimum > maximum:
        return None, None, "BAD_SEVERITY_FILTER"
    return minimum, maximum, None


def _severity_matches(value, minimum, maximum):
    severity = _severity_value(value)
    if severity is None:
        return False, None
    if minimum is not None and severity < minimum:
        return False, severity
    if maximum is not None and severity > maximum:
        return False, severity
    return True, severity


def _effective_rule_id(faction_id, policy_id, fact_id=None, selector_mode="EXACT"):
    base = f"FACTION_POLICY:{str(faction_id)}:{str(policy_id)}"
    if str(selector_mode or "EXACT").upper() == "TYPE" and fact_id:
        return f"{base}:FACT:{str(fact_id)}"
    return base


def _managed_rule(
    policy,
    membership,
    faction_id,
    policy_id,
    fact_id,
    selector_mode,
    authored_fact_type=None,
    fact_severity=None,
    min_severity=None,
    max_severity=None,
):
    item = dict(policy)
    item["id"] = _effective_rule_id(
        faction_id,
        policy_id,
        fact_id=fact_id,
        selector_mode=selector_mode,
    )
    item["fact_id"] = str(fact_id)
    item["authored_rule_id"] = policy_id
    item["inherited_from_faction_id"] = faction_id
    item["rule_scope"] = RULE_SCOPE
    item["fact_selector_mode"] = str(selector_mode).upper()
    item["authored_fact_type"] = authored_fact_type
    item["fact_severity"] = fact_severity
    item["authored_min_severity"] = min_severity
    item["authored_max_severity"] = max_severity
    item[MANAGED_FIELD] = FACTION_FACT_SHARE_POLICY_BUILD
    item["fact_type_policy_build"] = FACTION_FACT_TYPE_POLICY_BUILD
    item["fact_severity_policy_build"] = FACTION_FACT_SEVERITY_POLICY_BUILD
    item.setdefault("target_mode", "FACTION")
    if str(item.get("target_mode") or "").upper() == "FACTION" and not str(item.get("faction_id") or "").strip():
        item["faction_id"] = faction_id
    item["source_membership_authority"] = membership_authority(
        npc=membership.get("_npc"),
        faction_id=faction_id,
        active_only=True,
    ) if membership.get("_npc") else None
    item.pop("_npc", None)
    return item


def _policy_candidates(npc):
    candidates = []
    skipped = []
    stored_facts = sorted(
        (dict(row) for row in knowledge_facts(npc)),
        key=lambda row: str(row.get("id") or ""),
    )
    memberships = sorted(
        npc_memberships(npc, active_only=True),
        key=lambda row: str(row.get("faction_id") or ""),
    )
    for membership in memberships:
        faction_id = str(membership.get("faction_id") or "").strip()
        if not faction_id:
            continue
        faction = faction_definition(faction_id) or {}
        if faction and not bool(faction.get("active", True)):
            skipped.append({"faction_id": faction_id, "reason": "FACTION_INACTIVE"})
            continue
        policies = sorted(
            (_record(raw) for raw in _plain_list(faction.get(POLICY_FIELD))),
            key=lambda row: str((row or {}).get("id") or ""),
        )
        for policy in policies:
            if policy is None or not bool(policy.get("enabled", False)):
                continue
            policy_id = str(policy.get("id") or "").strip()
            authored_fact_id = str(policy.get("fact_id") or "").strip()
            authored_fact_type = _normalize_fact_type(policy.get("fact_type"))
            min_severity, max_severity, severity_error = _severity_filter(policy)
            has_severity_filter = (policy.get("min_severity") is not None or policy.get("max_severity") is not None)
            if not policy_id:
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": None,
                        "reason": "MALFORMED_FACTION_POLICY",
                    }
                )
                continue
            if bool(authored_fact_id) == bool(authored_fact_type):
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": policy_id,
                        "reason": "AMBIGUOUS_FACT_SELECTOR" if authored_fact_id and authored_fact_type else "MALFORMED_FACTION_POLICY",
                    }
                )
                continue
            if severity_error:
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": policy_id,
                        "reason": severity_error,
                    }
                )
                continue
            if authored_fact_id and has_severity_filter:
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": policy_id,
                        "reason": "SEVERITY_FILTER_REQUIRES_FACT_TYPE",
                    }
                )
                continue

            membership_context = dict(membership)
            membership_context["_npc"] = npc
            if authored_fact_id:
                candidates.append(
                    _managed_rule(
                        policy,
                        membership_context,
                        faction_id,
                        policy_id,
                        authored_fact_id,
                        "EXACT",
                    )
                )
                continue

            type_matches = [
                fact
                for fact in stored_facts
                if _normalize_fact_type(fact.get("fact_type")) == authored_fact_type
                and str(fact.get("id") or "").strip()
            ]
            if not type_matches:
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": policy_id,
                        "reason": "NO_FACTS_MATCH_TYPE",
                        "fact_type": authored_fact_type,
                    }
                )
                continue

            matches = []
            invalid_severity_fact_ids = []
            for fact in type_matches:
                fact_id = str(fact.get("id") or "").strip()
                if not has_severity_filter:
                    matches.append((fact, _severity_value(fact.get("severity"))))
                    continue
                matches_filter, severity = _severity_matches(
                    fact.get("severity"),
                    min_severity,
                    max_severity,
                )
                if severity is None:
                    invalid_severity_fact_ids.append(fact_id)
                    continue
                if matches_filter:
                    matches.append((fact, severity))

            for fact_id in invalid_severity_fact_ids:
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": policy_id,
                        "reason": "FACT_SEVERITY_MISSING_OR_INVALID",
                        "fact_type": authored_fact_type,
                        "fact_id": fact_id,
                    }
                )
            if not matches:
                skipped.append(
                    {
                        "faction_id": faction_id,
                        "policy_id": policy_id,
                        "reason": "NO_FACTS_MATCH_SEVERITY" if has_severity_filter else "NO_FACTS_MATCH_TYPE",
                        "fact_type": authored_fact_type,
                        "min_severity": min_severity,
                        "max_severity": max_severity,
                    }
                )
                continue

            for fact, fact_severity in matches:
                candidates.append(
                    _managed_rule(
                        policy,
                        membership_context,
                        faction_id,
                        policy_id,
                        str(fact.get("id") or "").strip(),
                        "TYPE",
                        authored_fact_type=authored_fact_type,
                        fact_severity=fact_severity,
                        min_severity=min_severity,
                        max_severity=max_severity,
                    )
                )
    return candidates, skipped


def sync_faction_fact_share_policies(npc):
    if not npc:
        return {
            "status": "NO_NPC",
            "build": FACTION_FACT_SHARE_POLICY_BUILD,
            "fact_type_policy_build": FACTION_FACT_TYPE_POLICY_BUILD,
            "fact_severity_policy_build": FACTION_FACT_SEVERITY_POLICY_BUILD,
            "inherited": [],
            "removed": [],
            "conflicts": [],
            "suppressed_by_local": [],
        }

    current = fact_share_rules(npc)
    local_rules = [dict(row) for row in current if not _is_managed_rule(row)]
    current_managed = {
        str(row.get("id") or ""): dict(row)
        for row in current
        if _is_managed_rule(row) and str(row.get("id") or "")
    }
    local_fact_ids = {
        str(row.get("fact_id") or "").strip()
        for row in local_rules
        if str(row.get("fact_id") or "").strip()
    }

    candidates, skipped = _policy_candidates(npc)
    suppressed = []
    eligible = []
    for rule in candidates:
        fact_id = str(rule.get("fact_id") or "").strip()
        if fact_id in local_fact_ids:
            suppressed.append(
                {
                    "rule_id": rule.get("id"),
                    "authored_rule_id": rule.get("authored_rule_id"),
                    "faction_id": rule.get("inherited_from_faction_id"),
                    "fact_id": fact_id,
                    "fact_selector_mode": rule.get("fact_selector_mode"),
                    "fact_type": rule.get("authored_fact_type"),
                    "fact_severity": rule.get("fact_severity"),
                    "reason": "LOCAL_RULE_OVERRIDE",
                }
            )
            continue
        eligible.append(rule)

    by_fact = {}
    for rule in eligible:
        by_fact.setdefault(str(rule.get("fact_id") or ""), []).append(rule)

    conflicts = []
    desired = []
    for fact_id, rows in sorted(by_fact.items()):
        if len(rows) > 1:
            conflicts.append(
                {
                    "fact_id": fact_id,
                    "reason": "MULTIPLE_INHERITED_POLICIES_FOR_FACT",
                    "rule_ids": sorted(str(row.get("id") or "") for row in rows),
                    "faction_ids": sorted(str(row.get("inherited_from_faction_id") or "") for row in rows),
                    "selector_modes": sorted(str(row.get("fact_selector_mode") or "") for row in rows),
                    "severity_ranges": sorted(
                        (
                            row.get("authored_min_severity"),
                            row.get("authored_max_severity"),
                        )
                        for row in rows
                    ),
                }
            )
            continue
        desired.append(dict(rows[0]))

    desired.sort(key=lambda row: str(row.get("id") or ""))
    desired_ids = {str(row.get("id") or "") for row in desired}
    removed = []
    for rule_id, old_rule in sorted(current_managed.items()):
        if rule_id in desired_ids:
            continue
        cancelled = _cancel_rule_obligations(
            npc,
            rule_id,
            reason="FACTION_POLICY_NO_LONGER_INHERITED",
        )
        removed.append(
            {
                "rule_id": rule_id,
                "authored_rule_id": old_rule.get("authored_rule_id"),
                "faction_id": old_rule.get("inherited_from_faction_id"),
                "fact_id": old_rule.get("fact_id"),
                "fact_selector_mode": old_rule.get("fact_selector_mode"),
                "fact_type": old_rule.get("authored_fact_type"),
                "fact_severity": old_rule.get("fact_severity"),
                "min_severity": old_rule.get("authored_min_severity"),
                "max_severity": old_rule.get("authored_max_severity"),
                "cancelled_obligations": cancelled,
            }
        )

    new_rules = local_rules + desired
    changed = new_rules != current
    if changed:
        npc.db.fact_share_rules = new_rules

    return {
        "status": "SYNCED" if changed or removed else "NO_CHANGE",
        "build": FACTION_FACT_SHARE_POLICY_BUILD,
        "fact_type_policy_build": FACTION_FACT_TYPE_POLICY_BUILD,
        "fact_severity_policy_build": FACTION_FACT_SEVERITY_POLICY_BUILD,
        "inherited": [
            {
                "rule_id": row.get("id"),
                "authored_rule_id": row.get("authored_rule_id"),
                "faction_id": row.get("inherited_from_faction_id"),
                "fact_id": row.get("fact_id"),
                "fact_selector_mode": row.get("fact_selector_mode"),
                "fact_type": row.get("authored_fact_type"),
                "fact_severity": row.get("fact_severity"),
                "min_severity": row.get("authored_min_severity"),
                "max_severity": row.get("authored_max_severity"),
                "target_mode": row.get("target_mode"),
                "target_faction_id": row.get("faction_id"),
            }
            for row in desired
        ],
        "removed": removed,
        "conflicts": conflicts,
        "suppressed_by_local": suppressed,
        "skipped": skipped,
        "local_rule_count": len(local_rules),
        "managed_rule_count": len(desired),
    }
