from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import _find_obligation, _remove_fact_knowledge, _target_room
from commands.world_input_v90_commands import _seed_known_fact
from services.fact_share_rule_engine import (
    FACT_SHARE_RULE_BUILD,
    FACT_SHARE_SOURCE_AWARENESS_BUILD,
    FACT_SHARE_TARGET_AWARENESS_BUILD,
    FACT_SHARE_TARGET_MODE_BUILD,
    refresh_fact_share_obligations,
)
from services.faction_engine import set_membership_active, upsert_membership
from services.knowledge_fact_engine import find_knowledge_fact
from services.relationship_engine import collect_relationship_candidates, resolve_relationship_goal
from world.upgrade_pilot_v88 import FACT_ID
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V092_VALIDATION_BUILD = "0.92.0-faction-targeted-fact-share-rules"
TEST_FACTION_ID = "TEST-V092-DARSENA-REPORT-NET"
TEST_RULE_ID = "FACT-SHARE-V092-FACTION-001"
WORKER_B_NPC_ID = "TEST-NPC-KAL-DAR-WORKER-B"


def _npc_by_id(npc_id):
    from evennia import search_tag

    for npc in search_tag("kalnaj_pilot_v03_entities", category="siza_entity"):
        if str(getattr(npc.db, "npc_id", "") or "").strip() == str(npc_id or "").strip():
            return npc
    return None


def _obligation_id(target_id):
    return f"SHARE-FACT-{str(target_id)}-{FACT_ID}"


def _candidate_ids(npc):
    return {
        str(row.get("relationship_target_npc_id") or "")
        for row in collect_relationship_candidates(npc)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
        and str(row.get("fact_id") or "") == FACT_ID
    }


def _rule():
    return {
        "id": TEST_RULE_ID,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": FACT_ID,
        "target_mode": "FACTION",
        "faction_id": TEST_FACTION_ID,
        "priority": 940,
        "one_shot": True,
    }


class CmdSizaValidateV92(Command):
    key = "siza-validate-v92"
    aliases = ["validate-v92"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.92 VALIDATION] FAIL | install={install}")
            return

        informant = install.get("informant")
        mara = install.get("mara")
        site = install.get("site")
        worker = _npc_by_id(WORKER_B_NPC_ID)
        away = _target_room()
        if not informant or not mara or not worker or not site or not away:
            self.caller.msg("[V0.92 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        worker_id = str(getattr(worker.db, "npc_id", "") or "").strip()
        mara_obligation_id = _obligation_id(mara_id)
        worker_obligation_id = _obligation_id(worker_id)

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
            "informant_current_goal": _clone(getattr(informant.db, "current_goal", None)),
            "informant_destination": getattr(informant.db, "destination_id", None),
            "informant_activity": getattr(informant.db, "current_activity", None),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.92 | {V092_VALIDATION_BUILD} ===")
        self.caller.msg(
            "one Fact-share rule targets a faction -> one normal SHARE_FACT obligation per active member -> source excluded -> membership churn cancels/reactivates only the affected target"
        )

        try:
            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != away:
                mara.move_to(away, quiet=True)
            if worker.location != away:
                worker.move_to(away, quiet=True)

            informant.db.decision_enabled = True
            informant.db.current_goal = None
            informant.db.destination_id = None
            informant.db.current_activity = None
            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            informant.db.fact_share_rules = [_rule()]

            _remove_fact_knowledge(informant)
            _remove_fact_knowledge(mara)
            _remove_fact_knowledge(worker)
            _seed_known_fact(informant, site, "SITE_PRESENCE")

            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "source"})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "recipient"})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "recipient"})

            first = refresh_fact_share_obligations(informant)
            first_targets = {
                str(row.get("target_npc_id") or "")
                for row in list(first.get("materialized") or [])
                if str(row.get("rule_id") or "") == TEST_RULE_ID
            }
            check(
                "faction-target-mode-expands-one-rule-to-all-active-members-except-source",
                first_targets == {mara_id, worker_id}
                and informant_id not in first_targets
                and all(str(row.get("target_mode") or "") == "FACTION" for row in list(first.get("materialized") or [])),
                f"targets={sorted(first_targets)} source={informant_id}",
            )

            mara_obligation = _find_obligation(informant, mara_id)
            worker_obligation = _find_obligation(informant, worker_id)
            source_map = dict(getattr(informant.db, "fact_share_obligation_sources", {}) or {})
            check(
                "faction-fanout-materializes-independent-normal-share-fact-obligations-with-rule-provenance",
                mara_obligation is not None
                and worker_obligation is not None
                and mara_obligation.get("active") is True
                and worker_obligation.get("active") is True
                and str(mara_obligation.get("kind") or "") == "SHARE_FACT"
                and str(worker_obligation.get("kind") or "") == "SHARE_FACT"
                and str((source_map.get(mara_obligation_id) or {}).get("rule_id") or "") == TEST_RULE_ID
                and str((source_map.get(worker_obligation_id) or {}).get("rule_id") or "") == TEST_RULE_ID,
                f"mara={mara_obligation_id in source_map} worker={worker_obligation_id in source_map}",
            )

            candidates = _candidate_ids(informant)
            check(
                "both-faction-obligations-enter-existing-relationship-candidate-system-independently",
                candidates == {mara_id, worker_id},
                f"candidates={sorted(candidates)}",
            )

            set_membership_active(worker, TEST_FACTION_ID, False)
            left = refresh_fact_share_obligations(informant)
            worker_after_leave = _find_obligation(informant, worker_id)
            mara_after_leave = _find_obligation(informant, mara_id)
            left_candidates = _candidate_ids(informant)
            check(
                "leaving-faction-cancels-only-that-targets-pending-share-and-keeps-other-member-active",
                any(
                    str(row.get("target_npc_id") or "") == worker_id
                    and row.get("reason") == "TARGET_NO_LONGER_MATCHES_RULE"
                    for row in list(left.get("skipped") or [])
                )
                and worker_after_leave is not None
                and worker_after_leave.get("active") is False
                and str(worker_after_leave.get("status") or "") == "cancelled"
                and worker_after_leave.get("cancellation_reason") == "TARGET_NO_LONGER_MATCHES_RULE"
                and mara_after_leave is not None
                and mara_after_leave.get("active") is True
                and left_candidates == {mara_id},
                f"candidates={sorted(left_candidates)} worker_status={None if worker_after_leave is None else worker_after_leave.get('status')}",
            )

            set_membership_active(worker, TEST_FACTION_ID, True)
            rejoined = refresh_fact_share_obligations(informant)
            worker_rejoined = _find_obligation(informant, worker_id)
            check(
                "rejoining-faction-reactivates-same-worker-obligation-id-without-duplication",
                any(
                    str(row.get("target_npc_id") or "") == worker_id
                    and str(row.get("obligation_id") or "") == worker_obligation_id
                    and row.get("created") is False
                    for row in list(rejoined.get("materialized") or [])
                )
                and worker_rejoined is not None
                and worker_rejoined.get("active") is True
                and str(worker_rejoined.get("status") or "") == "pending",
                f"materialized={rejoined.get('materialized')}",
            )

            if mara.location != site:
                mara.move_to(site, quiet=True)
            resolved = resolve_relationship_goal(informant, mara_obligation_id, mara_id)
            mara_fact = find_knowledge_fact(mara, FACT_ID)
            worker_still = _find_obligation(informant, worker_id)
            after_one_complete = refresh_fact_share_obligations(informant)
            check(
                "completing-one-faction-recipient-transfers-only-to-that-npc-and-leaves-other-target-independent",
                resolved.get("completed") is True
                and resolved.get("relationship_kind") == "SHARE_FACT"
                and mara_fact is not None
                and find_knowledge_fact(worker, FACT_ID) is None
                and worker_still is not None
                and worker_still.get("active") is True
                and any(
                    str(row.get("target_npc_id") or "") == mara_id
                    and row.get("reason") == "ALREADY_COMPLETED"
                    for row in list(after_one_complete.get("skipped") or [])
                ),
                f"resolved={resolved.get('completed')} worker_active={None if worker_still is None else worker_still.get('active')}",
            )

            _remove_fact_knowledge(informant)
            source_lost = refresh_fact_share_obligations(informant)
            worker_cancelled = _find_obligation(informant, worker_id)
            source_lost_row = next(
                (
                    row
                    for row in list(source_lost.get("skipped") or [])
                    if str((row or {}).get("rule_id") or "") == TEST_RULE_ID
                    and (row or {}).get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                ),
                {},
            )
            check(
                "source-loss-cancels-all-still-pending-obligations-owned-by-the-faction-rule",
                worker_cancelled is not None
                and worker_cancelled.get("active") is False
                and str(worker_cancelled.get("status") or "") == "cancelled"
                and worker_cancelled.get("cancellation_reason") == "SOURCE_NO_LONGER_KNOWS_FACT"
                and any(
                    str(row.get("target_npc_id") or "") == worker_id
                    for row in list(source_lost_row.get("cancelled_obligations") or [])
                ),
                f"worker_status={None if worker_cancelled is None else worker_cancelled.get('status')}",
            )

            check(
                "historical-fact-share-capabilities-remain-stable-and-v092-is-additive",
                FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_TARGET_AWARENESS_BUILD == "0.90.0-target-aware-fact-share-pruning"
                and FACT_SHARE_SOURCE_AWARENESS_BUILD == "0.91.0-source-aware-fact-share-cancellation"
                and first.get("target_mode_build") == FACT_SHARE_TARGET_MODE_BUILD,
                f"target_mode={first.get('target_mode_build')}",
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
            informant.db.current_goal = original["informant_current_goal"]
            informant.db.destination_id = original["informant_destination"]
            informant.db.current_activity = original["informant_activity"]

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara/Worker location, Knowledge/Facts, faction memberships, social obligations/rules/index and Informant decision state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.89 SHARE_FACT obligations and local transfer remain authoritative; v0.92 only expands authored targets through current faction memberships"
        )
        self.caller.msg("========================================================")
