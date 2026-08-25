from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import (
    _find_obligation,
    _obligation_id,
    _remove_fact_knowledge,
    _remove_test_obligation,
    _target_room,
)
from commands.world_input_v90_commands import _candidate_for, _seed_known_fact
from services.fact_driven_decision import (
    FACT_DRIVEN_DECISION_BUILD,
    FACT_SHARE_DECISION_BUILD,
    choose_goal,
    decision_step,
)
from services.fact_share_rule_engine import (
    FACT_SHARE_RULE_BUILD,
    FACT_SHARE_SOURCE_AWARENESS_BUILD,
    FACT_SHARE_TARGET_AWARENESS_BUILD,
    refresh_fact_share_obligations,
)
from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import find_knowledge_fact
from world.upgrade_pilot_v88 import FACT_ID, KNOWLEDGE_KEY
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V091_VALIDATION_BUILD = "0.91.0-source-lost-fact-share-cancel-and-recover"


class CmdSizaValidateV91(Command):
    key = "siza-validate-v91"
    aliases = ["validate-v91"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.91 VALIDATION] FAIL | install={install}")
            return

        informant = install.get("informant")
        mara = install.get("mara")
        site = install.get("site")
        away = _target_room()
        if not informant or not mara or not site or not away:
            self.caller.msg("[V0.91 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        wanted_obligation = _obligation_id(mara_id)

        original_informant_location = informant.location
        original_mara_location = mara.location
        original_informant_knowledge = _clone(getattr(informant.db, "knowledge", {}))
        original_informant_facts = _clone(getattr(informant.db, "knowledge_facts", []))
        original_informant_relationships = _clone(getattr(informant.db, "relationships", {}))
        original_informant_current_goal = _clone(getattr(informant.db, "current_goal", None))
        original_informant_destination = getattr(informant.db, "destination_id", None)
        original_informant_activity = getattr(informant.db, "current_activity", None)
        original_informant_decision_enabled = getattr(informant.db, "decision_enabled", None)
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.91 | {V091_VALIDATION_BUILD} ===")
        self.caller.msg(
            "pending SHARE_FACT + source loses exact Fact -> obligation cancels before candidate collection -> no transfer; source relearns -> same obligation reactivates and can complete normally"
        )

        try:
            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != away:
                mara.move_to(away, quiet=True)
            informant.db.decision_enabled = True
            informant.db.current_goal = None
            informant.db.destination_id = None
            informant.db.current_activity = None

            _remove_fact_knowledge(informant)
            _remove_fact_knowledge(mara)
            _remove_test_obligation(informant, mara_id)
            _seed_known_fact(informant, site, "SITE_PRESENCE")

            first = refresh_fact_share_obligations(informant)
            pending = _find_obligation(informant, mara_id)
            first_candidate = _candidate_for(informant, wanted_obligation)
            check(
                "known-source-and-unknown-target-still-create-normal-pending-share-before-source-loss",
                any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    for row in list(first.get("materialized") or [])
                )
                and pending is not None
                and pending.get("active") is True
                and str(pending.get("status") or "") == "pending"
                and first_candidate is not None
                and find_knowledge_fact(mara, FACT_ID) is None,
                f"refresh={first.get('status')} candidate={first_candidate is not None}",
            )

            check(
                "historical-share-builds-remain-stable-with-v091-source-awareness-as-separate-capability",
                FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_DECISION_BUILD == "0.89.0-fact-driven-social-share-wrapper"
                and FACT_DRIVEN_DECISION_BUILD == "0.59.0-fact-driven-decision-wrapper"
                and first.get("target_awareness_build") == FACT_SHARE_TARGET_AWARENESS_BUILD
                and first.get("source_awareness_build") == FACT_SHARE_SOURCE_AWARENESS_BUILD,
                f"rule={FACT_SHARE_RULE_BUILD} target={first.get('target_awareness_build')} source={first.get('source_awareness_build')}",
            )

            _remove_fact_knowledge(informant)
            cancelled_refresh = refresh_fact_share_obligations(informant)
            cancelled = _find_obligation(informant, mara_id)
            cancelled_candidate = _candidate_for(informant, wanted_obligation)
            check(
                "pending-share-cancels-when-source-no-longer-knows-the-exact-fact",
                any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                    and row.get("cancelled_pending") is True
                    for row in list(cancelled_refresh.get("skipped") or [])
                )
                and cancelled is not None
                and cancelled.get("active") is False
                and str(cancelled.get("status") or "") == "cancelled"
                and cancelled.get("cancellation_reason") == "SOURCE_NO_LONGER_KNOWS_FACT"
                and cancelled_candidate is None
                and find_knowledge_fact(mara, FACT_ID) is None
                and int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0) == 0,
                f"refresh={cancelled_refresh.get('status')} obligation={None if cancelled is None else cancelled.get('status')}",
            )

            wrapped = choose_goal(informant)
            wrapped_refresh = dict(wrapped.get("fact_share_refresh") or {})
            wrapped_candidates = list(wrapped.get("candidates") or [])
            check(
                "fact-driven-wrapper-keeps-source-lost-share-out-of-underlying-decision-candidates-without-moving-or-transferring",
                any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                    for row in list(wrapped_refresh.get("skipped") or [])
                )
                and not any(
                    str(row.get("relationship_obligation_id") or "") == wanted_obligation
                    for row in wrapped_candidates
                )
                and informant.location == site
                and mara.location == away
                and find_knowledge_fact(mara, FACT_ID) is None,
                f"refresh={wrapped_refresh.get('status')} selected={(wrapped.get('selected') or {}).get('id')}",
            )

            _seed_known_fact(informant, site, "SITE_PRESENCE")
            recovered_refresh = refresh_fact_share_obligations(informant)
            recovered = _find_obligation(informant, mara_id)
            recovered_candidate = _candidate_for(informant, wanted_obligation)
            check(
                "relearning-source-fact-reactivates-the-same-obligation-id-without-duplicating-it",
                any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("created") is False
                    for row in list(recovered_refresh.get("materialized") or [])
                )
                and recovered is not None
                and recovered.get("active") is True
                and str(recovered.get("status") or "") == "pending"
                and recovered.get("cancellation_reason") is None
                and recovered.get("cancelled_at") is None
                and recovered_candidate is not None,
                f"refresh={recovered_refresh.get('status')} created={[(row or {}).get('created') for row in list(recovered_refresh.get('materialized') or [])]}",
            )

            step = decision_step(informant, prepare_world_state=False)
            mara_fact = find_knowledge_fact(mara, FACT_ID)
            history = list((mara_fact or {}).get("transfer_history") or [])
            transfer = history[-1] if history else {}
            completed = _find_obligation(informant, mara_id)
            check(
                "recovered-share-completes-through-existing-local-transfer-authority-after-physical-contact",
                step.get("status") == "GOAL_COMPLETED"
                and step.get("completion_source") == "RELATIONSHIP"
                and step.get("relationship_resolved") is True
                and str(step.get("relationship_obligation_id") or "") == wanted_obligation
                and informant.location == mara.location
                and mara_fact is not None
                and str(transfer.get("source_npc_id") or "") == informant_id
                and str(transfer.get("target_npc_id") or "") == mara_id
                and transfer.get("mode") == "DIRECT_LOCAL"
                and completed is not None
                and completed.get("active") is False
                and str(completed.get("status") or "") == "completed",
                f"status={step.get('status')} history={len(history)} obligation={None if completed is None else completed.get('status')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if informant.location != original_informant_location:
                    informant.move_to(original_informant_location, quiet=True)
            except Exception:
                pass
            try:
                if mara.location != original_mara_location:
                    mara.move_to(original_mara_location, quiet=True)
            except Exception:
                pass

            informant.db.knowledge = original_informant_knowledge
            informant.db.knowledge_facts = original_informant_facts
            informant.db.relationships = original_informant_relationships
            informant.db.current_goal = original_informant_current_goal
            informant.db.destination_id = original_informant_destination
            informant.db.current_activity = original_informant_activity
            informant.db.decision_enabled = original_informant_decision_enabled
            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara locations, Knowledge/Facts, Informant relationships and current decision state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.89 local SHARE_FACT transfer and v0.90 target-aware pruning remain unchanged; v0.91 only cancels source-invalid pending shares and permits later reactivation after relearning"
        )
        self.caller.msg("========================================================")
