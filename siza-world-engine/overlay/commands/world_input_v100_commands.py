from evennia import Command, search_object, search_tag

from commands.world_input_v74_commands import _clone
from services.fact_driven_decision import decision_step
from services.fact_share_holder_acquisition_engine import (
    FACT_SHARE_HOLDER_ACQUISITION_BUILD,
    fact_holder_acquisition,
    refresh_holder_aware_fact_share_obligations,
)
from services.fact_share_rule_engine import (
    FACT_SHARE_AUTHORITY_RELATION_BUILD,
    FACT_SHARE_RULE_BUILD,
)
from services.faction_fact_share_policy_engine import sync_faction_fact_share_policies
from services.faction_engine import get_faction_registry, upsert_faction, upsert_membership
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.relationship_engine import collect_relationship_candidates, inspect_relationships
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V100_VALIDATION_BUILD = "1.00.0-holder-acquisition-aware-fact-sharing"
TEST_FACTION_ID = "TEST-V100-DARSENA-PROVENANCE"
TEST_POLICY_ID = "POLICY-V100-HOLDER-ACQUISITION-001"
TEST_FACT_ID = "FACT-V100-HOLDER-ACQUISITION-001"
TEST_KNOWLEDGE_KEY = "V100_HOLDER_ACQUISITION"
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


def _policy(holder_acquisition=None):
    row = {
        "id": TEST_POLICY_ID,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": TEST_FACT_ID,
        "target_mode": "FACTION",
        "authority_relation": "HIGHER_THAN_SOURCE",
        "selection": "NEAREST",
        "max_targets": 1,
        "priority": 1000,
        "one_shot": True,
    }
    if holder_acquisition is not None:
        row["holder_acquisition"] = holder_acquisition
    return row


def _faction(holder_acquisition=None):
    return {
        "id": TEST_FACTION_ID,
        "name": TEST_FACTION_ID,
        "active": True,
        "canon_status": "prototype",
        "fact_share_policies": [_policy(holder_acquisition)],
    }


def _seed_fact(npc, site):
    payload = {
        "id": TEST_FACT_ID,
        "knowledge_key": TEST_KNOWLEDGE_KEY,
        "required_level": 1,
        "fact_type": "SECURITY_INCIDENT",
        "severity": 5,
        "topic": "provenance de holder de prueba",
        "text": "Un incidente de prueba distingue adquisición local de evidencia no transferida.",
        "canon_status": "prototype",
        "source": {
            "kind": "VALIDATOR_SEED",
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
        },
        "learned_by": {"mode": "VALIDATOR"},
    }
    upsert_knowledge_fact(npc, payload)
    set_knowledge_level(npc, TEST_KNOWLEDGE_KEY, 1)
    return payload


def _candidate_ids(source):
    return {
        str(row.get("relationship_target_npc_id") or "")
        for row in collect_relationship_candidates(source)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
        and str(row.get("fact_id") or "") == TEST_FACT_ID
    }


def _find_obligation(source, target_id):
    wanted = f"SHARE-FACT-{str(target_id)}-{TEST_FACT_ID}"
    for relation in inspect_relationships(source):
        if str(relation.get("target_npc_id") or "") != str(target_id):
            continue
        for raw in list(relation.get("obligations") or []):
            row = dict(raw or {})
            if str(row.get("id") or "") == wanted:
                return row
    return None


class CmdSizaValidateV100(Command):
    key = "siza-validate-v100"
    aliases = ["validate-v100"]
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
            self.caller.msg("[V1.00 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        worker_id = str(getattr(worker.db, "npc_id", "") or "").strip()
        mara_oid = f"SHARE-FACT-{mara_id}-{TEST_FACT_ID}"
        worker_oid = f"SHARE-FACT-{worker_id}-{TEST_FACT_ID}"

        original = {
            "registry_factions": _clone(getattr(registry.db, "factions", {})),
            "npcs": {},
        }
        for name, npc in (("informant", informant), ("mara", mara), ("worker", worker)):
            original["npcs"][name] = {
                "location": npc.location,
                "knowledge": _clone(getattr(npc.db, "knowledge", {})),
                "facts": _clone(getattr(npc.db, "knowledge_facts", [])),
                "relationships": _clone(getattr(npc.db, "relationships", {})),
                "rules": _clone(getattr(npc.db, "fact_share_rules", [])),
                "sources": _clone(getattr(npc.db, "fact_share_obligation_sources", {})),
                "memberships": _clone(getattr(npc.db, "faction_memberships", [])),
                "decision_enabled": getattr(npc.db, "decision_enabled", None),
                "current_goal": _clone(getattr(npc.db, "current_goal", None)),
                "destination_id": getattr(npc.db, "destination_id", None),
                "current_activity": getattr(npc.db, "current_activity", None),
            }

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v1.00 | {V100_VALIDATION_BUILD} ===")
        self.caller.msg(
            "holder_acquisition gate distinguishes non-transferred holder state from a Fact received through DIRECT_LOCAL without rewriting original provenance"
        )

        try:
            informant.move_to(site, quiet=True)
            mara.move_to(calle, quiet=True)
            worker.move_to(plaza, quiet=True)
            for npc in (informant, mara, worker):
                npc.db.knowledge = {}
                npc.db.knowledge_facts = []
                npc.db.relationships = {}
                npc.db.fact_share_rules = []
                npc.db.fact_share_obligation_sources = {}
                npc.db.decision_enabled = True
                npc.db.current_goal = None
                npc.db.destination_id = None
                npc.db.current_activity = None

            seeded = _seed_fact(informant, site)
            upsert_faction(_faction())
            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "supervisor", "authority_level": 500})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 800})

            sync_faction_fact_share_policies(informant)
            legacy = refresh_holder_aware_fact_share_obligations(informant)
            informant_fact = find_knowledge_fact(informant, TEST_FACT_ID)
            check(
                "omitted-holder-acquisition-preserves-any-behavior-and-classifies-seeded-holder-as-nontransferred",
                legacy.get("holder_acquisition_build") == FACT_SHARE_HOLDER_ACQUISITION_BUILD
                and FACT_SHARE_HOLDER_ACQUISITION_BUILD == V100_VALIDATION_BUILD
                and FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_AUTHORITY_RELATION_BUILD == "0.99.0-upchain-authority-relative-fact-sharing"
                and fact_holder_acquisition(informant, informant_fact) == "NONTRANSFERRED"
                and _candidate_ids(informant) == {mara_id},
                f"candidate={sorted(_candidate_ids(informant))} acquisition={fact_holder_acquisition(informant, informant_fact)}",
            )

            upsert_faction(_faction("NONTRANSFERRED"))
            sync_faction_fact_share_policies(informant)
            nontransferred = refresh_holder_aware_fact_share_obligations(informant)
            check(
                "nontransferred-policy-keeps-the-same-existing-first-hop-obligation-eligible",
                _candidate_ids(informant) == {mara_id}
                and not list(nontransferred.get("holder_acquisition_skipped") or [])
                and any(
                    str(row.get("obligation_id") or "") == mara_oid and row.get("created") is False
                    for row in list(nontransferred.get("materialized") or [])
                ),
                f"candidate={sorted(_candidate_ids(informant))}",
            )

            first_step = decision_step(informant, prepare_world_state=False)
            mara_fact = find_knowledge_fact(mara, TEST_FACT_ID)
            first_history = list((mara_fact or {}).get("transfer_history") or [])
            check(
                "first-local-transfer-preserves-original-provenance-and-classifies-recipient-holder-as-local-transfer",
                first_step.get("status") == "GOAL_COMPLETED"
                and mara_fact is not None
                and dict((mara_fact or {}).get("source") or {}) == dict(seeded.get("source") or {})
                and dict((mara_fact or {}).get("learned_by") or {}) == dict(seeded.get("learned_by") or {})
                and len(first_history) == 1
                and str((first_history[-1] or {}).get("target_npc_id") or "") == mara_id
                and fact_holder_acquisition(mara, mara_fact) == "LOCAL_TRANSFER",
                f"status={first_step.get('status')} acquisition={fact_holder_acquisition(mara, mara_fact)} history={first_history}",
            )

            sync_faction_fact_share_policies(mara)
            blocked = refresh_holder_aware_fact_share_obligations(mara)
            mismatch_rows = [
                row for row in list(blocked.get("holder_acquisition_skipped") or [])
                if row.get("reason") == "HOLDER_ACQUISITION_MISMATCH"
            ]
            check(
                "nontransferred-policy-blocks-a-socially-received-holder-before-any-second-hop-materializes",
                not _candidate_ids(mara)
                and not list(blocked.get("materialized") or [])
                and len(mismatch_rows) == 1
                and mismatch_rows[0].get("requested") == "NONTRANSFERRED"
                and mismatch_rows[0].get("actual") == "LOCAL_TRANSFER",
                f"skipped={mismatch_rows} candidates={sorted(_candidate_ids(mara))}",
            )

            upsert_faction(_faction("LOCAL_TRANSFER"))
            sync_faction_fact_share_policies(mara)
            received_ok = refresh_holder_aware_fact_share_obligations(mara)
            worker_obligation = _find_obligation(mara, worker_id)
            check(
                "local-transfer-policy-opens-the-next-upchain-branch-for-a-socially-received-holder",
                _candidate_ids(mara) == {worker_id}
                and worker_obligation is not None
                and worker_obligation.get("active") is True
                and any(str(row.get("obligation_id") or "") == worker_oid for row in list(received_ok.get("materialized") or [])),
                f"candidates={sorted(_candidate_ids(mara))} obligation={worker_obligation}",
            )

            upsert_faction(_faction("RUMOR"))
            sync_faction_fact_share_policies(mara)
            malformed = refresh_holder_aware_fact_share_obligations(mara)
            cancelled_worker = _find_obligation(mara, worker_id)
            bad_rows = [
                row for row in list(malformed.get("holder_acquisition_skipped") or [])
                if row.get("reason") == "BAD_HOLDER_ACQUISITION"
            ]
            check(
                "malformed-holder-acquisition-fails-closed-and-cancels-existing-pending-branch",
                len(bad_rows) == 1
                and cancelled_worker is not None
                and cancelled_worker.get("active") is False
                and cancelled_worker.get("status") == "cancelled"
                and cancelled_worker.get("cancellation_reason") == "BAD_HOLDER_ACQUISITION"
                and not _candidate_ids(mara),
                f"skipped={bad_rows} obligation={cancelled_worker}",
            )

            upsert_faction(_faction("LOCAL_TRANSFER"))
            sync_faction_fact_share_policies(mara)
            repaired = refresh_holder_aware_fact_share_obligations(mara)
            repaired_worker = _find_obligation(mara, worker_id)
            check(
                "correcting-holder-acquisition-reactivates-the-same-worker-obligation-id-without-duplication",
                repaired_worker is not None
                and repaired_worker.get("active") is True
                and repaired_worker.get("status") == "pending"
                and any(
                    str(row.get("obligation_id") or "") == worker_oid and row.get("created") is False
                    for row in list(repaired.get("materialized") or [])
                ),
                f"obligation={repaired_worker}",
            )

            second_step = decision_step(mara, prepare_world_state=False)
            worker_fact = find_knowledge_fact(worker, TEST_FACT_ID)
            history = list((worker_fact or {}).get("transfer_history") or [])
            check(
                "second-local-transfer-preserves-two-hop-history-and-classifies-the-new-holder-as-local-transfer",
                second_step.get("status") == "GOAL_COMPLETED"
                and worker_fact is not None
                and len(history) == 2
                and str((history[0] or {}).get("source_npc_id") or "") == informant_id
                and str((history[0] or {}).get("target_npc_id") or "") == mara_id
                and str((history[1] or {}).get("source_npc_id") or "") == mara_id
                and str((history[1] or {}).get("target_npc_id") or "") == worker_id
                and fact_holder_acquisition(worker, worker_fact) == "LOCAL_TRANSFER",
                f"status={second_step.get('status')} acquisition={fact_holder_acquisition(worker, worker_fact)} history={history}",
            )

            sync_faction_fact_share_policies(worker)
            top_refresh = refresh_holder_aware_fact_share_obligations(worker)
            check(
                "top-authority-still-stops-naturally-after-holder-acquisition-gate-passes",
                fact_holder_acquisition(worker, worker_fact) == "LOCAL_TRANSFER"
                and not _candidate_ids(worker)
                and not list(top_refresh.get("materialized") or []),
                f"candidates={sorted(_candidate_ids(worker))} refresh={top_refresh.get('status')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            registry.db.factions = original["registry_factions"]
            for name, npc in (("informant", informant), ("mara", mara), ("worker", worker)):
                state = original["npcs"][name]
                try:
                    if npc.location != state["location"]:
                        npc.move_to(state["location"], quiet=True)
                except Exception:
                    pass
                npc.db.knowledge = state["knowledge"]
                npc.db.knowledge_facts = state["facts"]
                npc.db.relationships = state["relationships"]
                npc.db.fact_share_rules = state["rules"]
                npc.db.fact_share_obligation_sources = state["sources"]
                npc.db.faction_memberships = state["memberships"]
                npc.db.decision_enabled = state["decision_enabled"]
                npc.db.current_goal = state["current_goal"]
                npc.db.destination_id = state["destination_id"]
                npc.db.current_activity = state["current_activity"]

        self.caller.msg("")
        self.caller.msg(f"RESULT: {sum(1 for value in results if value)}/{len(results)} PASS")
        self.caller.msg("")
        self.caller.msg(
            "STATE RESTORED: faction registry plus Informant/Mara/Worker locations, memberships, Knowledge/Facts, rules, relationships, source-index and decision state restored exactly"
        )
        self.caller.msg("")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: original Fact source/learned_by remain immutable provenance; v1.00 only gates social rule eligibility from current-holder DIRECT_LOCAL transfer history before v0.89-v0.99 refresh"
        )
        self.caller.msg("")
        self.caller.msg("========================================================")
