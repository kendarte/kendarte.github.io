from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v101_commands import (
    FACT_ID,
    GOAL_ID,
    GOAL_RULE_ID,
    SHARE_RULE_ID,
    _candidate_ids,
    _find_obligation,
    _seed_fact,
)
from services.fact_goal_engine import find_decision_goal, refresh_fact_driven_goals, upsert_fact_goal_rule
from services.fact_share_holder_acquisition_engine import refresh_holder_aware_fact_share_obligations
from services.fact_share_rule_engine import upsert_fact_share_rule
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V1011_VALIDATION_BUILD = "1.01.1-targeted-decision-enabled-baseline-contract"


class CmdSizaValidateV1011(Command):
    key = "siza-validate-v1011"
    aliases = ["validate-v1011"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        informant = install.get("informant") if install.get("success") else None
        mara = install.get("mara") if install.get("success") else None
        site = install.get("site") if install.get("success") else None
        if not informant or not mara or not site:
            self.caller.msg("[V1.01.1 VALIDATION] FAIL | persistent context missing")
            return

        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        obligation_id = f"SHARE-FACT-{mara_id}-{FACT_ID}"
        original = {}
        for name, npc in (("informant", informant), ("mara", mara)):
            original[name] = {
                "location": npc.location,
                "knowledge": _clone(getattr(npc.db, "knowledge", {})),
                "facts": _clone(getattr(npc.db, "knowledge_facts", [])),
                "relationships": _clone(getattr(npc.db, "relationships", {})),
                "rules": _clone(getattr(npc.db, "fact_share_rules", [])),
                "sources": _clone(getattr(npc.db, "fact_share_obligation_sources", {})),
                "goal_rules": _clone(getattr(npc.db, "fact_goal_rules", [])),
                "goals": _clone(getattr(npc.db, "decision_goals", [])),
                "decision_enabled": getattr(npc.db, "decision_enabled", None),
                "current_goal": _clone(getattr(npc.db, "current_goal", None)),
                "destination_id": getattr(npc.db, "destination_id", None),
                "current_activity": getattr(npc.db, "current_activity", None),
            }

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v1.01.1 | {V1011_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted rerun: v1.01 baseline must control decision_enabled because relationship candidate collection intentionally returns no candidates for disabled NPC decisions"
        )

        try:
            informant.move_to(site, quiet=True)
            mara.move_to(site, quiet=True)
            for npc in (informant, mara):
                npc.db.knowledge = {}
                npc.db.knowledge_facts = []
                npc.db.relationships = {}
                npc.db.fact_share_rules = []
                npc.db.fact_share_obligation_sources = {}
                npc.db.fact_goal_rules = []
                npc.db.decision_goals = []
                npc.db.decision_enabled = True
                npc.db.current_goal = None
                npc.db.destination_id = None
                npc.db.current_activity = None

            _seed_fact(informant, site)
            upsert_fact_share_rule(
                informant,
                {
                    "id": SHARE_RULE_ID,
                    "enabled": True,
                    "fact_id": FACT_ID,
                    "target_mode": "EXPLICIT",
                    "target_npc_id": mara_id,
                    "priority": 1001,
                    "one_shot": True,
                },
            )
            upsert_fact_goal_rule(
                informant,
                {
                    "id": GOAL_RULE_ID,
                    "enabled": True,
                    "fact_id": FACT_ID,
                    "goal": {
                        "id": GOAL_ID,
                        "type": "OBSERVE",
                        "priority": 1001,
                        "active": True,
                        "canon_status": "prototype",
                    },
                },
            )

            goal_refresh = refresh_fact_driven_goals(informant)
            social_refresh = refresh_holder_aware_fact_share_obligations(informant)
            goal = find_decision_goal(informant, GOAL_ID)
            obligation = _find_obligation(informant, mara_id)
            candidates = _candidate_ids(informant)

            check(
                "active-fact-materializes-the-historical-fact-derived-goal-under-controlled-decision-state",
                GOAL_ID in list(goal_refresh.get("materialized") or [])
                and goal is not None
                and goal.get("active") is True,
                f"materialized={goal_refresh.get('materialized')} goal={goal}",
            )
            check(
                "active-fact-materializes-the-historical-share-fact-obligation-with-exact-identity",
                any(str(row.get("obligation_id") or "") == obligation_id for row in list(social_refresh.get("materialized") or []))
                and obligation is not None
                and obligation.get("active") is True
                and str(obligation.get("status") or "") == "pending",
                f"materialized={social_refresh.get('materialized')} obligation={obligation}",
            )
            check(
                "decision-enabled-source-exposes-the-exact-share-fact-relationship-candidate",
                bool(informant.db.decision_enabled)
                and candidates == {mara_id},
                f"decision_enabled={bool(informant.db.decision_enabled)} candidates={sorted(candidates)}",
            )
        finally:
            for name, npc in (("informant", informant), ("mara", mara)):
                state = original[name]
                npc.move_to(state["location"], quiet=True)
                npc.db.knowledge = state["knowledge"]
                npc.db.knowledge_facts = state["facts"]
                npc.db.relationships = state["relationships"]
                npc.db.fact_share_rules = state["rules"]
                npc.db.fact_share_obligation_sources = state["sources"]
                npc.db.fact_goal_rules = state["goal_rules"]
                npc.db.decision_goals = state["goals"]
                npc.db.decision_enabled = state["decision_enabled"]
                npc.db.current_goal = state["current_goal"]
                npc.db.destination_id = state["destination_id"]
                npc.db.current_activity = state["current_activity"]

        passed = sum(1 for value in results if value)
        self.caller.msg(f"RESULT: {passed}/{len(results)} PASS")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara locations, Knowledge/Facts, relationships, rules/goals, decision_enabled and current decision state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v1.01 production unchanged; the original 9/10 failure came from validator setup not controlling decision_enabled before calling collect_relationship_candidates"
        )
        self.caller.msg("========================================================")
