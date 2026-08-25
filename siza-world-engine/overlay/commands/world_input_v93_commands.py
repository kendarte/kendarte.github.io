from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import _find_obligation, _remove_fact_knowledge, _target_room
from commands.world_input_v90_commands import _seed_known_fact
from services.fact_share_rule_engine import (
    FACT_SHARE_AUTHORITY_FILTER_BUILD,
    FACT_SHARE_RULE_BUILD,
    FACT_SHARE_SOURCE_AWARENESS_BUILD,
    FACT_SHARE_TARGET_AWARENESS_BUILD,
    FACT_SHARE_TARGET_MODE_BUILD,
    refresh_fact_share_obligations,
)
from services.faction_engine import membership_authority, upsert_membership
from services.relationship_engine import collect_relationship_candidates
from world.upgrade_pilot_v88 import FACT_ID
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V093_VALIDATION_BUILD = "0.93.0-faction-authority-filtered-fact-share-rules"
TEST_FACTION_ID = "TEST-V093-DARSENA-HIERARCHY"
TEST_RULE_ID = "FACT-SHARE-V093-AUTHORITY-001"
WORKER_B_NPC_ID = "TEST-NPC-KAL-DAR-WORKER-B"


def _npc_by_id(npc_id):
    from evennia import search_tag

    for npc in search_tag("kalnaj_pilot_v03_entities", category="siza_entity"):
        if str(getattr(npc.db, "npc_id", "") or "").strip() == str(npc_id or "").strip():
            return npc
    return None


def _obligation_id(target_id):
    return f"SHARE-FACT-{str(target_id)}-{FACT_ID}"


def _rule(min_authority_marker=500):
    row = {
        "id": TEST_RULE_ID,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": FACT_ID,
        "target_mode": "FACTION",
        "faction_id": TEST_FACTION_ID,
        "priority": 940,
        "one_shot": True,
    }
    if min_authority_marker is not None:
        row["min_authority"] = min_authority_marker
    return row


def _candidate_ids(source):
    return {
        str(row.get("relationship_target_npc_id") or "")
        for row in collect_relationship_candidates(source)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
        and str(row.get("fact_id") or "") == FACT_ID
    }


class CmdSizaValidateV93(Command):
    key = "siza-validate-v93"
    aliases = ["validate-v93"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        informant = install.get("informant") if install.get("success") else None
        mara = install.get("mara") if install.get("success") else None
        site = install.get("site") if install.get("success") else None
        worker = _npc_by_id(WORKER_B_NPC_ID)
        away = _target_room()
        if not informant or not mara or not worker or not site or not away:
            self.caller.msg("[V0.93 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        worker_id = str(getattr(worker.db, "npc_id", "") or "").strip()
        mara_oid = _obligation_id(mara_id)
        worker_oid = _obligation_id(worker_id)

        original = {
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

        self.caller.msg(f"=== SIZA VALIDATION v0.93 | {V093_VALIDATION_BUILD} ===")
        self.caller.msg(
            "FACTION share + optional min_authority -> only qualifying current members get branches; hierarchy changes prune/reactivate exact obligations; malformed thresholds fail closed"
        )

        try:
            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != away:
                mara.move_to(away, quiet=True)
            if worker.location != away:
                worker.move_to(away, quiet=True)
            informant.db.decision_enabled = True
            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            _remove_fact_knowledge(informant)
            _remove_fact_knowledge(mara)
            _remove_fact_knowledge(worker)
            _seed_known_fact(informant, site, "SITE_PRESENCE")

            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "source", "authority_level": 100})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "supervisor", "authority_level": 700})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "worker", "authority_level": 200})
            informant.db.fact_share_rules = [_rule(500)]

            first = refresh_fact_share_obligations(informant)
            first_targets = {
                str(row.get("target_npc_id") or "")
                for row in list(first.get("materialized") or [])
                if str(row.get("rule_id") or "") == TEST_RULE_ID
            }
            check(
                "min-authority-faction-rule-selects-only-current-members-at-or-above-threshold",
                first_targets == {mara_id}
                and informant_id not in first_targets
                and _find_obligation(informant, mara_id) is not None
                and _find_obligation(informant, worker_id) is None,
                f"targets={sorted(first_targets)} mara_auth={membership_authority(mara, TEST_FACTION_ID)} worker_auth={membership_authority(worker, TEST_FACTION_ID)}",
            )

            source_map = dict(getattr(informant.db, "fact_share_obligation_sources", {}) or {})
            check(
                "authority-filter-is-holder-local-rule-metadata-and-historical-capability-builds-remain-stable",
                int((source_map.get(mara_oid) or {}).get("min_authority", -1)) == 500
                and (source_map.get(mara_oid) or {}).get("authority_filter_build") == FACT_SHARE_AUTHORITY_FILTER_BUILD
                and FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_TARGET_AWARENESS_BUILD == "0.90.0-target-aware-fact-share-pruning"
                and FACT_SHARE_SOURCE_AWARENESS_BUILD == "0.91.0-source-aware-fact-share-cancellation"
                and FACT_SHARE_TARGET_MODE_BUILD == "0.92.0-faction-targeted-fact-share-rules"
                and first.get("authority_filter_build") == FACT_SHARE_AUTHORITY_FILTER_BUILD,
                f"authority_filter={first.get('authority_filter_build')}",
            )

            informant.db.fact_share_rules = [_rule(None)]
            legacy = refresh_fact_share_obligations(informant)
            legacy_targets = _candidate_ids(informant)
            check(
                "omitting-min-authority-preserves-v092-all-active-faction-member-fanout",
                legacy_targets == {mara_id, worker_id}
                and any(str(row.get("target_npc_id") or "") == worker_id for row in list(legacy.get("materialized") or [])),
                f"candidates={sorted(legacy_targets)}",
            )

            informant.db.fact_share_rules = [_rule(500)]
            threshold_again = refresh_fact_share_obligations(informant)
            worker_cancelled = _find_obligation(informant, worker_id)
            check(
                "reapplying-threshold-cancels-only-below-authority-branch-before-candidate-selection",
                worker_cancelled is not None
                and worker_cancelled.get("active") is False
                and worker_cancelled.get("cancellation_reason") == "TARGET_NO_LONGER_MATCHES_RULE"
                and _candidate_ids(informant) == {mara_id}
                and any(
                    str(row.get("target_npc_id") or "") == worker_id
                    and row.get("reason") == "TARGET_NO_LONGER_MATCHES_RULE"
                    for row in list(threshold_again.get("skipped") or [])
                ),
                f"worker_status={None if worker_cancelled is None else worker_cancelled.get('status')}",
            )

            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "worker", "authority_level": 600})
            promoted = refresh_fact_share_obligations(informant)
            worker_active = _find_obligation(informant, worker_id)
            check(
                "promotion-above-threshold-reactivates-the-same-worker-obligation-id-without-duplication",
                any(
                    str(row.get("obligation_id") or "") == worker_oid
                    and row.get("created") is False
                    for row in list(promoted.get("materialized") or [])
                )
                and worker_active is not None
                and worker_active.get("active") is True
                and _candidate_ids(informant) == {mara_id, worker_id},
                f"worker_auth={membership_authority(worker, TEST_FACTION_ID)}",
            )

            informant.db.fact_share_rules = [_rule("alto")]
            malformed = refresh_fact_share_obligations(informant)
            bad_row = next(
                (row for row in list(malformed.get("skipped") or []) if row.get("reason") == "BAD_MIN_AUTHORITY"),
                {},
            )
            mara_bad = _find_obligation(informant, mara_id)
            worker_bad = _find_obligation(informant, worker_id)
            check(
                "malformed-authority-filter-fails-closed-by-cancelling-existing-pending-branches",
                mara_bad is not None
                and worker_bad is not None
                and mara_bad.get("active") is False
                and worker_bad.get("active") is False
                and mara_bad.get("cancellation_reason") == "BAD_MIN_AUTHORITY"
                and worker_bad.get("cancellation_reason") == "BAD_MIN_AUTHORITY"
                and len(list(bad_row.get("cancelled_obligations") or [])) == 2
                and not _candidate_ids(informant),
                f"cancelled={bad_row.get('cancelled_obligations')}",
            )

            informant.db.fact_share_rules = [_rule(500)]
            recovered = refresh_fact_share_obligations(informant)
            recovered_ids = {
                str(row.get("obligation_id") or "")
                for row in list(recovered.get("materialized") or [])
                if row.get("created") is False
            }
            check(
                "correcting-authority-filter-reactivates-the-same-existing-branches",
                {mara_oid, worker_oid}.issubset(recovered_ids)
                and (_find_obligation(informant, mara_id) or {}).get("active") is True
                and (_find_obligation(informant, worker_id) or {}).get("active") is True
                and _candidate_ids(informant) == {mara_id, worker_id},
                f"reactivated={sorted(recovered_ids)}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
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

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara/Worker location, Knowledge/Facts, memberships, share rules, obligations and source-index restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.92 faction fanout remains the default when min_authority is absent; v0.93 only adds deterministic hierarchy filtering"
        )
        self.caller.msg("========================================================")
