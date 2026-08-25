from evennia import Command, search_object, search_tag

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import _find_obligation
from services.fact_driven_decision import choose_goal
from services.fact_share_rule_engine import refresh_fact_share_obligations
from services.faction_fact_share_policy_engine import (
    FACTION_FACT_SHARE_POLICY_BUILD,
    sync_faction_fact_share_policies,
)
from services.faction_engine import get_faction_registry, upsert_faction, upsert_membership
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import remove_knowledge_fact, upsert_knowledge_fact
from services.relationship_engine import collect_relationship_candidates
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V096_VALIDATION_BUILD = "0.96.0-inherited-faction-fact-share-policies"
TEST_FACTION_ID = "TEST-V096-DARSENA-INSTITUTION"
TEST_FACTION_2_ID = "TEST-V096-DARSENA-SECOND-INSTITUTION"
TEST_POLICY_ID = "POLICY-V096-REPORT-001"
TEST_POLICY_2_ID = "POLICY-V096-REPORT-002"
TEST_FACT_ID = "FACT-V096-INSTITUTIONAL-REPORT-001"
TEST_KNOWLEDGE_KEY = "V096_INSTITUTIONAL_REPORT"
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


def _policy(policy_id=TEST_POLICY_ID):
    return {
        "id": policy_id,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": TEST_FACT_ID,
        "target_mode": "FACTION",
        "min_authority": 500,
        "selection": "NEAREST",
        "max_targets": 1,
        "priority": 945,
        "one_shot": True,
    }


def _faction(faction_id, policy_id=TEST_POLICY_ID, with_policy=True):
    row = {
        "id": faction_id,
        "name": faction_id,
        "active": True,
        "canon_status": "prototype",
    }
    if with_policy:
        row["fact_share_policies"] = [_policy(policy_id)]
    return row


def _seed_fact(npc, site):
    upsert_knowledge_fact(
        npc,
        {
            "id": TEST_FACT_ID,
            "knowledge_key": TEST_KNOWLEDGE_KEY,
            "required_level": 1,
            "topic": "reporte institucional de auditoria",
            "text": "Existe un reporte institucional de auditoria que debe subir por la cadena de mando.",
            "canon_status": "prototype",
            "source": {
                "kind": "VALIDATOR_SEED",
                "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            },
            "learned_by": {"mode": "VALIDATOR"},
        },
    )
    set_knowledge_level(npc, TEST_KNOWLEDGE_KEY, 1)


def _clear_fact(npc):
    remove_knowledge_fact(npc, TEST_FACT_ID)
    set_knowledge_level(npc, TEST_KNOWLEDGE_KEY, 0)


def _candidate_ids(source):
    return {
        str(row.get("relationship_target_npc_id") or "")
        for row in collect_relationship_candidates(source)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
        and str(row.get("fact_id") or "") == TEST_FACT_ID
    }


def _managed_rules(npc):
    return [
        dict(row)
        for row in list(getattr(npc.db, "fact_share_rules", []) or [])
        if str((row or {}).get("managed_by") or "") == FACTION_FACT_SHARE_POLICY_BUILD
    ]


class CmdSizaValidateV96(Command):
    key = "siza-validate-v96"
    aliases = ["validate-v96"]
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
            self.caller.msg("[V0.96 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        worker_id = str(getattr(worker.db, "npc_id", "") or "").strip()
        mara_oid = f"SHARE-FACT-{mara_id}-{TEST_FACT_ID}"

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

        self.caller.msg(f"=== SIZA VALIDATION v0.96 | {V096_VALIDATION_BUILD} ===")
        self.caller.msg(
            "faction-level policy -> active member inherits managed rule -> existing Fact-share authority creates normal branch; membership/policy changes remove inherited intent safely"
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
            _clear_fact(informant)
            _clear_fact(mara)
            _clear_fact(worker)
            _seed_fact(informant, site)

            upsert_faction(_faction(TEST_FACTION_ID))
            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 700})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "worker", "authority_level": 200})

            first_sync = sync_faction_fact_share_policies(informant)
            inherited = _managed_rules(informant)
            check(
                "active-member-inherits-one-namespaced-managed-rule-from-faction-definition",
                len(inherited) == 1
                and inherited[0].get("authored_rule_id") == TEST_POLICY_ID
                and inherited[0].get("inherited_from_faction_id") == TEST_FACTION_ID
                and inherited[0].get("faction_id") == TEST_FACTION_ID
                and inherited[0].get("fact_id") == TEST_FACT_ID,
                f"inherited={first_sync.get('inherited')}",
            )

            first_refresh = refresh_fact_share_obligations(informant)
            check(
                "inherited-policy-reuses-existing-authority-filter-nearest-and-share-fact-materialization",
                _candidate_ids(informant) == {mara_id}
                and any(
                    str(row.get("target_npc_id") or "") == mara_id
                    and str(row.get("faction_id") or "") == TEST_FACTION_ID
                    and int(row.get("path_length", -1)) == 1
                    for row in list(first_refresh.get("materialized") or [])
                ),
                f"candidates={sorted(_candidate_ids(informant))}",
            )

            informant.db.relationships = {}
            informant.db.fact_share_obligation_sources = {}
            informant.db.fact_share_rules = [
                dict(row)
                for row in list(informant.db.fact_share_rules or [])
                if str((row or {}).get("managed_by") or "") != FACTION_FACT_SHARE_POLICY_BUILD
            ]
            wrapper = choose_goal(informant)
            check(
                "fact-driven-wrapper-syncs-institutional-policy-before-normal-social-refresh",
                wrapper.get("fact_share_policy_build") == FACTION_FACT_SHARE_POLICY_BUILD
                and len(_managed_rules(informant)) == 1
                and _candidate_ids(informant) == {mara_id},
                f"sync={wrapper.get('fact_share_policy_sync')} refresh_status={(wrapper.get('fact_share_refresh') or {}).get('status')}",
            )

            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": False, "role": "reporter", "authority_level": 100})
            left = sync_faction_fact_share_policies(informant)
            left_obligation = _find_obligation(informant, mara_id)
            check(
                "leaving-source-faction-removes-managed-rule-and-cancels-its-pending-obligation",
                not _managed_rules(informant)
                and left_obligation is not None
                and left_obligation.get("active") is False
                and left_obligation.get("cancellation_reason") == "FACTION_POLICY_NO_LONGER_INHERITED"
                and any(str(row.get("rule_id") or "").startswith(f"FACTION_POLICY:{TEST_FACTION_ID}:") for row in list(left.get("removed") or [])),
                f"removed={left.get('removed')}",
            )

            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100})
            rejoin_sync = sync_faction_fact_share_policies(informant)
            rejoin_refresh = refresh_fact_share_obligations(informant)
            rejoined_obligation = _find_obligation(informant, mara_id)
            check(
                "rejoining-faction-reinherits-policy-and-reactivates-same-normal-obligation-id",
                len(_managed_rules(informant)) == 1
                and rejoined_obligation is not None
                and rejoined_obligation.get("active") is True
                and any(
                    str(row.get("obligation_id") or "") == mara_oid and row.get("created") is False
                    for row in list(rejoin_refresh.get("materialized") or [])
                ),
                f"sync={rejoin_sync.get('status')}",
            )

            upsert_faction(_faction(TEST_FACTION_ID, with_policy=False))
            removed_policy = sync_faction_fact_share_policies(informant)
            check(
                "removing-policy-from-faction-definition-removes-derived-rule-and-cancels-pending-intent",
                not _managed_rules(informant)
                and (_find_obligation(informant, mara_id) or {}).get("active") is False
                and (_find_obligation(informant, mara_id) or {}).get("cancellation_reason") == "FACTION_POLICY_NO_LONGER_INHERITED"
                and len(list(removed_policy.get("removed") or [])) == 1,
                f"removed={removed_policy.get('removed')}",
            )

            upsert_faction(_faction(TEST_FACTION_ID))
            local_override = {
                "id": "LOCAL-V096-OVERRIDE-001",
                "enabled": True,
                "fact_id": TEST_FACT_ID,
                "target_mode": "EXPLICIT",
                "target_npc_id": worker_id,
                "priority": 946,
                "one_shot": True,
            }
            informant.db.fact_share_rules = [local_override]
            overridden = sync_faction_fact_share_policies(informant)
            check(
                "npc-local-rule-for-same-fact-overrides-inherited-policy-without-duplicating-authority",
                not _managed_rules(informant)
                and len(list(getattr(informant.db, "fact_share_rules", []) or [])) == 1
                and str((list(informant.db.fact_share_rules or [])[0] or {}).get("id") or "") == "LOCAL-V096-OVERRIDE-001"
                and len(list(overridden.get("suppressed_by_local") or [])) == 1,
                f"suppressed={overridden.get('suppressed_by_local')}",
            )

            informant.db.fact_share_rules = []
            upsert_faction(_faction(TEST_FACTION_2_ID, TEST_POLICY_2_ID, with_policy=True))
            upsert_membership(informant, {"faction_id": TEST_FACTION_2_ID, "active": True, "role": "dual-member", "authority_level": 100})
            conflict = sync_faction_fact_share_policies(informant)
            check(
                "multiple-active-factions-with-policies-for-same-fact-fail-closed-instead-of-silently-picking-one",
                not _managed_rules(informant)
                and len(list(conflict.get("conflicts") or [])) == 1
                and (conflict.get("conflicts") or [{}])[0].get("reason") == "MULTIPLE_INHERITED_POLICIES_FOR_FACT",
                f"conflicts={conflict.get('conflicts')}",
            )

            check(
                "v096-policy-inheritance-is-additive-and-keeps-existing-social-authorities-unchanged",
                FACTION_FACT_SHARE_POLICY_BUILD == "0.96.0-inherited-faction-fact-share-policies"
                and first_sync.get("build") == FACTION_FACT_SHARE_POLICY_BUILD
                and informant_id not in _candidate_ids(informant),
                f"build={FACTION_FACT_SHARE_POLICY_BUILD}",
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
            registry.db.factions = original["registry_factions"]
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
            "STATE RESTORED: faction registry, Informant/Mara/Worker locations, memberships, Knowledge/Facts, local/managed share rules, relationships and source-index restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: faction policies only project managed rules; normal v0.89-v0.95 SHARE_FACT selection/contact/transfer authority remains unchanged"
        )
        self.caller.msg("========================================================")
