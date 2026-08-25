from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v96_commands import (
    TEST_FACT_ID,
    TEST_FACTION_ID,
    TEST_POLICY_ID,
    WORKER_B_NPC_ID,
    _clear_fact,
    _faction,
    _npc_by_id,
    _seed_fact,
)
from services.faction_fact_share_policy_engine import (
    FACTION_FACT_SHARE_POLICY_BUILD,
    sync_faction_fact_share_policies,
)
from services.fact_share_rule_engine import refresh_fact_share_obligations
from services.faction_engine import get_faction_registry, upsert_faction, upsert_membership
from services.relationship_engine import inspect_relationships
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V0961_VALIDATION_BUILD = "0.96.1-targeted-inherited-policy-obligation-lifecycle"


def _find_fact_obligation(source, target_npc_id, fact_id):
    wanted = f"SHARE-FACT-{str(target_npc_id)}-{str(fact_id)}"
    for row in inspect_relationships(source):
        if str(row.get("target_npc_id") or "") != str(target_npc_id):
            continue
        for obligation in list(row.get("obligations") or []):
            if str((obligation or {}).get("id") or "") == wanted:
                return dict(obligation)
    return None


def _managed_rules(npc):
    return [
        dict(row)
        for row in list(getattr(npc.db, "fact_share_rules", []) or [])
        if str((row or {}).get("managed_by") or "") == FACTION_FACT_SHARE_POLICY_BUILD
    ]


class CmdSizaValidateV961(Command):
    key = "siza-validate-v961"
    aliases = ["validate-v961"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        informant = install.get("informant") if install.get("success") else None
        mara = install.get("mara") if install.get("success") else None
        worker = _npc_by_id(WORKER_B_NPC_ID)
        site = install.get("site") if install.get("success") else None
        registry = get_faction_registry(create=True)
        if not informant or not mara or not worker or not site or registry is None:
            self.caller.msg("[V0.96.1 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        wanted_obligation_id = f"SHARE-FACT-{mara_id}-{TEST_FACT_ID}"

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
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.96.1 | {V0961_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted rerun: inspect the v0.96 Fact-specific SHARE_FACT obligation id instead of the v0.89 helper hard-coded to the v0.88 Fact"
        )

        try:
            informant.move_to(site, quiet=True)
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

            upsert_faction(_faction(TEST_FACTION_ID, TEST_POLICY_ID, with_policy=True))
            upsert_membership(
                informant,
                {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100},
            )
            upsert_membership(
                mara,
                {"faction_id": TEST_FACTION_ID, "active": True, "role": "officer", "authority_level": 700},
            )
            upsert_membership(
                worker,
                {"faction_id": TEST_FACTION_ID, "active": True, "role": "worker", "authority_level": 200},
            )

            sync_faction_fact_share_policies(informant)
            initial_refresh = refresh_fact_share_obligations(informant)
            initial = _find_fact_obligation(informant, mara_id, TEST_FACT_ID)
            if not initial or not initial.get("active"):
                raise RuntimeError(
                    f"baseline inherited obligation missing id={wanted_obligation_id} refresh={initial_refresh}"
                )

            upsert_membership(
                informant,
                {"faction_id": TEST_FACTION_ID, "active": False, "role": "reporter", "authority_level": 100},
            )
            left = sync_faction_fact_share_policies(informant)
            left_obligation = _find_fact_obligation(informant, mara_id, TEST_FACT_ID)
            check(
                "leaving-source-faction-cancels-the-exact-v096-obligation-and-removes-managed-rule",
                not _managed_rules(informant)
                and left_obligation is not None
                and left_obligation.get("active") is False
                and left_obligation.get("status") == "cancelled"
                and left_obligation.get("cancellation_reason") == "FACTION_POLICY_NO_LONGER_INHERITED"
                and any(
                    wanted_obligation_id
                    == str(cancelled.get("obligation_id") or "")
                    for removed in list(left.get("removed") or [])
                    for cancelled in list((removed or {}).get("cancelled_obligations") or [])
                ),
                f"obligation={left_obligation} removed={left.get('removed')}",
            )

            upsert_membership(
                informant,
                {"faction_id": TEST_FACTION_ID, "active": True, "role": "reporter", "authority_level": 100},
            )
            rejoin_sync = sync_faction_fact_share_policies(informant)
            rejoin_refresh = refresh_fact_share_obligations(informant)
            rejoined = _find_fact_obligation(informant, mara_id, TEST_FACT_ID)
            check(
                "rejoining-source-faction-reactivates-the-same-exact-v096-obligation-id",
                len(_managed_rules(informant)) == 1
                and rejoined is not None
                and rejoined.get("active") is True
                and rejoined.get("status") == "pending"
                and str(rejoined.get("id") or "") == wanted_obligation_id
                and any(
                    str(row.get("obligation_id") or "") == wanted_obligation_id
                    and row.get("created") is False
                    for row in list(rejoin_refresh.get("materialized") or [])
                ),
                f"sync={rejoin_sync.get('status')} obligation={rejoined}",
            )

            upsert_faction(_faction(TEST_FACTION_ID, TEST_POLICY_ID, with_policy=False))
            removed_policy = sync_faction_fact_share_policies(informant)
            removed_obligation = _find_fact_obligation(informant, mara_id, TEST_FACT_ID)
            check(
                "removing-faction-policy-cancels-the-exact-reactivated-v096-obligation",
                not _managed_rules(informant)
                and removed_obligation is not None
                and removed_obligation.get("active") is False
                and removed_obligation.get("status") == "cancelled"
                and removed_obligation.get("cancellation_reason") == "FACTION_POLICY_NO_LONGER_INHERITED"
                and any(
                    wanted_obligation_id
                    == str(cancelled.get("obligation_id") or "")
                    for removed in list(removed_policy.get("removed") or [])
                    for cancelled in list((removed or {}).get("cancelled_obligations") or [])
                ),
                f"obligation={removed_obligation} removed={removed_policy.get('removed')}",
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

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: faction registry, Informant/Mara/Worker memberships, Knowledge/Facts, managed rules, relationships and source-index restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.96 production unchanged; targeted QA now inspects the exact institutional Fact obligation identity"
        )
        self.caller.msg("========================================================")
