from evennia import Command, search_object, search_tag

from commands.world_input_v74_commands import _clone
from services.fact_share_rule_engine import refresh_fact_share_obligations
from services.faction_fact_share_policy_engine import (
    FACTION_FACT_SEVERITY_POLICY_BUILD,
    FACTION_FACT_SHARE_POLICY_BUILD,
    FACTION_FACT_TYPE_POLICY_BUILD,
    sync_faction_fact_share_policies,
)
from services.faction_engine import get_faction_registry, upsert_faction, upsert_membership
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import upsert_knowledge_fact
from services.relationship_engine import collect_relationship_candidates, inspect_relationships
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V098_VALIDATION_BUILD = "0.98.0-severity-filtered-faction-fact-policies"
TEST_FACTION_ID = "TEST-V098-DARSENA-ESCALATION"
FACT_TYPE = "SECURITY_INCIDENT"
FACT_LOW = "FACT-V098-SECURITY-LOW-001"
FACT_HIGH = "FACT-V098-SECURITY-HIGH-001"
FACT_MISSING = "FACT-V098-SECURITY-MISSING-001"
KEY_LOW = "V098_SECURITY_LOW"
KEY_HIGH = "V098_SECURITY_HIGH"
KEY_MISSING = "V098_SECURITY_MISSING"
UNFILTERED_POLICY_ID = "POLICY-V098-ALL-SECURITY-001"
LOW_POLICY_ID = "POLICY-V098-LOW-SECURITY-001"
HIGH_POLICY_ID = "POLICY-V098-HIGH-SECURITY-001"
GOOD_EXACT_POLICY_ID = "POLICY-V098-EXACT-GOOD-001"
BAD_EXACT_POLICY_ID = "POLICY-V098-EXACT-BAD-001"
WORKER_B_NPC_ID = "TEST-NPC-KAL-DAR-WORKER-B"
CALLE_ID = "CAR-KAL-DAR-004"
PLAZA_ID = "CAR-KAL-DAR-003"


def _npc_by_id(npc_id):
    for npc in search_tag("kalnaj_pilot_v03_entities", category="siza_entity"):
        if str(getattr(npc.db, "npc_id", "") or "").strip() == str(npc_id or "").strip():
            return npc
    return None


def _room(key, room_id):
    for obj in search_object(key):
        if str(getattr(obj.db, "room_id", "") or "") == str(room_id):
            return obj
    return None


def _type_policy(policy_id, minimum=None, maximum=None, min_authority=500):
    row = {
        "id": policy_id,
        "enabled": True,
        "canon_status": "prototype",
        "fact_type": FACT_TYPE,
        "target_mode": "FACTION",
        "min_authority": min_authority,
        "selection": "NEAREST",
        "max_targets": 1,
        "priority": 948,
        "one_shot": True,
    }
    if minimum is not None:
        row["min_severity"] = minimum
    if maximum is not None:
        row["max_severity"] = maximum
    return row


def _exact_policy(policy_id, fact_id, minimum_marker=None):
    row = {
        "id": policy_id,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": fact_id,
        "target_mode": "FACTION",
        "min_authority": 500,
        "selection": "NEAREST",
        "max_targets": 1,
        "priority": 948,
        "one_shot": True,
    }
    if minimum_marker is not None:
        row["min_severity"] = minimum_marker
    return row


def _faction(policies):
    return {
        "id": TEST_FACTION_ID,
        "name": TEST_FACTION_ID,
        "active": True,
        "canon_status": "prototype",
        "fact_share_policies": list(policies),
    }


def _seed_fact(npc, site, fact_id, key, severity_marker):
    fact = {
        "id": fact_id,
        "knowledge_key": key,
        "required_level": 1,
        "fact_type": FACT_TYPE,
        "topic": f"validator {fact_id}",
        "text": f"Validator Fact {fact_id}.",
        "canon_status": "prototype",
        "source": {
            "kind": "VALIDATOR_SEED",
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
        },
        "learned_by": {"mode": "VALIDATOR"},
    }
    if severity_marker is not None:
        fact["severity"] = severity_marker
    upsert_knowledge_fact(npc, fact)
    set_knowledge_level(npc, key, 1)


def _managed_rules(npc):
    return [
        dict(row)
        for row in list(getattr(npc.db, "fact_share_rules", []) or [])
        if str((row or {}).get("managed_by") or "") == FACTION_FACT_SHARE_POLICY_BUILD
    ]


def _rule_for(npc, fact_id):
    return next((row for row in _managed_rules(npc) if str(row.get("fact_id") or "") == str(fact_id)), None)


def _obligation(source, target_id, fact_id):
    wanted = f"SHARE-FACT-{target_id}-{fact_id}"
    for relation in inspect_relationships(source):
        if str(relation.get("target_npc_id") or "") != str(target_id):
            continue
        for row in list(relation.get("obligations") or []):
            if str((row or {}).get("id") or "") == wanted:
                return dict(row)
    return None


def _candidate_pairs(source):
    return {
        (
            str(row.get("relationship_target_npc_id") or ""),
            str(row.get("fact_id") or ""),
        )
        for row in collect_relationship_candidates(source)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
    }


class CmdSizaValidateV98(Command):
    key = "siza-validate-v98"
    aliases = ["validate-v98"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        informant = install.get("informant") if install.get("success") else None
        mara = install.get("mara") if install.get("success") else None
        site = install.get("site") if install.get("success") else None
        worker = _npc_by_id(WORKER_B_NPC_ID)
        calle = _room("Calle de Servicio", CALLE_ID)
        plaza = _room("Plaza de Recepcion", PLAZA_ID)
        registry = get_faction_registry(create=True)
        if not informant or not mara or not worker or not site or not calle or not plaza or registry is None:
            self.caller.msg("[V0.98 VALIDATION] FAIL | persistent context missing")
            return

        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        worker_id = str(getattr(worker.db, "npc_id", "") or "").strip()
        low_mara_oid = f"SHARE-FACT-{mara_id}-{FACT_LOW}"
        low_worker_oid = f"SHARE-FACT-{worker_id}-{FACT_LOW}"

        original = {
            "registry_factions": _clone(getattr(registry.db, "factions", {})),
            "informant_location": informant.location,
            "mara_location": mara.location,
            "worker_location": worker.location,
            "informant_knowledge": _clone(getattr(informant.db, "knowledge", {})),
            "informant_facts": _clone(getattr(informant.db, "knowledge_facts", [])),
            "mara_knowledge": _clone(getattr(mara.db, "knowledge", {})),
            "mara_facts": _clone(getattr(mara.db, "knowledge_facts", [])),
            "worker_knowledge": _clone(getattr(worker.db, "knowledge", {})),
            "worker_facts": _clone(getattr(worker.db, "knowledge_facts", [])),
            "informant_relationships": _clone(getattr(informant.db, "relationships", {})),
            "informant_rules": _clone(getattr(informant.db, "fact_share_rules", [])),
            "informant_sources": _clone(getattr(informant.db, "fact_share_obligation_sources", {})),
            "informant_memberships": _clone(getattr(informant.db, "faction_memberships", [])),
            "mara_memberships": _clone(getattr(mara.db, "faction_memberships", [])),
            "worker_memberships": _clone(getattr(worker.db, "faction_memberships", [])),
            "informant_decision_enabled": getattr(informant.db, "decision_enabled", None),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.98 | {V098_VALIDATION_BUILD} ===")
        self.caller.msg(
            "typed institutional Facts may carry non-negative severity; disjoint policy ranges route each exact fact through the existing SHARE_FACT pipeline without introducing implicit precedence"
        )

        try:
            informant.move_to(site, quiet=True)
            mara.move_to(calle, quiet=True)
            worker.move_to(plaza, quiet=True)
            informant.db.decision_enabled = True
            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            informant.db.fact_share_rules = [
                dict(row)
                for row in list(original["informant_rules"] or [])
                if str((row or {}).get("managed_by") or "") != FACTION_FACT_SHARE_POLICY_BUILD
            ]

            _seed_fact(informant, site, FACT_LOW, KEY_LOW, 2)
            _seed_fact(informant, site, FACT_HIGH, KEY_HIGH, 5)
            _seed_fact(informant, site, FACT_MISSING, KEY_MISSING, None)

            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "supervisor", "authority_level": 700})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "commander", "authority_level": 900})

            upsert_faction(_faction([_type_policy(UNFILTERED_POLICY_ID)]))
            legacy_sync = sync_faction_fact_share_policies(informant)
            legacy_facts = {str(row.get("fact_id") or "") for row in _managed_rules(informant)}
            check(
                "v097-unfiltered-type-policy-still-matches-stored-facts-with-or-without-severity",
                legacy_facts == {FACT_LOW, FACT_HIGH, FACT_MISSING}
                and legacy_sync.get("fact_type_policy_build") == FACTION_FACT_TYPE_POLICY_BUILD
                and legacy_sync.get("fact_severity_policy_build") == FACTION_FACT_SEVERITY_POLICY_BUILD,
                f"facts={sorted(legacy_facts)} severity_build={legacy_sync.get('fact_severity_policy_build')}",
            )

            upsert_faction(
                _faction(
                    [
                        _type_policy(LOW_POLICY_ID, minimum=0, maximum=3, min_authority=500),
                        _type_policy(HIGH_POLICY_ID, minimum=4, maximum=None, min_authority=800),
                    ]
                )
            )
            split_sync = sync_faction_fact_share_policies(informant)
            low_rule = _rule_for(informant, FACT_LOW)
            high_rule = _rule_for(informant, FACT_HIGH)
            missing_rule = _rule_for(informant, FACT_MISSING)
            missing_skip = [
                row for row in list(split_sync.get("skipped") or [])
                if row.get("reason") == "FACT_SEVERITY_MISSING_OR_INVALID"
                and row.get("fact_id") == FACT_MISSING
            ]
            check(
                "disjoint-severity-ranges-project-each-concrete-fact-to-the-correct-policy-and-exclude-missing-severity",
                low_rule is not None
                and low_rule.get("authored_rule_id") == LOW_POLICY_ID
                and low_rule.get("fact_severity") == 2
                and high_rule is not None
                and high_rule.get("authored_rule_id") == HIGH_POLICY_ID
                and high_rule.get("fact_severity") == 5
                and missing_rule is None
                and len(missing_skip) == 2,
                f"low={None if low_rule is None else low_rule.get('authored_rule_id')} high={None if high_rule is None else high_rule.get('authored_rule_id')} missing_skips={len(missing_skip)}",
            )

            split_refresh = refresh_fact_share_obligations(informant)
            pairs = _candidate_pairs(informant)
            check(
                "severity-ranges-reuse-existing-authority-and-nearest-selection-to-escalate-low-vs-high-incidents",
                (mara_id, FACT_LOW) in pairs
                and (worker_id, FACT_HIGH) in pairs
                and (worker_id, FACT_LOW) not in pairs
                and (mara_id, FACT_HIGH) not in pairs
                and any(row.get("fact_id") == FACT_LOW and row.get("target_npc_id") == mara_id for row in list(split_refresh.get("materialized") or []))
                and any(row.get("fact_id") == FACT_HIGH and row.get("target_npc_id") == worker_id for row in list(split_refresh.get("materialized") or [])),
                f"pairs={sorted(pairs)}",
            )

            _seed_fact(informant, site, FACT_LOW, KEY_LOW, 5)
            escalated_sync = sync_faction_fact_share_policies(informant)
            escalated_refresh = refresh_fact_share_obligations(informant)
            old_low_obligation = _obligation(informant, mara_id, FACT_LOW)
            new_high_obligation = _obligation(informant, worker_id, FACT_LOW)
            check(
                "raising-fact-severity-switches-policy-and-target-while-cancelling-the-old-pending-branch",
                (_rule_for(informant, FACT_LOW) or {}).get("authored_rule_id") == HIGH_POLICY_ID
                and old_low_obligation is not None
                and old_low_obligation.get("active") is False
                and old_low_obligation.get("cancellation_reason") == "FACTION_POLICY_NO_LONGER_INHERITED"
                and new_high_obligation is not None
                and new_high_obligation.get("active") is True
                and str(new_high_obligation.get("id") or "") == low_worker_oid
                and any(row.get("fact_id") == FACT_LOW and row.get("target_npc_id") == worker_id for row in list(escalated_refresh.get("materialized") or [])),
                f"removed={escalated_sync.get('removed')} old={old_low_obligation} new={new_high_obligation}",
            )

            _seed_fact(informant, site, FACT_LOW, KEY_LOW, 2)
            deescalated_sync = sync_faction_fact_share_policies(informant)
            deescalated_refresh = refresh_fact_share_obligations(informant)
            restored_low = _obligation(informant, mara_id, FACT_LOW)
            stale_high = _obligation(informant, worker_id, FACT_LOW)
            check(
                "lowering-severity-reactivates-the-original-low-branch-identity-and-retires-high-escalation",
                (_rule_for(informant, FACT_LOW) or {}).get("authored_rule_id") == LOW_POLICY_ID
                and restored_low is not None
                and restored_low.get("active") is True
                and str(restored_low.get("id") or "") == low_mara_oid
                and any(
                    row.get("obligation_id") == low_mara_oid and row.get("created") is False
                    for row in list(deescalated_refresh.get("materialized") or [])
                )
                and stale_high is not None
                and stale_high.get("active") is False,
                f"removed={deescalated_sync.get('removed')} restored={restored_low} stale_high={stale_high}",
            )

            upsert_faction(
                _faction(
                    [
                        _type_policy(LOW_POLICY_ID, minimum=0, maximum=5, min_authority=500),
                        _type_policy(HIGH_POLICY_ID, minimum=2, maximum=None, min_authority=800),
                    ]
                )
            )
            overlap = sync_faction_fact_share_policies(informant)
            conflict_facts = {str(row.get("fact_id") or "") for row in list(overlap.get("conflicts") or [])}
            check(
                "overlapping-severity-policies-fail-closed-per-concrete-fact-instead-of-choosing-precedence",
                FACT_LOW in conflict_facts
                and FACT_HIGH in conflict_facts
                and _rule_for(informant, FACT_LOW) is None
                and _rule_for(informant, FACT_HIGH) is None,
                f"conflicts={overlap.get('conflicts')}",
            )

            upsert_faction(_faction([_type_policy(LOW_POLICY_ID, minimum="low", maximum=3, min_authority=500)]))
            malformed = sync_faction_fact_share_policies(informant)
            check(
                "malformed-severity-range-fails-closed-without-derived-rules",
                not _managed_rules(informant)
                and any(row.get("reason") == "BAD_SEVERITY_FILTER" for row in list(malformed.get("skipped") or [])),
                f"skipped={malformed.get('skipped')}",
            )

            upsert_faction(
                _faction(
                    [
                        _exact_policy(GOOD_EXACT_POLICY_ID, FACT_LOW),
                        _exact_policy(BAD_EXACT_POLICY_ID, FACT_HIGH, minimum_marker=4),
                    ]
                )
            )
            exact_sync = sync_faction_fact_share_policies(informant)
            exact_rules = _managed_rules(informant)
            good_rule = next((row for row in exact_rules if row.get("authored_rule_id") == GOOD_EXACT_POLICY_ID), None)
            check(
                "exact-v096-policy-remains-unchanged-while-severity-filter-on-exact-selector-fails-closed",
                good_rule is not None
                and str(good_rule.get("id") or "") == f"FACTION_POLICY:{TEST_FACTION_ID}:{GOOD_EXACT_POLICY_ID}"
                and str(good_rule.get("fact_selector_mode") or "") == "EXACT"
                and not any(row.get("authored_rule_id") == BAD_EXACT_POLICY_ID for row in exact_rules)
                and any(
                    row.get("policy_id") == BAD_EXACT_POLICY_ID
                    and row.get("reason") == "SEVERITY_FILTER_REQUIRES_FACT_TYPE"
                    for row in list(exact_sync.get("skipped") or [])
                )
                and FACTION_FACT_SHARE_POLICY_BUILD == "0.96.0-inherited-faction-fact-share-policies"
                and FACTION_FACT_TYPE_POLICY_BUILD == "0.97.0-fact-type-inherited-faction-policies"
                and FACTION_FACT_SEVERITY_POLICY_BUILD == V098_VALIDATION_BUILD,
                f"rules={[row.get('id') for row in exact_rules]} skipped={exact_sync.get('skipped')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            registry.db.factions = original["registry_factions"]
            for npc, location in (
                (informant, original["informant_location"]),
                (mara, original["mara_location"]),
                (worker, original["worker_location"]),
            ):
                try:
                    if npc.location != location:
                        npc.move_to(location, quiet=True)
                except Exception:
                    pass
            informant.db.knowledge = original["informant_knowledge"]
            informant.db.knowledge_facts = original["informant_facts"]
            mara.db.knowledge = original["mara_knowledge"]
            mara.db.knowledge_facts = original["mara_facts"]
            worker.db.knowledge = original["worker_knowledge"]
            worker.db.knowledge_facts = original["worker_facts"]
            informant.db.relationships = original["informant_relationships"]
            informant.db.fact_share_rules = original["informant_rules"]
            informant.db.fact_share_obligation_sources = original["informant_sources"]
            informant.db.faction_memberships = original["informant_memberships"]
            mara.db.faction_memberships = original["mara_memberships"]
            worker.db.faction_memberships = original["worker_memberships"]
            informant.db.decision_enabled = original["informant_decision_enabled"]

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: faction registry, Informant/Mara/Worker locations, memberships, Knowledge/Facts, managed/local rules, relationships and source-index restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.96 exact and v0.97 typed policy identities remain stable; v0.98 only filters typed policy projection by authored Fact severity"
        )
        self.caller.msg("========================================================")
