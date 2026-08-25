from datetime import datetime, timezone

from evennia import search_tag

from services.faction_engine import has_active_membership
from services.knowledge_context_engine import fact_knowledge_state
from services.knowledge_fact_engine import find_knowledge_fact
from services.relationship_engine import create_fact_share_obligation


FACT_SHARE_RULE_BUILD = "0.89.0-fact-driven-social-share-rules"
FACT_SHARE_TARGET_AWARENESS_BUILD = "0.90.0-target-aware-fact-share-pruning"
FACT_SHARE_SOURCE_AWARENESS_BUILD = "0.91.0-source-aware-fact-share-cancellation"
FACT_SHARE_TARGET_MODE_BUILD = "0.92.0-faction-targeted-fact-share-rules"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"


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


def _all_npcs():
    output = []
    for npc in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if not bool(getattr(npc.db, "is_npc", False)):
            continue
        npc_id = str(getattr(npc.db, "npc_id", "") or "").strip()
        if npc_id:
            output.append(npc)
    output.sort(key=lambda npc: str(getattr(npc.db, "npc_id", "") or ""))
    return output


def _npc_id(npc):
    return str(getattr(npc.db, "npc_id", "") or "").strip() if npc else ""


def _npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    if not wanted:
        return None
    for npc in _all_npcs():
        if _npc_id(npc) == wanted:
            return npc
    return None


def _completed_obligation_exists(npc, target_id, obligation_id):
    relationships = _plain_dict(getattr(npc.db, "relationships", {})) if npc else {}
    relation = _plain_dict(relationships.get(str(target_id), {}))
    for raw in _plain_list(relation.get("obligations")):
        item = _record(raw) or {}
        if str(item.get("id") or "") != str(obligation_id):
            continue
        return not bool(item.get("active", False)) and str(item.get("status") or "").lower() == "completed"
    return False


def _target_knows_fact(target, fact_id):
    fact = find_knowledge_fact(target, fact_id) if target else None
    if not fact:
        return False
    return bool(fact_knowledge_state(target, fact).get("known"))


def _update_obligation_state(npc, target_id, obligation_id, status, reason, reason_key):
    if not npc:
        return False
    relationships = _plain_dict(getattr(npc.db, "relationships", {}))
    relation = _plain_dict(relationships.get(str(target_id), {}))
    obligations = []
    changed = False
    now = datetime.now(timezone.utc).isoformat()

    for raw in _plain_list(relation.get("obligations")):
        item = _record(raw)
        if item is None:
            continue
        if (
            str(item.get("id") or "") == str(obligation_id)
            and str(item.get("kind") or "").upper() == "SHARE_FACT"
            and bool(item.get("active", False))
        ):
            item["active"] = False
            item["status"] = str(status)
            item[f"{status}_at"] = now
            item[str(reason_key)] = str(reason)
            if status == "completed":
                item["completed_without_contact"] = True
            changed = True
        obligations.append(item)

    if changed:
        relation["obligations"] = obligations
        relationships[str(target_id)] = relation
        npc.db.relationships = relationships
    return changed


def _retire_pending_fact_share_obligation(npc, target_id, obligation_id):
    return _update_obligation_state(
        npc,
        target_id,
        obligation_id,
        "completed",
        "TARGET_ALREADY_KNOWS_FACT",
        "completion_reason",
    )


def _cancel_pending_fact_share_obligation(npc, target_id, obligation_id, reason="SOURCE_NO_LONGER_KNOWS_FACT"):
    return _update_obligation_state(
        npc,
        target_id,
        obligation_id,
        "cancelled",
        reason,
        "cancellation_reason",
    )


def _obligation_sources(npc):
    return _plain_dict(getattr(npc.db, "fact_share_obligation_sources", {})) if npc else {}


def _remember_obligation_source(npc, obligation_id, rule, target_id):
    if not npc or not obligation_id:
        return
    rows = _obligation_sources(npc)
    mode = str((rule or {}).get("target_mode") or "EXPLICIT").upper()
    rows[str(obligation_id)] = {
        "rule_id": str((rule or {}).get("id") or ""),
        "fact_id": str((rule or {}).get("fact_id") or ""),
        "target_npc_id": str(target_id or ""),
        "target_mode": mode,
        "faction_id": str((rule or {}).get("faction_id") or "") if mode == "FACTION" else "",
        "build": FACT_SHARE_TARGET_MODE_BUILD,
    }
    npc.db.fact_share_obligation_sources = rows


def _mapped_rule_obligations(npc, rule_id):
    wanted = str(rule_id or "")
    output = []
    for obligation_id, raw in _obligation_sources(npc).items():
        row = _record(raw) or {}
        if str(row.get("rule_id") or "") != wanted:
            continue
        target_id = str(row.get("target_npc_id") or "").strip()
        if target_id:
            output.append((str(obligation_id), target_id, row))
    return output


def _resolve_rule_targets(npc, rule):
    mode = str((rule or {}).get("target_mode") or "EXPLICIT").upper()
    source_id = _npc_id(npc)
    if mode == "EXPLICIT":
        target_id = str((rule or {}).get("target_npc_id") or "").strip()
        if not target_id:
            return mode, [], "TARGET_NOT_CONFIGURED"
        target = _npc_by_id(target_id)
        return mode, [target] if target else [], None if target else "TARGET_NOT_FOUND"

    if mode == "FACTION":
        faction_id = str((rule or {}).get("faction_id") or "").strip()
        if not faction_id:
            return mode, [], "FACTION_NOT_CONFIGURED"
        targets = [
            candidate
            for candidate in _all_npcs()
            if _npc_id(candidate) != source_id and has_active_membership(candidate, faction_id)
        ]
        return mode, targets, None

    return mode, [], "UNSUPPORTED_TARGET_MODE"


def fact_share_rules(npc):
    if not npc:
        return []
    output = []
    for raw in _plain_list(getattr(npc.db, "fact_share_rules", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def upsert_fact_share_rule(npc, rule):
    if not npc:
        return {"status": "NO_NPC", "build": FACT_SHARE_RULE_BUILD}
    item = _record(rule)
    rule_id = str((item or {}).get("id") or "").strip()
    if not rule_id:
        return {"status": "BAD_RULE", "build": FACT_SHARE_RULE_BUILD}
    item.setdefault("target_mode", "EXPLICIT")
    rows = []
    replaced = False
    for current in fact_share_rules(npc):
        if str(current.get("id") or "") == rule_id:
            rows.append(dict(item))
            replaced = True
        else:
            rows.append(current)
    if not replaced:
        rows.append(dict(item))
    npc.db.fact_share_rules = rows
    return {
        "status": "UPDATED" if replaced else "CREATED",
        "rule_id": rule_id,
        "build": FACT_SHARE_RULE_BUILD,
        "target_awareness_build": FACT_SHARE_TARGET_AWARENESS_BUILD,
        "source_awareness_build": FACT_SHARE_SOURCE_AWARENESS_BUILD,
        "target_mode_build": FACT_SHARE_TARGET_MODE_BUILD,
    }


def _cancel_rule_obligations(npc, rule_id, reason, only_targets=None):
    allowed = {str(value) for value in (only_targets or []) if value} if only_targets is not None else None
    changed = []
    for obligation_id, target_id, _row in _mapped_rule_obligations(npc, rule_id):
        if allowed is not None and target_id not in allowed:
            continue
        if _cancel_pending_fact_share_obligation(npc, target_id, obligation_id, reason=reason):
            changed.append({"obligation_id": obligation_id, "target_npc_id": target_id})
    return changed


def refresh_fact_share_obligations(npc):
    """Materialize useful SHARE_FACT obligations while source knows, target qualifies and target remains ignorant."""
    if not npc:
        return {
            "status": "NO_NPC",
            "build": FACT_SHARE_RULE_BUILD,
            "target_awareness_build": FACT_SHARE_TARGET_AWARENESS_BUILD,
            "source_awareness_build": FACT_SHARE_SOURCE_AWARENESS_BUILD,
            "target_mode_build": FACT_SHARE_TARGET_MODE_BUILD,
            "materialized": [],
        }

    materialized = []
    skipped = []
    for rule in fact_share_rules(npc):
        if not bool(rule.get("enabled", False)):
            continue
        rule_id = str(rule.get("id") or "").strip()
        fact_id = str(rule.get("fact_id") or "").strip()
        if not rule_id or not fact_id:
            skipped.append({"rule_id": rule_id, "reason": "MALFORMED_RULE"})
            continue

        fact = find_knowledge_fact(npc, fact_id)
        if not fact or not bool(fact_knowledge_state(npc, fact).get("known")):
            cancelled = _cancel_rule_obligations(
                npc,
                rule_id,
                reason="SOURCE_NO_LONGER_KNOWS_FACT",
            )
            # Compatibility for old explicit obligations created before v0.92 source indexing.
            explicit_target = str(rule.get("target_npc_id") or "").strip()
            explicit_obligation = f"SHARE-FACT-{explicit_target}-{fact_id}" if explicit_target else ""
            legacy_cancelled = False
            if explicit_target and explicit_obligation:
                legacy_cancelled = _cancel_pending_fact_share_obligation(
                    npc,
                    explicit_target,
                    explicit_obligation,
                )
            skipped.append(
                {
                    "rule_id": rule_id,
                    "reason": "SOURCE_DOES_NOT_KNOW_FACT",
                    "cancelled_pending": bool(cancelled or legacy_cancelled),
                    "cancelled_obligations": cancelled,
                }
            )
            continue

        mode, targets, target_error = _resolve_rule_targets(npc, rule)
        if target_error:
            skipped.append(
                {
                    "rule_id": rule_id,
                    "reason": target_error,
                    "target_mode": mode,
                }
            )
            continue

        current_target_ids = {_npc_id(target) for target in targets if _npc_id(target)}
        stale_targets = [
            target_id
            for _obligation_id, target_id, _row in _mapped_rule_obligations(npc, rule_id)
            if target_id not in current_target_ids
        ]
        stale_cancelled = _cancel_rule_obligations(
            npc,
            rule_id,
            reason="TARGET_NO_LONGER_MATCHES_RULE",
            only_targets=stale_targets,
        )
        for row in stale_cancelled:
            skipped.append(
                {
                    "rule_id": rule_id,
                    "reason": "TARGET_NO_LONGER_MATCHES_RULE",
                    "target_mode": mode,
                    **row,
                }
            )

        if not targets:
            skipped.append(
                {
                    "rule_id": rule_id,
                    "reason": "NO_ELIGIBLE_TARGETS",
                    "target_mode": mode,
                }
            )
            continue

        for target in targets:
            target_id = _npc_id(target)
            obligation_id = f"SHARE-FACT-{target_id}-{fact_id}"

            if bool(rule.get("one_shot", True)) and _completed_obligation_exists(npc, target_id, obligation_id):
                skipped.append(
                    {
                        "rule_id": rule_id,
                        "reason": "ALREADY_COMPLETED",
                        "obligation_id": obligation_id,
                        "target_npc_id": target_id,
                        "target_mode": mode,
                    }
                )
                continue

            if _target_knows_fact(target, fact_id):
                retired = _retire_pending_fact_share_obligation(npc, target_id, obligation_id)
                skipped.append(
                    {
                        "rule_id": rule_id,
                        "reason": "TARGET_ALREADY_KNOWS_FACT",
                        "obligation_id": obligation_id,
                        "target_npc_id": target_id,
                        "target_mode": mode,
                        "retired_pending": bool(retired),
                    }
                )
                continue

            packet = create_fact_share_obligation(
                npc,
                target,
                fact_id,
                priority=rule.get("priority", 50),
            )
            if packet.get("success"):
                _remember_obligation_source(npc, packet.get("obligation_id"), rule, target_id)
                materialized.append(
                    {
                        "rule_id": rule_id,
                        "obligation_id": packet.get("obligation_id"),
                        "fact_id": fact_id,
                        "target_npc_id": target_id,
                        "target_mode": mode,
                        "faction_id": str(rule.get("faction_id") or "") if mode == "FACTION" else None,
                        "created": bool(packet.get("created")),
                    }
                )
            else:
                skipped.append(
                    {
                        "rule_id": rule_id,
                        "reason": packet.get("reason") or "CREATE_FAILED",
                        "target_npc_id": target_id,
                        "target_mode": mode,
                    }
                )

    return {
        "status": "MATERIALIZED" if materialized else "NO_CHANGE",
        "materialized": materialized,
        "skipped": skipped,
        "build": FACT_SHARE_RULE_BUILD,
        "target_awareness_build": FACT_SHARE_TARGET_AWARENESS_BUILD,
        "source_awareness_build": FACT_SHARE_SOURCE_AWARENESS_BUILD,
        "target_mode_build": FACT_SHARE_TARGET_MODE_BUILD,
    }
