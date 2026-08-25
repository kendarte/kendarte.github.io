from evennia import Command, search_object, search_tag

from commands.world_input_v74_commands import _clone
from services.fact_share_rule_engine import refresh_fact_share_obligations
from services.faction_fact_share_policy_engine import (
    FACTION_FACT_SHARE_POLICY_BUILD,
    FACTION_FACT_TYPE_POLICY_BUILD,
    sync_faction_fact_share_policies,
)
from services.faction_engine import get_faction_registry, upsert_faction, upsert_membership
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import remove_knowledge_fact, upsert_knowledge_fact
from services.relationship_engine import inspect_relationships
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V097_VALIDATION_BUILD = "0.97.0-fact-type-inherited-faction-policies"
TEST_FACTION_ID = "TEST-V097-DARSENA-INSTITUTION"
TEST_FACTION_2_ID = "TEST-V097-DARSENA-SECOND-INSTITUTION"
TYPE_POLICY_ID = "POLICY-V097-SECURITY-TYPE-001"
EXACT_POLICY_ID = "POLICY-V097-EXACT-001"
SECOND_TYPE_POLICY_ID = "POLICY-V097-SECURITY-TYPE-002"
FACT_TYPE = "SECURITY_INCIDENT"
FACT_A = "FACT-V097-SECURITY-A-001"
FACT_B = "FACT-V097-SECURITY-B-001"
FACT_OTHER = "FACT-V097-OTHER-001"
FACT_EXACT = "FACT-V097-EXACT-001"
KEY_A = "V097_SECURITY_A"
KEY_B = "V097_SECURITY_B"
KEY_OTHER = "V097_OTHER"
KEY_EXACT = "V097_EXACT"
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


def _type_policy(policy_id=TYPE_POLICY_ID):
    return {
        "id": policy_id,
        "enabled": True,
        "canon_status": "prototype",
        "fact_type": FACT_TYPE,
        "target_mode": "FACTION",
        "min_authority": 500,
        "selection": "NEAREST",
        "max_targets": 1,
        "priority": 947,
        "one_shot": True,
    }


def _exact_policy():
    return {
        "id": EXACT_POLICY_ID,
        "enabled": True,
        "canon_status": "prototype",
        "fact_id": FACT_EXACT,
        "target_mode": "FACTION",
        "min_authority": 500,
        "selection": "NEAREST",
        "max_targets": 1,
        "priority": 946,
        "one_shot": True,
    }


def _faction(faction_id, policies):
    return {
        "id": faction_id,
        "name": faction_id,
        "active": True,
        "canon_status": "prototype",
        "fact_share_policies": list(policies),
    }


def _seed_fact(npc, site, fact_id, knowledge_key, fact_type, level):
    upsert_knowledge_fact(
        npc,
        {
            "id": fact_id,
            "knowledge_key": knowledge_key,
            "required_level": 1,
            "fact_type": fact_type,
            "topic": f"validator {fact_id}",
            "text": f"Validator Fact {fact_id}.",
            "canon_status": "prototype",
            "source": {
                "kind": "VALIDATOR_SEED",
                "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            },
            "learned_by": {"mode": "VALIDATOR"},
        },
    )
    set_knowledge_level(npc, knowledge_key, level)


def _remove_fact(npc, fact_id, knowledge_key):
    remove_knowledge_fact(npc, fact_id)
    set_knowledge_level(npc, knowledge_key, 0)


def _managed_rules(npc):
    return [
        dict(row)
        for row in list(getattr(npc.db, "fact_share_rules", []) or [])
        if str((row or {}).get("managed_by") or "") == FACTION_FACT_SHARE_POLICY_BUILD
    ]


def _managed_by_fact(npc):
    return {
        str(row.get("fact_id") or ""): dict(row)
        for row in _managed_rules(npc)
        if str(row.get("fact_id") or "")
    }


def _obligation(source, target_id, fact_id):
    wanted = f"SHARE-FACT-{target_id}-{fact_id}"
    for relation in inspect_relationships(source):
        if str(relation.get("target_npc_id") or "") != str(target_id):
            continue
        for raw in list(relation.get("obligations") or []):
            item = dict(raw or {})
            if str(item.get("id") or "") == wanted:
                return item
    return None


def _materialized_for(packet, fact_id):
    return [
        dict(row)
        for row in list((packet or {}).get("materialized") or [])
        if str((row or {}).get("fact_id") or "") == str(fact_id)
    ]


class CmdSizaValidateV97(Command):
    key = "siza-validate-v97"
    aliases = ["validate-v97"]
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
            self.caller.msg("[V0.97 VALIDATION] FAIL | persistent context missing")
            return

        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        type_a_rule_id = f"FACTION_POLICY:{TEST_FACTION_ID}:{TYPE_POLICY_ID}:FACT:{FACT_A}"
        type_b_rule_id = f"FACTION_POLICY:{TEST_FACTION_ID}:{TYPE_POLICY_ID}:FACT:{FACT_B}"
        exact_rule_id = f"FACTION_POLICY:{TEST_FACTION_ID}:{EXACT_POLICY_ID}"
        a_obligation_id = f"SHARE-FACT-{mara_id}-{FACT_A}"
        b_obligation_id = f"SHARE-FACT-{mara_id}-{FACT_B}"

        original = {
            "registry_factions": _clone(getattr(registry.db, "factions", {})),
            "informant_location": informant.location,
            "mara_location": mara.location,
            "worker_location": worker.location,
            "informant_knowledge": _clone(getattr(informant.db, "knowledge", {})),
            "informant_facts": _clone(getattr(informant.db, "knowledge_facts", [])),
            "informant_rules": _clone(getattr(informant.db, "fact_share_rules", [])),
            "informant_sources": _clone(getattr(informant.db, "fact_share_obligation_sources", {})),
            "informant_relationships": _clone(getattr(informant.db, "relationships", {})),
            "informant_memberships": _clone(getattr(informant.db, "faction_memberships", [])),
            "mara_memberships": _clone(getattr(mara.db, "faction_memberships", [])),
            "worker_memberships": _clone(getattr(worker.db, "faction_memberships", [])),
            "informant_decision_enabled": getattr(informant.db, "decision_enabled", None),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.97 | {V097_VALIDATION_BUILD} ===")
        self.caller.msg(
            "one faction fact_type policy -> exact managed rule per stored matching Fact -> existing source Knowledge and SHARE_FACT authority remain exact per fact_id"
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

            for fact_id, key in (
                (FACT_A, KEY_A),
                (FACT_B, KEY_B),
                (FACT_OTHER, KEY_OTHER),
                (FACT_EXACT, KEY_EXACT),
            ):
                _remove_fact(informant, fact_id, key)
            _seed_fact(informant, site, FACT_A, KEY_A, FACT_TYPE, 1)
            _seed_fact(informant, site, FACT_B, KEY_B, FACT_TYPE, 0)
            _seed_fact(informant, site, FACT_OTHER, KEY_OTHER, "OTHER_REPORT", 1)
            _seed_fact(informant, site, FACT_EXACT, KEY_EXACT, "LEGACY_EXACT", 0)

            upsert_faction(_faction(TEST_FACTION_ID, [_type_policy(), _exact_policy()]))
            upsert_membership(informant, {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100})
            upsert_membership(mara, {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 700})
            upsert_membership(worker, {"faction_id": TEST_FACTION_ID, "active": True, "role": "worker", "authority_level": 200})

            first_sync = sync_faction_fact_share_policies(informant)
            by_fact = _managed_by_fact(informant)
            exact_rule = by_fact.get(FACT_EXACT) or {}
            check(
                "v096-exact-fact-policy-keeps-its-historical-rule-id-and-selector-contract",
                str(exact_rule.get("id") or "") == exact_rule_id
                and exact_rule.get("fact_selector_mode") == "EXACT"
                and first_sync.get("build") == FACTION_FACT_SHARE_POLICY_BUILD,
                f"rule={exact_rule.get('id')} selector={exact_rule.get('fact_selector_mode')}",
            )

            check(
                "one-fact-type-policy-expands-to-one-exact-managed-rule-per-stored-matching-fact-only",
                set(by_fact) == {FACT_A, FACT_B, FACT_EXACT}
                and str((by_fact.get(FACT_A) or {}).get("id") or "") == type_a_rule_id
                and str((by_fact.get(FACT_B) or {}).get("id") or "") == type_b_rule_id
                and (by_fact.get(FACT_A) or {}).get("fact_selector_mode") == "TYPE"
                and (by_fact.get(FACT_B) or {}).get("authored_fact_type") == FACT_TYPE
                and first_sync.get("fact_type_policy_build") == FACTION_FACT_TYPE_POLICY_BUILD,
                f"facts={sorted(by_fact)} build={first_sync.get('fact_type_policy_build')}",
            )

            first_refresh = refresh_fact_share_obligations(informant)
            check(
                "typed-policy-keeps-source-knowledge-authority-exact-so-only-currently-known-matching-fact-materializes",
                bool(_materialized_for(first_refresh, FACT_A))
                and not _materialized_for(first_refresh, FACT_B)
                and (_obligation(informant, mara_id, FACT_A) or {}).get("active") is True
                and _obligation(informant, mara_id, FACT_B) is None,
                f"A={_materialized_for(first_refresh, FACT_A)} B={_materialized_for(first_refresh, FACT_B)}",
            )

            set_knowledge_level(informant, KEY_B, 1)
            second_refresh = refresh_fact_share_obligations(informant)
            check(
                "raising-knowledge-for-second-matching-fact-activates-its-own-exact-branch-without-changing-policy",
                any(str(row.get("obligation_id") or "") == b_obligation_id for row in _materialized_for(second_refresh, FACT_B))
                and (_obligation(informant, mara_id, FACT_B) or {}).get("active") is True
                and str((_managed_by_fact(informant).get(FACT_B) or {}).get("id") or "") == type_b_rule_id,
                f"materialized={_materialized_for(second_refresh, FACT_B)}",
            )

            _remove_fact(informant, FACT_A, KEY_A)
            removed_a = sync_faction_fact_share_policies(informant)
            after_remove = _managed_by_fact(informant)
            a_cancelled = _obligation(informant, mara_id, FACT_A)
            check(
                "removing-one-matching-fact-removes-only-its-derived-rule-and-cancels-only-that-fact-branch",
                FACT_A not in after_remove
                and FACT_B in after_remove
                and a_cancelled is not None
                and a_cancelled.get("active") is False
                and a_cancelled.get("cancellation_reason") == "FACTION_POLICY_NO_LONGER_INHERITED"
                and any(str(row.get("rule_id") or "") == type_a_rule_id for row in list(removed_a.get("removed") or [])),
                f"remaining={sorted(after_remove)} removed={removed_a.get('removed')}",
            )

            _seed_fact(informant, site, FACT_A, KEY_A, FACT_TYPE, 1)
            readded_sync = sync_faction_fact_share_policies(informant)
            readded_refresh = refresh_fact_share_obligations(informant)
            a_reactivated = _obligation(informant, mara_id, FACT_A)
            check(
                "readding-same-typed-fact-reuses-same-derived-rule-and-normal-obligation-identities",
                str((_managed_by_fact(informant).get(FACT_A) or {}).get("id") or "") == type_a_rule_id
                and a_reactivated is not None
                and a_reactivated.get("active") is True
                and any(
                    str(row.get("obligation_id") or "") == a_obligation_id and row.get("created") is False
                    for row in _materialized_for(readded_refresh, FACT_A)
                )
                and readded_sync.get("status") == "SYNCED",
                f"obligation={a_reactivated}",
            )

            local_override = {
                "id": "LOCAL-V097-B-OVERRIDE",
                "enabled": True,
                "fact_id": FACT_B,
                "target_mode": "EXPLICIT",
                "target_npc_id": mara_id,
                "priority": 950,
                "one_shot": True,
            }
            informant.db.fact_share_rules = [local_override] + _managed_rules(informant)
            overridden = sync_faction_fact_share_policies(informant)
            overridden_by_fact = _managed_by_fact(informant)
            check(
                "local-rule-overrides-only-the-concrete-matching-fact-not-the-entire-fact-type-policy",
                FACT_B not in overridden_by_fact
                and FACT_A in overridden_by_fact
                and FACT_EXACT in overridden_by_fact
                and any(
                    str(row.get("fact_id") or "") == FACT_B and row.get("reason") == "LOCAL_RULE_OVERRIDE"
                    for row in list(overridden.get("suppressed_by_local") or [])
                ),
                f"managed={sorted(overridden_by_fact)} suppressed={overridden.get('suppressed_by_local')}",
            )

            informant.db.fact_share_rules = [
                row
                for row in list(informant.db.fact_share_rules or [])
                if str((row or {}).get("id") or "") != "LOCAL-V097-B-OVERRIDE"
            ]
            upsert_faction(_faction(TEST_FACTION_2_ID, [_type_policy(SECOND_TYPE_POLICY_ID)]))
            upsert_membership(informant, {"faction_id": TEST_FACTION_2_ID, "active": True, "role": "dual-member", "authority_level": 100})
            conflict = sync_faction_fact_share_policies(informant)
            conflict_facts = {str(row.get("fact_id") or "") for row in list(conflict.get("conflicts") or [])}
            check(
                "two-inherited-type-policies-that-match-the-same-concrete-facts-fail-closed-per-fact-id",
                {FACT_A, FACT_B}.issubset(conflict_facts)
                and all(
                    row.get("reason") == "MULTIPLE_INHERITED_POLICIES_FOR_FACT"
                    for row in list(conflict.get("conflicts") or [])
                    if str(row.get("fact_id") or "") in {FACT_A, FACT_B}
                )
                and FACT_A not in _managed_by_fact(informant)
                and FACT_B not in _managed_by_fact(informant),
                f"conflicts={conflict.get('conflicts')}",
            )

            upsert_membership(informant, {"faction_id": TEST_FACTION_2_ID, "active": False, "role": "dual-member", "authority_level": 100})
            ambiguous = _type_policy()
            ambiguous["fact_id"] = FACT_A
            upsert_faction(_faction(TEST_FACTION_ID, [ambiguous]))
            malformed = sync_faction_fact_share_policies(informant)
            check(
                "policy-with-both-fact-id-and-fact-type-fails-closed-instead-of-choosing-a-selector",
                not _managed_rules(informant)
                and any(row.get("reason") == "AMBIGUOUS_FACT_SELECTOR" for row in list(malformed.get("skipped") or []))
                and malformed.get("fact_type_policy_build") == FACTION_FACT_TYPE_POLICY_BUILD,
                f"skipped={malformed.get('skipped')}",
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
            informant.db.fact_share_rules = original["informant_rules"]
            informant.db.fact_share_obligation_sources = original["informant_sources"]
            informant.db.relationships = original["informant_relationships"]
            informant.db.faction_memberships = original["informant_memberships"]
            mara.db.faction_memberships = original["mara_memberships"]
            worker.db.faction_memberships = original["worker_memberships"]
            informant.db.decision_enabled = original["informant_decision_enabled"]

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: faction registry, Informant/Mara/Worker locations, memberships, Knowledge/Facts, managed/local rules, relationships and source-index restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.96 exact fact_id policy IDs remain stable; v0.97 only expands fact_type policies into exact per-Fact managed rules before existing v0.89-v0.95 authority"
        )
        self.caller.msg("========================================================")
