from evennia import Command, search_tag

from commands.world_input_v74_commands import _clone
from services.fact_goal_engine import (
    FACT_GOAL_BUILD,
    FACT_GOAL_LIFECYCLE_BUILD,
    LIFECYCLE_CANCELLATION_REASON,
    find_decision_goal,
    refresh_fact_driven_goals,
    upsert_fact_goal_rule,
)
from services.fact_share_holder_acquisition_engine import refresh_holder_aware_fact_share_obligations
from services.fact_share_rule_engine import FACT_SHARE_RULE_BUILD, upsert_fact_share_rule
from services.knowledge_context_engine import (
    FACT_LIFECYCLE_BUILD,
    FACT_STATUS_ACTIVE,
    FACT_STATUS_RETRACTED,
    FACT_STATUS_SUPERSEDED,
    fact_knowledge_state,
    knowledge_decision_modifiers,
    set_knowledge_level,
)
from services.knowledge_fact_engine import (
    KNOWLEDGE_FACT_BUILD,
    find_knowledge_fact,
    set_knowledge_fact_status,
    upsert_knowledge_fact,
)
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.knowledge_fact_transfer_engine import FACT_TRANSFER_BUILD, transfer_knowledge_fact
from services.npc_fact_disclosure_engine import _first_shareable_topic_fact
from services.relationship_engine import collect_relationship_candidates, inspect_relationships
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V101_VALIDATION_BUILD = "1.01.0-holder-local-fact-lifecycle-authority"
FACT_ID = "FACT-V101-LIFECYCLE-001"
REPLACEMENT_FACT_ID = "FACT-V101-LIFECYCLE-REPLACEMENT-001"
KNOWLEDGE_KEY = "V101_LIFECYCLE"
REPLACEMENT_KNOWLEDGE_KEY = "V101_LIFECYCLE_REPLACEMENT"
SHARE_RULE_ID = "FACT-SHARE-V101-LIFECYCLE-001"
GOAL_RULE_ID = "FACT-GOAL-V101-LIFECYCLE-001"
GOAL_ID = "GOAL-V101-LIFECYCLE-001"
TOPIC = "validator lifecycle manifest correction"


def _npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    for npc in search_tag("kalnaj_pilot_v03_entities", category="siza_entity"):
        if str(getattr(npc.db, "npc_id", "") or "").strip() == wanted:
            return npc
    return None


def _candidate_ids(source):
    return {
        str(row.get("relationship_target_npc_id") or "")
        for row in collect_relationship_candidates(source)
        if str(row.get("relationship_kind") or "") == "SHARE_FACT"
        and str(row.get("fact_id") or "") == FACT_ID
    }


def _find_obligation(source, target_id):
    wanted = f"SHARE-FACT-{str(target_id)}-{FACT_ID}"
    for relation in inspect_relationships(source):
        if str(relation.get("target_npc_id") or "") != str(target_id):
            continue
        for raw in list(relation.get("obligations") or []):
            row = dict(raw or {})
            if str(row.get("id") or "") == wanted:
                return row
    return None


def _seed_fact(entity, site, fact_id=FACT_ID, knowledge_key=KNOWLEDGE_KEY, text=None):
    packet = upsert_knowledge_fact(
        entity,
        {
            "id": fact_id,
            "knowledge_key": knowledge_key,
            "required_level": 1,
            "fact_type": "SECURITY_INCIDENT",
            "severity": 4,
            "topic": TOPIC if fact_id == FACT_ID else "validator lifecycle replacement",
            "text": text or f"Validator lifecycle Fact {fact_id}.",
            "response": text or f"Validator lifecycle Fact {fact_id}.",
            "canon_status": "prototype",
            "decision_effects": [
                {
                    "id": f"EFFECT-{fact_id}",
                    "enabled": True,
                    "value": 7,
                }
            ],
            "source": {
                "kind": "VALIDATOR_SEED",
                "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                "site_dbref": int(site.id),
                "site_name": site.key,
            },
            "learned_by": {"mode": "VALIDATOR"},
        },
    )
    set_knowledge_level(entity, knowledge_key, 1)
    return packet


class CmdSizaValidateV101(Command):
    key = "siza-validate-v101"
    aliases = ["validate-v101"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        informant = install.get("informant") if install.get("success") else None
        mara = install.get("mara") if install.get("success") else None
        site = install.get("site") if install.get("success") else None
        if not informant or not mara or not site:
            self.caller.msg("[V1.01 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = str(getattr(informant.db, "npc_id", "") or "").strip()
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
                "current_goal": _clone(getattr(npc.db, "current_goal", None)),
                "destination_id": getattr(npc.db, "destination_id", None),
                "current_activity": getattr(npc.db, "current_activity", None),
            }

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v1.01 | {V101_VALIDATION_BUILD} ===")
        self.caller.msg(
            "holder-local Fact lifecycle: ACTIVE is usable; RETRACTED/SUPERSEDED remain stored historical knowledge but cannot ground retrieval, disclosure, decisions, goals, social travel or transfer"
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
                npc.db.current_goal = None
                npc.db.destination_id = None
                npc.db.current_activity = None

            seed = _seed_fact(informant, site)
            fact = find_knowledge_fact(informant, FACT_ID)
            state = fact_knowledge_state(informant, fact)
            retrieval = retrieve_known_facts(informant, query=FACT_ID)
            check(
                "legacy-fact-without-authored-lifecycle-defaults-active-and-preserves-historical-build-contracts",
                seed.get("fact", {}).get("fact_status") == FACT_STATUS_ACTIVE
                and state.get("known") is True
                and state.get("level_known") is True
                and state.get("fact_active") is True
                and state.get("fact_status") == FACT_STATUS_ACTIVE
                and retrieval.get("selected_fact_ids") == [FACT_ID]
                and KNOWLEDGE_FACT_BUILD == "0.57.0-persistent-knowledge-facts"
                and FACT_GOAL_BUILD == "0.59.0-fact-driven-npc-goals"
                and FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_TRANSFER_BUILD == "0.58.0-persistent-fact-transfer"
                and FACT_LIFECYCLE_BUILD == V101_VALIDATION_BUILD,
                f"state={state}",
            )

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
            active_goal_refresh = refresh_fact_driven_goals(informant)
            active_social = refresh_holder_aware_fact_share_obligations(informant)
            active_goal = find_decision_goal(informant, GOAL_ID)
            active_obligation = _find_obligation(informant, mara_id)
            check(
                "active-fact-materializes-normal-derived-goal-and-social-obligation-before-lifecycle-change",
                GOAL_ID in list(active_goal_refresh.get("materialized") or [])
                and active_goal is not None
                and active_goal.get("active") is True
                and any(str(row.get("obligation_id") or "") == obligation_id for row in list(active_social.get("materialized") or []))
                and active_obligation is not None
                and active_obligation.get("active") is True
                and _candidate_ids(informant) == {mara_id},
                f"goal={active_goal} obligation={active_obligation}",
            )

            retract = set_knowledge_fact_status(
                informant,
                FACT_ID,
                FACT_STATUS_RETRACTED,
                reason="validator correction",
            )
            retracted_fact = find_knowledge_fact(informant, FACT_ID)
            retracted_state = fact_knowledge_state(informant, retracted_fact)
            lifecycle_history = list((retracted_fact or {}).get("fact_lifecycle_history") or [])
            check(
                "retraction-preserves-stored-fact-knowledge-level-and-provenance-but-makes-current-state-unusable",
                retract.get("success") is True
                and retract.get("changed") is True
                and retracted_fact is not None
                and retracted_state.get("level") == 1
                and retracted_state.get("level_known") is True
                and retracted_state.get("known") is False
                and retracted_state.get("fact_status") == FACT_STATUS_RETRACTED
                and retracted_state.get("fact_active") is False
                and len(lifecycle_history) == 1
                and str((lifecycle_history[-1] or {}).get("from") or "") == FACT_STATUS_ACTIVE
                and str((lifecycle_history[-1] or {}).get("to") or "") == FACT_STATUS_RETRACTED
                and str(((retracted_fact or {}).get("source") or {}).get("kind") or "") == "VALIDATOR_SEED",
                f"state={retracted_state} history={lifecycle_history}",
            )

            retracted_retrieval = retrieve_known_facts(informant, query=FACT_ID)
            disclosure_fact = _first_shareable_topic_fact(informant, TOPIC)
            modifiers = knowledge_decision_modifiers(informant, {"id": "GOAL-V101-DUMMY"})
            check(
                "retracted-fact-is-excluded-from-llm-retrieval-disclosure-and-live-decision-effects",
                FACT_ID not in list(retracted_retrieval.get("selected_fact_ids") or [])
                and FACT_ID not in str(retracted_retrieval.get("context_text") or "")
                and disclosure_fact is None
                and not any(str(row.get("fact_id") or "") == FACT_ID for row in modifiers),
                f"retrieval={retracted_retrieval.get('selected_fact_ids')} disclosure={disclosure_fact} modifiers={modifiers}",
            )

            retracted_goal_refresh = refresh_fact_driven_goals(informant)
            retracted_goal = find_decision_goal(informant, GOAL_ID)
            check(
                "existing-fact-derived-goal-cancels-when-source-fact-becomes-inactive-without-destroying-one-shot-identity",
                GOAL_ID in list(retracted_goal_refresh.get("cancelled") or [])
                and retracted_goal is not None
                and retracted_goal.get("active") is False
                and str(retracted_goal.get("status") or "") == "cancelled"
                and str(retracted_goal.get("cancellation_reason") or "") == LIFECYCLE_CANCELLATION_REASON
                and FACT_GOAL_LIFECYCLE_BUILD == "1.01.0-lifecycle-aware-fact-goals",
                f"goal={retracted_goal}",
            )

            retracted_social = refresh_holder_aware_fact_share_obligations(informant)
            retracted_obligation = _find_obligation(informant, mara_id)
            check(
                "retracted-source-fact-cancels-pending-share-and-produces-no-relationship-candidate",
                retracted_obligation is not None
                and retracted_obligation.get("active") is False
                and str(retracted_obligation.get("status") or "") == "cancelled"
                and str(retracted_obligation.get("cancellation_reason") or "") == "SOURCE_NO_LONGER_KNOWS_FACT"
                and not _candidate_ids(informant)
                and any(row.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT" for row in list(retracted_social.get("skipped") or [])),
                f"obligation={retracted_obligation}",
            )

            blocked_transfer = transfer_knowledge_fact(informant, mara, FACT_ID)
            check(
                "retracted-fact-cannot-be-transferred-even-while-source-and-target-are-colocated",
                blocked_transfer.get("success") is False
                and blocked_transfer.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                and find_knowledge_fact(mara, FACT_ID) is None,
                f"transfer={blocked_transfer}",
            )

            reactivate = set_knowledge_fact_status(informant, FACT_ID, FACT_STATUS_ACTIVE, reason="validator reinstated")
            active_again_state = fact_knowledge_state(informant, find_knowledge_fact(informant, FACT_ID))
            goal_again = refresh_fact_driven_goals(informant)
            social_again = refresh_holder_aware_fact_share_obligations(informant)
            obligation_again = _find_obligation(informant, mara_id)
            retrieval_again = retrieve_known_facts(informant, query=FACT_ID)
            disclosure_again = _first_shareable_topic_fact(informant, TOPIC)
            check(
                "reactivating-same-fact-restores-live-authorities-and-reactivates-existing-goal-and-obligation-identities",
                reactivate.get("success") is True
                and active_again_state.get("known") is True
                and GOAL_ID in list(goal_again.get("reactivated") or [])
                and obligation_again is not None
                and obligation_again.get("active") is True
                and str(obligation_again.get("id") or "") == obligation_id
                and any(
                    str(row.get("obligation_id") or "") == obligation_id and row.get("created") is False
                    for row in list(social_again.get("materialized") or [])
                )
                and retrieval_again.get("selected_fact_ids") == [FACT_ID]
                and disclosure_again is not None,
                f"goal={goal_again.get('reactivated')} obligation={obligation_again}",
            )

            transferred = transfer_knowledge_fact(informant, mara, FACT_ID)
            mara_before_local_retract = fact_knowledge_state(mara, find_knowledge_fact(mara, FACT_ID))
            set_knowledge_fact_status(informant, FACT_ID, FACT_STATUS_RETRACTED, reason="validator holder-local proof")
            informant_after_local_retract = fact_knowledge_state(informant, find_knowledge_fact(informant, FACT_ID))
            mara_after_local_retract = fact_knowledge_state(mara, find_knowledge_fact(mara, FACT_ID))
            mara_retrieval = retrieve_known_facts(mara, query=FACT_ID)
            check(
                "fact-lifecycle-is-holder-local-so-retracting-source-copy-does-not-magically-mutate-an-already-transferred-recipient-copy",
                transferred.get("success") is True
                and transferred.get("reason") == "FACT_TRANSFERRED"
                and mara_before_local_retract.get("known") is True
                and informant_after_local_retract.get("known") is False
                and informant_after_local_retract.get("fact_status") == FACT_STATUS_RETRACTED
                and mara_after_local_retract.get("known") is True
                and mara_after_local_retract.get("fact_status") == FACT_STATUS_ACTIVE
                and mara_retrieval.get("selected_fact_ids") == [FACT_ID],
                f"source={informant_after_local_retract} recipient={mara_after_local_retract}",
            )

            set_knowledge_fact_status(informant, FACT_ID, FACT_STATUS_ACTIVE, reason="prepare supersession")
            _seed_fact(
                informant,
                site,
                fact_id=REPLACEMENT_FACT_ID,
                knowledge_key=REPLACEMENT_KNOWLEDGE_KEY,
                text="Validator replacement Fact supersedes the original report.",
            )
            supersede = set_knowledge_fact_status(
                informant,
                FACT_ID,
                FACT_STATUS_SUPERSEDED,
                reason="validator replacement available",
                superseded_by_fact_id=REPLACEMENT_FACT_ID,
            )
            superseded_fact = find_knowledge_fact(informant, FACT_ID)
            superseded_state = fact_knowledge_state(informant, superseded_fact)
            replacement_state = fact_knowledge_state(informant, find_knowledge_fact(informant, REPLACEMENT_FACT_ID))
            old_retrieval = retrieve_known_facts(informant, query=FACT_ID)
            replacement_retrieval = retrieve_known_facts(informant, query=REPLACEMENT_FACT_ID)
            superseded_transfer = transfer_knowledge_fact(informant, mara, FACT_ID)
            bad_status = set_knowledge_fact_status(informant, FACT_ID, "STALEISH")
            final_state = fact_knowledge_state(informant, find_knowledge_fact(informant, FACT_ID))
            check(
                "superseded-fact-remains-historical-but-unusable-points-to-active-replacement-and-invalid-status-mutation-fails-closed",
                supersede.get("success") is True
                and superseded_state.get("fact_status") == FACT_STATUS_SUPERSEDED
                and superseded_state.get("known") is False
                and str((superseded_fact or {}).get("superseded_by_fact_id") or "") == REPLACEMENT_FACT_ID
                and replacement_state.get("known") is True
                and FACT_ID not in list(old_retrieval.get("selected_fact_ids") or [])
                and replacement_retrieval.get("selected_fact_ids") == [REPLACEMENT_FACT_ID]
                and superseded_transfer.get("success") is False
                and superseded_transfer.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                and bad_status.get("success") is False
                and bad_status.get("reason") == "BAD_FACT_STATUS"
                and final_state.get("fact_status") == FACT_STATUS_SUPERSEDED,
                f"old={superseded_state} replacement={replacement_state} bad={bad_status}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            for name, npc in (("informant", informant), ("mara", mara)):
                state = original[name]
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
                npc.db.fact_goal_rules = state["goal_rules"]
                npc.db.decision_goals = state["goals"]
                npc.db.current_goal = state["current_goal"]
                npc.db.destination_id = state["destination_id"]
                npc.db.current_activity = state["current_activity"]

        self.caller.msg("")
        self.caller.msg(f"RESULT: {sum(1 for value in results if value)}/{len(results)} PASS")
        self.caller.msg("")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara locations, Knowledge/Facts, lifecycle metadata, social obligations/rules, Fact-goals and current decision state restored exactly"
        )
        self.caller.msg("")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: lifecycle is holder-local; inactive Facts remain stored historical records while central fact_knowledge_state removes them from live Knowledge authorities"
        )
        self.caller.msg("")
        self.caller.msg("========================================================")
