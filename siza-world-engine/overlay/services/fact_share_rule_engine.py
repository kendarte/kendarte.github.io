from datetime import datetime, timezone

from evennia import search_tag

from services.faction_engine import has_active_membership, membership_authority
from services.knowledge_context_engine import fact_knowledge_state
from services.knowledge_fact_engine import find_knowledge_fact
from services.npc_simulation import find_path
from services.relationship_engine import create_fact_share_obligation


FACT_SHARE_RULE_BUILD = "0.89.0-fact-driven-social-share-rules"
FACT_SHARE_TARGET_AWARENESS_BUILD = "0.90.0-target-aware-fact-share-pruning"
FACT_SHARE_SOURCE_AWARENESS_BUILD = "0.91.0-source-aware-fact-share-cancellation"
FACT_SHARE_TARGET_MODE_BUILD = "0.92.0-faction-targeted-fact-share-rules"
FACT_SHARE_AUTHORITY_FILTER_BUILD = "0.93.0-faction-authority-filtered-fact-share-rules"
FACT_SHARE_RECIPIENT_SELECTION_BUILD = "0.94.0-nearest-limited-faction-fact-share-selection"
FACT_SHARE_NEED_AWARE_SELECTION_BUILD = "0.95.0-need-aware-nearest-fact-share-selection"
FACT_SHARE_AUTHORITY_RELATION_BUILD = "0.99.0-upchain-authority-relative-fact-sharing"
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
    return _update_obligation_state(npc, target_id, obligation_id, "completed", "TARGET_ALREADY_KNOWS_FACT", "completion_reason")


def _cancel_pending_fact_share_obligation(npc, target_id, obligation_id, reason="SOURCE_NO_LONGER_KNOWS_FACT"):
    return _update_obligation_state(npc, target_id, obligation_id, "cancelled", reason, "cancellation_reason")


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
        "min_authority": (rule or {}).get("min_authority") if mode == "FACTION" else None,
        "authority_relation": str((rule or {}).get("authority_relation") or "ANY").upper() if mode == "FACTION" else None,
        "selection": str((rule or {}).get("selection") or "ALL").upper() if mode == "FACTION" else None,
        "max_targets": (rule or {}).get("max_targets") if mode == "FACTION" else None,
        "build": FACT_SHARE_TARGET_MODE_BUILD,
        "authority_filter_build": FACT_SHARE_AUTHORITY_FILTER_BUILD,
        "recipient_selection_build": FACT_SHARE_RECIPIENT_SELECTION_BUILD,
        "need_aware_selection_build": FACT_SHARE_NEED_AWARE_SELECTION_BUILD,
        "authority_relation_build": FACT_SHARE_AUTHORITY_RELATION_BUILD,
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


def _parse_min_authority(rule):
    raw = (rule or {}).get("min_authority")
    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return None, "BAD_MIN_AUTHORITY"
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, "BAD_MIN_AUTHORITY"
    if value < 0 or value > 1000:
        return None, "BAD_MIN_AUTHORITY"
    return value, None


def _parse_authority_relation(rule):
    value = str((rule or {}).get("authority_relation") or "ANY").strip().upper()
    if value not in {"ANY", "HIGHER_THAN_SOURCE"}:
        return None, "BAD_AUTHORITY_RELATION"
    return value, None


def _parse_selection(rule):
    value = str((rule or {}).get("selection") or "ALL").strip().upper()
    if value not in {"ALL", "NEAREST"}:
        return None, "BAD_SELECTION"
    return value, None


def _parse_max_targets(rule, selection):
    raw = (rule or {}).get("max_targets")
    if selection == "ALL":
        if raw is None:
            return None, None
        return None, "BAD_MAX_TARGETS"
    if raw is None:
        return 1, None
    if isinstance(raw, bool):
        return None, "BAD_MAX_TARGETS"
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, "BAD_MAX_TARGETS"
    if value < 1 or value > 100:
        return None, "BAD_MAX_TARGETS"
    return value, None


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
        min_authority, authority_error = _parse_min_authority(rule)
        if authority_error:
            return mode, [], authority_error
        authority_relation, relation_error = _parse_authority_relation(rule)
        if relation_error:
            return mode, [], relation_error
        source_authority = None
        if authority_relation == "HIGHER_THAN_SOURCE":
            source_authority = membership_authority(npc, faction_id, active_only=True)
            if source_authority is None:
                return mode, [], "SOURCE_AUTHORITY_UNAVAILABLE"
            source_authority = int(source_authority)
        targets = []
        for candidate in _all_npcs():
            if _npc_id(candidate) == source_id or not has_active_membership(candidate, faction_id):
                continue
            authority = None
            if min_authority is not None or authority_relation == "HIGHER_THAN_SOURCE":
                authority = membership_authority(candidate, faction_id, active_only=True)
                if authority is None:
                    continue
                authority = int(authority)
            if min_authority is not None and authority < min_authority:
                continue
            if authority_relation == "HIGHER_THAN_SOURCE" and authority <= source_authority:
                continue
            targets.append(candidate)
        return mode, targets, None
    return mode, [], "UNSUPPORTED_TARGET_MODE"


def _select_rule_targets(npc, rule, mode, targets, fact_id=None):
    empty_meta = {"selection": None, "max_targets": None, "reachable": {}, "already_known": {}, "already_completed": []}
    if mode != "FACTION":
        return list(targets or []), empty_meta, None
    selection, selection_error = _parse_selection(rule)
    if selection_error:
        return [], empty_meta, selection_error
    max_targets, max_error = _parse_max_targets(rule, selection)
    if max_error:
        meta = dict(empty_meta)
        meta["selection"] = selection
        return [], meta, max_error
    if selection == "ALL":
        return list(targets or []), {"selection": "ALL", "max_targets": None, "reachable": {}, "already_known": {}, "already_completed": []}, None

    one_shot = bool(rule.get("one_shot", True))
    need_targets = []
    already_known = {}
    already_completed = []
    for target in list(targets or []):
        target_id = _npc_id(target)
        if not target_id:
            continue
        obligation_id = f"SHARE-FACT-{target_id}-{fact_id}" if fact_id else ""
        if fact_id and one_shot and obligation_id and _completed_obligation_exists(npc, target_id, obligation_id):
            already_completed.append(target_id)
            continue
        if fact_id and _target_knows_fact(target, fact_id):
            retired = _retire_pending_fact_share_obligation(npc, target_id, obligation_id) if obligation_id else False
            already_known[target_id] = {"retired_pending": bool(retired)}
            continue
        need_targets.append(target)

    faction_id = str((rule or {}).get("faction_id") or "").strip()
    ranked = []
    reachable = {}
    for target in need_targets:
        target_id = _npc_id(target)
        if not target_id or not npc.location or not target.location:
            continue
        path = [] if npc.location == target.location else find_path(npc.location, target.location)
        if path is None:
            continue
        authority = membership_authority(target, faction_id, active_only=True)
        authority_value = int(authority) if authority is not None else -1
        path_length = len(path)
        reachable[target_id] = {"path_length": path_length, "authority": authority_value}
        ranked.append((path_length, -authority_value, target_id, target))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = [item[3] for item in ranked[: int(max_targets or 1)]]
    return selected, {
        "selection": "NEAREST",
        "max_targets": int(max_targets or 1),
        "reachable": reachable,
        "already_known": already_known,
        "already_completed": already_completed,
    }, None


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
        "authority_filter_build": FACT_SHARE_AUTHORITY_FILTER_BUILD,
        "recipient_selection_build": FACT_SHARE_RECIPIENT_SELECTION_BUILD,
        "need_aware_selection_build": FACT_SHARE_NEED_AWARE_SELECTION_BUILD,
        "authority_relation_build": FACT_SHARE_AUTHORITY_RELATION_BUILD,
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
            "status": "NO_NPC", "build": FACT_SHARE_RULE_BUILD,
            "target_awareness_build": FACT_SHARE_TARGET_AWARENESS_BUILD,
            "source_awareness_build": FACT_SHARE_SOURCE_AWARENESS_BUILD,
            "target_mode_build": FACT_SHARE_TARGET_MODE_BUILD,
            "authority_filter_build": FACT_SHARE_AUTHORITY_FILTER_BUILD,
            "recipient_selection_build": FACT_SHARE_RECIPIENT_SELECTION_BUILD,
            "need_aware_selection_build": FACT_SHARE_NEED_AWARE_SELECTION_BUILD,
            "authority_relation_build": FACT_SHARE_AUTHORITY_RELATION_BUILD,
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
            cancelled = _cancel_rule_obligations(npc, rule_id, reason="SOURCE_NO_LONGER_KNOWS_FACT")
            mode = str(rule.get("target_mode") or "EXPLICIT").upper()
            explicit_target = str(rule.get("target_npc_id") or "").strip() if mode == "EXPLICIT" else ""
            explicit_obligation = f"SHARE-FACT-{explicit_target}-{fact_id}" if explicit_target else ""
            legacy_cancelled = _cancel_pending_fact_share_obligation(npc, explicit_target, explicit_obligation) if explicit_target and explicit_obligation else False
            compatibility_obligation_id = explicit_obligation or (str(cancelled[0].get("obligation_id") or "") if len(cancelled) == 1 else "")
            skipped.append({
                "rule_id": rule_id, "reason": "SOURCE_DOES_NOT_KNOW_FACT",
                "obligation_id": compatibility_obligation_id or None,
                "cancelled_pending": bool(cancelled or legacy_cancelled),
                "cancelled_obligations": cancelled, "target_mode": mode,
            })
            continue

        mode, eligible_targets, target_error = _resolve_rule_targets(npc, rule)
        selection_meta = {"selection": None, "max_targets": None, "reachable": {}, "already_known": {}, "already_completed": []}
        if not target_error:
            targets, selection_meta, target_error = _select_rule_targets(npc, rule, mode, eligible_targets, fact_id=fact_id)
        else:
            targets = []

        if target_error:
            invalid_cancelled = []
            if target_error in {"BAD_MIN_AUTHORITY", "BAD_AUTHORITY_RELATION", "SOURCE_AUTHORITY_UNAVAILABLE", "BAD_SELECTION", "BAD_MAX_TARGETS"}:
                invalid_cancelled = _cancel_rule_obligations(npc, rule_id, reason=target_error)
            skipped.append({
                "rule_id": rule_id, "reason": target_error, "target_mode": mode,
                "selection": selection_meta.get("selection"), "max_targets": selection_meta.get("max_targets"),
                "cancelled_obligations": invalid_cancelled,
            })
            continue

        for target_id, known_meta in dict(selection_meta.get("already_known") or {}).items():
            skipped.append({
                "rule_id": rule_id, "reason": "TARGET_ALREADY_KNOWS_FACT",
                "obligation_id": f"SHARE-FACT-{target_id}-{fact_id}", "target_npc_id": target_id,
                "target_mode": mode, "selection": selection_meta.get("selection"),
                "retired_pending": bool((known_meta or {}).get("retired_pending")), "preselection_pruned": True,
            })
        for target_id in list(selection_meta.get("already_completed") or []):
            skipped.append({
                "rule_id": rule_id, "reason": "ALREADY_COMPLETED",
                "obligation_id": f"SHARE-FACT-{target_id}-{fact_id}", "target_npc_id": target_id,
                "target_mode": mode, "selection": selection_meta.get("selection"), "preselection_pruned": True,
            })

        current_target_ids = {_npc_id(target) for target in targets if _npc_id(target)}
        current_target_ids.update(str(value) for value in dict(selection_meta.get("already_known") or {}).keys())
        current_target_ids.update(str(value) for value in list(selection_meta.get("already_completed") or []))
        stale_targets = [
            target_id for _obligation_id, target_id, _row in _mapped_rule_obligations(npc, rule_id)
            if target_id not in current_target_ids
        ]
        stale_cancelled = _cancel_rule_obligations(npc, rule_id, reason="TARGET_NO_LONGER_MATCHES_RULE", only_targets=stale_targets)
        for row in stale_cancelled:
            skipped.append({
                "rule_id": rule_id, "reason": "TARGET_NO_LONGER_MATCHES_RULE",
                "target_mode": mode, "selection": selection_meta.get("selection"), **row,
            })

        if not targets:
            skipped.append({
                "rule_id": rule_id, "reason": "NO_ELIGIBLE_TARGETS", "target_mode": mode,
                "selection": selection_meta.get("selection"), "max_targets": selection_meta.get("max_targets"),
            })
            continue

        for target in targets:
            target_id = _npc_id(target)
            obligation_id = f"SHARE-FACT-{target_id}-{fact_id}"
            if bool(rule.get("one_shot", True)) and _completed_obligation_exists(npc, target_id, obligation_id):
                skipped.append({"rule_id": rule_id, "reason": "ALREADY_COMPLETED", "obligation_id": obligation_id, "target_npc_id": target_id, "target_mode": mode})
                continue
            if _target_knows_fact(target, fact_id):
                retired = _retire_pending_fact_share_obligation(npc, target_id, obligation_id)
                skipped.append({
                    "rule_id": rule_id, "reason": "TARGET_ALREADY_KNOWS_FACT", "obligation_id": obligation_id,
                    "target_npc_id": target_id, "target_mode": mode, "retired_pending": bool(retired),
                })
                continue
            packet = create_fact_share_obligation(npc, target, fact_id, priority=rule.get("priority", 50))
            if packet.get("success"):
                _remember_obligation_source(npc, packet.get("obligation_id"), rule, target_id)
                reachable_meta = dict(selection_meta.get("reachable") or {}).get(target_id) or {}
                materialized.append({
                    "rule_id": rule_id, "obligation_id": packet.get("obligation_id"), "fact_id": fact_id,
                    "target_npc_id": target_id, "target_mode": mode,
                    "faction_id": str(rule.get("faction_id") or "") if mode == "FACTION" else None,
                    "min_authority": rule.get("min_authority") if mode == "FACTION" else None,
                    "authority_relation": str(rule.get("authority_relation") or "ANY").upper() if mode == "FACTION" else None,
                    "selection": selection_meta.get("selection"), "max_targets": selection_meta.get("max_targets"),
                    "path_length": reachable_meta.get("path_length"), "created": bool(packet.get("created")),
                })
            else:
                skipped.append({"rule_id": rule_id, "reason": packet.get("reason") or "CREATE_FAILED", "target_npc_id": target_id, "target_mode": mode})

    return {
        "status": "MATERIALIZED" if materialized else "NO_CHANGE",
        "materialized": materialized, "skipped": skipped, "build": FACT_SHARE_RULE_BUILD,
        "target_awareness_build": FACT_SHARE_TARGET_AWARENESS_BUILD,
        "source_awareness_build": FACT_SHARE_SOURCE_AWARENESS_BUILD,
        "target_mode_build": FACT_SHARE_TARGET_MODE_BUILD,
        "authority_filter_build": FACT_SHARE_AUTHORITY_FILTER_BUILD,
        "recipient_selection_build": FACT_SHARE_RECIPIENT_SELECTION_BUILD,
        "need_aware_selection_build": FACT_SHARE_NEED_AWARE_SELECTION_BUILD,
        "authority_relation_build": FACT_SHARE_AUTHORITY_RELATION_BUILD,
    }
