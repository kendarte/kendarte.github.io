from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import _find_obligation, _remove_fact_knowledge
from commands.world_input_v90_commands import _seed_known_fact
from commands.world_input_v94_commands import _npc_by_id, _room
from services.fact_share_rule_engine import (
    FACT_SHARE_AUTHORITY_FILTER_BUILD,
    FACT_SHARE_NEED_AWARE_SELECTION_BUILD,
    FACT_SHARE_RECIPIENT_SELECTION_BUILD,
    FACT_SHARE_RULE_BUILD,
    FACT_SHARE_SOURCE_AWARENESS_BUILD,
    FACT_SHARE_TARGET_AWARENESS_BUILD,
    FACT_SHARE_TARGET_MODE_BUILD,
    refresh_fact_share_obligations,
)
from services.faction_engine import upsert_membership
from services.relationship_engine import collect_relationship_candidates
from world.upgrade_pilot_v88 import FACT_ID
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V095_VALIDATION_BUILD = "0.95.0-need-aware-nearest-fact-share-selection"
TEST_FACTION_ID = "TEST-V095-DARSENA-NEED-AWARE"
TEST_RULE_ID = "FACT-SHARE-V095-NEED-AWARE-001"
WORKER_B_NPC_ID = "TEST-NPC-KAL-DAR-WORKER-B"
CALLE_ID = "CAR-KAL-DAR-004"
PLAZA_ID = "CAR-KAL-DAR-003"


def _rule(selection="NEAREST", max_targets=1):
    row = {
        "id": TEST_RULE_ID,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": FACT_ID,
        "target_mode": "FACTION",
        "faction_id": TEST_FACTION_ID,
        "min_authority": 500,
        "priority": 940,
        "one_shot": True,
    }
    if selection is not None:
        row["selection"] = selection
    if max_targets is not None:
        row["max_targets"] = max_targets
    return row


def _candidate_ids(source):
    return {
        str(row.get("relationship_target_npc_id") or "")
        for row in collect_relationship_candidates(source)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
        and str(row.get("fact_id") or "") == FACT_ID
    }


def _materialized_targets(packet):
    return {
        str(row.get("target_npc_id") or "")
        for row in list((packet or {}).get("materialized") or [])
        if str(row.get("rule_id") or "") == TEST_RULE_ID
    }


class CmdSizaValidateV95(Command):
    key = "siza-validate-v95"
    aliases = ["validate-v95"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        informant = install.get("informant") if install.get("success") else None
        mara = install.get("mara") if install.get("success") else None
        site = install.get("site") if install.get("success") else None
        worker = _npc_by_id(WORKER_B_NPC_ID)
        calle = _room("Calle de Servicio", CALLE_ID)
        plaza = _room("Plaza de Recepcion", PLAZA_ID)
        if not informant or not mara or not worker or not site or not calle or not plaza:
            self.caller.msg("[V0.95 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        worker_id = str(getattr(worker.db, "npc_id", "") or "").strip()

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

        self.caller.msg(f"=== SIZA VALIDATION v0.95 | {V095_VALIDATION_BUILD} ===")
        self.caller.msg(
            "NEAREST limited share selects among recipients that still need the exact Fact; already-known or completed one-shot recipients cannot consume scarce slots"
        )

        try:
            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != calle:
                mara.move_to(calle, quiet=True)
            if worker.location != plaza:
                worker.move_to(plaza, quiet=True)
            informant.db.decision_enabled = True
            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            _remove_fact_knowledge(informant)
            _remove_fact_knowledge(mara)
            _remove_fact_knowledge(worker)
            _seed_known_fact(informant, site, "SITE_PRESENCE")

            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "source", "authority_level": 100})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 700})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 700})
            informant.db.fact_share_rules = [_rule("NEAREST", 1)]

            baseline = refresh_fact_share_obligations(informant)
            baseline_rows = [
                row for row in list(baseline.get("materialized") or [])
                if str(row.get("rule_id") or "") == TEST_RULE_ID
            ]
            check(
                "when-both-targets-need-the-fact-v094-nearest-behavior-remains-unchanged",
                _candidate_ids(informant) == {mara_id}
                and _materialized_targets(baseline) == {mara_id}
                and len(baseline_rows) == 1
                and int(baseline_rows[0].get("path_length", -1)) == 1,
                f"selected={sorted(_materialized_targets(baseline))}",
            )

            source_map = dict(getattr(informant.db, "fact_share_obligation_sources", {}) or {})
            mara_oid = f"SHARE-FACT-{mara_id}-{FACT_ID}"
            check(
                "v095-need-aware-selection-is-additive-and-keeps-v089-v094-build-contracts-stable",
                baseline.get("need_aware_selection_build") == FACT_SHARE_NEED_AWARE_SELECTION_BUILD
                and (source_map.get(mara_oid) or {}).get("need_aware_selection_build") == FACT_SHARE_NEED_AWARE_SELECTION_BUILD
                and FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_TARGET_AWARENESS_BUILD == "0.90.0-target-aware-fact-share-pruning"
                and FACT_SHARE_SOURCE_AWARENESS_BUILD == "0.91.0-source-aware-fact-share-cancellation"
                and FACT_SHARE_TARGET_MODE_BUILD == "0.92.0-faction-targeted-fact-share-rules"
                and FACT_SHARE_AUTHORITY_FILTER_BUILD == "0.93.0-faction-authority-filtered-fact-share-rules"
                and FACT_SHARE_RECIPIENT_SELECTION_BUILD == "0.94.0-nearest-limited-faction-fact-share-selection",
                f"need_aware={baseline.get('need_aware_selection_build')}",
            )

            _seed_known_fact(mara, site, "INDEPENDENT_TEST_ACQUISITION")
            fallback = refresh_fact_share_obligations(informant)
            mara_obligation = _find_obligation(informant, mara_id)
            worker_obligation = _find_obligation(informant, worker_id)
            known_row = next(
                (
                    row for row in list(fallback.get("skipped") or [])
                    if row.get("reason") == "TARGET_ALREADY_KNOWS_FACT"
                    and str(row.get("target_npc_id") or "") == mara_id
                ),
                {},
            )
            worker_rows = [
                row for row in list(fallback.get("materialized") or [])
                if str(row.get("target_npc_id") or "") == worker_id
            ]
            check(
                "nearest-known-recipient-is-retired-before-slot-selection-and-next-ignorant-recipient-fills-max-one",
                mara_obligation is not None
                and mara_obligation.get("active") is False
                and mara_obligation.get("status") == "completed"
                and mara_obligation.get("completion_reason") == "TARGET_ALREADY_KNOWS_FACT"
                and bool(known_row.get("preselection_pruned"))
                and _candidate_ids(informant) == {worker_id}
                and _materialized_targets(fallback) == {worker_id}
                and len(worker_rows) == 1
                and int(worker_rows[0].get("path_length", -1)) == 2
                and worker_obligation is not None
                and worker_obligation.get("active") is True,
                f"candidates={sorted(_candidate_ids(informant))} worker_path={None if not worker_rows else worker_rows[0].get('path_length')}",
            )

            _remove_fact_knowledge(mara)
            completed_fallback = refresh_fact_share_obligations(informant)
            completed_row = next(
                (
                    row for row in list(completed_fallback.get("skipped") or [])
                    if row.get("reason") == "ALREADY_COMPLETED"
                    and str(row.get("target_npc_id") or "") == mara_id
                ),
                {},
            )
            check(
                "completed-one-shot-nearest-recipient-stays-out-of-limited-selection-even-after-losing-the-fact",
                bool(completed_row.get("preselection_pruned"))
                and (_find_obligation(informant, mara_id) or {}).get("status") == "completed"
                and (_find_obligation(informant, mara_id) or {}).get("active") is False
                and _candidate_ids(informant) == {worker_id}
                and mara_id not in _materialized_targets(completed_fallback),
                f"candidates={sorted(_candidate_ids(informant))}",
            )

            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            _remove_fact_knowledge(mara)
            _remove_fact_knowledge(worker)
            informant.db.fact_share_rules = [_rule(None, None)]
            legacy_all = refresh_fact_share_obligations(informant)
            check(
                "selection-all-remains-v093-compatible-and-does-not-apply-limited-slot-prepruning",
                _candidate_ids(informant) == {mara_id, worker_id}
                and _materialized_targets(legacy_all) == {mara_id, worker_id},
                f"candidates={sorted(_candidate_ids(informant))}",
            )

            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            _remove_fact_knowledge(mara)
            _remove_fact_knowledge(worker)
            _seed_known_fact(mara, site, "INDEPENDENT_TEST_ACQUISITION")
            _seed_known_fact(worker, site, "INDEPENDENT_TEST_ACQUISITION")
            informant.db.fact_share_rules = [_rule("NEAREST", 1)]
            nobody_needs = refresh_fact_share_obligations(informant)
            known_ids = {
                str(row.get("target_npc_id") or "")
                for row in list(nobody_needs.get("skipped") or [])
                if row.get("reason") == "TARGET_ALREADY_KNOWS_FACT"
                and bool(row.get("preselection_pruned"))
            }
            check(
                "limited-selection-with-no-recipient-needing-the-fact-produces-no-social-travel",
                known_ids == {mara_id, worker_id}
                and not _candidate_ids(informant)
                and not _materialized_targets(nobody_needs),
                f"known={sorted(known_ids)} candidates={sorted(_candidate_ids(informant))}",
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
            "STATE RESTORED: Informant/Mara/Worker locations, Knowledge/Facts, memberships, share rules, obligations and source-index restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.94 path/authority ranking is unchanged; v0.95 only removes already-satisfied/terminal recipients before limited NEAREST slots are assigned"
        )
        self.caller.msg("========================================================")
