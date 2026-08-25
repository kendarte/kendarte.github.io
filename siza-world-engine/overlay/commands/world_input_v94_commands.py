from evennia import Command, search_object

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import _find_obligation, _remove_fact_knowledge
from commands.world_input_v90_commands import _seed_known_fact
from services.fact_share_rule_engine import (
    FACT_SHARE_AUTHORITY_FILTER_BUILD,
    FACT_SHARE_RECIPIENT_SELECTION_BUILD,
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


V094_VALIDATION_BUILD = "0.94.0-nearest-limited-faction-fact-share-selection"
TEST_FACTION_ID = "TEST-V094-DARSENA-CHAIN-OF-COMMAND"
TEST_RULE_ID = "FACT-SHARE-V094-NEAREST-001"
WORKER_B_NPC_ID = "TEST-NPC-KAL-DAR-WORKER-B"
CALLE_ID = "CAR-KAL-DAR-004"
PLAZA_ID = "CAR-KAL-DAR-003"


def _npc_by_id(npc_id):
    from evennia import search_tag

    for npc in search_tag("kalnaj_pilot_v03_entities", category="siza_entity"):
        if str(getattr(npc.db, "npc_id", "") or "").strip() == str(npc_id or "").strip():
            return npc
    return None


def _room(key, room_id):
    for obj in search_object(key):
        if str(getattr(obj.db, "room_id", "") or "") == str(room_id):
            return obj
    return None


def _obligation_id(target_id):
    return f"SHARE-FACT-{str(target_id)}-{FACT_ID}"


def _rule(selection_marker="NEAREST", max_targets_marker=1):
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
    if selection_marker is not None:
        row["selection"] = selection_marker
    if max_targets_marker is not None:
        row["max_targets"] = max_targets_marker
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


class CmdSizaValidateV94(Command):
    key = "siza-validate-v94"
    aliases = ["validate-v94"]
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
            self.caller.msg("[V0.94 VALIDATION] FAIL | persistent context missing")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.94 | {V094_VALIDATION_BUILD} ===")
        self.caller.msg(
            "FACTION + min_authority -> optional NEAREST selection uses real passable path length -> limited branches follow current nearest qualifying recipients"
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

            informant.db.fact_share_rules = [_rule(None, None)]
            legacy = refresh_fact_share_obligations(informant)
            check(
                "omitting-selection-preserves-v093-all-qualified-faction-recipient-behavior",
                _candidate_ids(informant) == {mara_id, worker_id}
                and _materialized_targets(legacy) == {mara_id, worker_id},
                f"candidates={sorted(_candidate_ids(informant))}",
            )

            informant.db.fact_share_rules = [_rule("NEAREST", 1)]
            nearest = refresh_fact_share_obligations(informant)
            worker_cancelled = _find_obligation(informant, worker_id)
            nearest_rows = [
                row
                for row in list(nearest.get("materialized") or [])
                if str(row.get("rule_id") or "") == TEST_RULE_ID
            ]
            check(
                "nearest-max-one-selects-only-the-shortest-real-path-and-prunes-farther-pending-branch",
                _candidate_ids(informant) == {mara_id}
                and len(nearest_rows) == 1
                and str(nearest_rows[0].get("target_npc_id") or "") == mara_id
                and int(nearest_rows[0].get("path_length", -1)) == 1
                and worker_cancelled is not None
                and worker_cancelled.get("active") is False
                and worker_cancelled.get("cancellation_reason") == "TARGET_NO_LONGER_MATCHES_RULE",
                f"selected={_materialized_targets(nearest)} path={None if not nearest_rows else nearest_rows[0].get('path_length')}",
            )

            source_map = dict(getattr(informant.db, "fact_share_obligation_sources", {}) or {})
            check(
                "nearest-selection-metadata-is-holder-local-and-v089-v093-build-contracts-remain-stable",
                str((source_map.get(mara_oid) or {}).get("selection") or "") == "NEAREST"
                and int((source_map.get(mara_oid) or {}).get("max_targets", 0) or 0) == 1
                and (source_map.get(mara_oid) or {}).get("recipient_selection_build") == FACT_SHARE_RECIPIENT_SELECTION_BUILD
                and FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_TARGET_AWARENESS_BUILD == "0.90.0-target-aware-fact-share-pruning"
                and FACT_SHARE_SOURCE_AWARENESS_BUILD == "0.91.0-source-aware-fact-share-cancellation"
                and FACT_SHARE_TARGET_MODE_BUILD == "0.92.0-faction-targeted-fact-share-rules"
                and FACT_SHARE_AUTHORITY_FILTER_BUILD == "0.93.0-faction-authority-filtered-fact-share-rules"
                and nearest.get("recipient_selection_build") == FACT_SHARE_RECIPIENT_SELECTION_BUILD,
                f"selection_build={nearest.get('recipient_selection_build')}",
            )

            mara.move_to(plaza, quiet=True)
            worker.move_to(calle, quiet=True)
            switched = refresh_fact_share_obligations(informant)
            mara_cancelled = _find_obligation(informant, mara_id)
            worker_active = _find_obligation(informant, worker_id)
            check(
                "moving-qualified-members-switches-the-single-active-branch-to-the-new-nearest-target",
                _candidate_ids(informant) == {worker_id}
                and _materialized_targets(switched) == {worker_id}
                and mara_cancelled is not None
                and mara_cancelled.get("active") is False
                and worker_active is not None
                and worker_active.get("active") is True
                and any(
                    str(row.get("obligation_id") or "") == worker_oid
                    and row.get("created") is False
                    for row in list(switched.get("materialized") or [])
                ),
                f"candidates={sorted(_candidate_ids(informant))}",
            )

            mara.move_to(calle, quiet=True)
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 700})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 800})
            tie = refresh_fact_share_obligations(informant)
            check(
                "equal-distance-nearest-tie-breaks-by-higher-current-faction-authority",
                _candidate_ids(informant) == {worker_id}
                and _materialized_targets(tie) == {worker_id}
                and membership_authority(worker, TEST_FACTION_ID) > membership_authority(mara, TEST_FACTION_ID),
                f"mara_auth={membership_authority(mara, TEST_FACTION_ID)} worker_auth={membership_authority(worker, TEST_FACTION_ID)}",
            )

            informant.db.fact_share_rules = [_rule("NEAREST", 2)]
            two = refresh_fact_share_obligations(informant)
            check(
                "nearest-max-two-materializes-the-two-best-qualified-reachable-branches-without-new-obligation-identities",
                _candidate_ids(informant) == {mara_id, worker_id}
                and _materialized_targets(two) == {mara_id, worker_id}
                and all(
                    row.get("created") is False
                    for row in list(two.get("materialized") or [])
                    if str(row.get("rule_id") or "") == TEST_RULE_ID
                ),
                f"targets={sorted(_materialized_targets(two))}",
            )

            informant.db.fact_share_rules = [_rule("RANDOM", 1)]
            malformed = refresh_fact_share_obligations(informant)
            bad_row = next(
                (row for row in list(malformed.get("skipped") or []) if row.get("reason") == "BAD_SELECTION"),
                {},
            )
            check(
                "malformed-selection-fails-closed-and-cancels-existing-pending-branches",
                len(list(bad_row.get("cancelled_obligations") or [])) == 2
                and not _candidate_ids(informant)
                and (_find_obligation(informant, mara_id) or {}).get("cancellation_reason") == "BAD_SELECTION"
                and (_find_obligation(informant, worker_id) or {}).get("cancellation_reason") == "BAD_SELECTION",
                f"cancelled={bad_row.get('cancelled_obligations')}",
            )

            informant.db.fact_share_rules = [_rule("NEAREST", 2)]
            recovered = refresh_fact_share_obligations(informant)
            recovered_ids = {
                str(row.get("obligation_id") or "")
                for row in list(recovered.get("materialized") or [])
                if row.get("created") is False
            }
            check(
                "correcting-selection-reactivates-the-same-existing-branches-without-duplication",
                {mara_oid, worker_oid}.issubset(recovered_ids)
                and _candidate_ids(informant) == {mara_id, worker_id},
                f"reactivated={sorted(recovered_ids)}",
            )

            informant.db.fact_share_rules = [_rule("NEAREST", 0)]
            bad_limit = refresh_fact_share_obligations(informant)
            limit_row = next(
                (row for row in list(bad_limit.get("skipped") or []) if row.get("reason") == "BAD_MAX_TARGETS"),
                {},
            )
            check(
                "malformed-max-targets-also-fails-closed-instead-of-leaving-old-nearest-branches-active",
                len(list(limit_row.get("cancelled_obligations") or [])) == 2
                and not _candidate_ids(informant),
                f"cancelled={limit_row.get('cancelled_obligations')}",
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
            "PERSISTENT SYSTEM RETAINED: v0.92/v0.93 faction eligibility remains authoritative; v0.94 only selects a deterministic reachable subset before normal SHARE_FACT materialization"
        )
        self.caller.msg("========================================================")
