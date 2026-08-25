from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import (
    _find_obligation,
    _obligation_id,
    _remove_fact_knowledge,
    _remove_test_obligation,
    _target_room,
)
from services.fact_driven_decision import decision_step
from services.fact_share_rule_engine import refresh_fact_share_obligations
from services.knowledge_context_engine import knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.relationship_engine import collect_relationship_candidates
from world.upgrade_pilot_v88 import FACT_ID, FACT_TEXT, FACT_TOPIC, KNOWLEDGE_KEY
from world.upgrade_pilot_v89 import PRIORITY, ensure_v89_pilot_content


V0891_VALIDATION_BUILD = "0.89.1-targeted-relationship-completion-packet-contract"


class CmdSizaValidateV891(Command):
    key = "siza-validate-v891"
    aliases = ["validate-v891"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.89.1 VALIDATION] FAIL | install={install}")
            return

        informant = install.get("informant")
        mara = install.get("mara")
        site = install.get("site")
        away = _target_room()
        if not informant or not mara or not site or not away:
            self.caller.msg("[V0.89.1 VALIDATION] FAIL | persistent context missing")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.89.1 | {V0891_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted rerun: SHARE_FACT identity is asserted on the relationship candidate/obligation; npc_decision completion is validated against its real historical RELATIONSHIP packet contract"
        )

        try:
            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != away:
                mara.move_to(away, quiet=True)

            _remove_fact_knowledge(informant)
            _remove_fact_knowledge(mara)
            _remove_test_obligation(informant, mara_id)
            informant.db.current_goal = None
            informant.db.destination_id = None
            informant.db.current_activity = None
            informant.db.decision_enabled = True

            upsert_knowledge_fact(
                informant,
                {
                    "id": FACT_ID,
                    "topic": FACT_TOPIC,
                    "aliases": ["cruce del sello blanco", "sello blanco presenciado"],
                    "text": FACT_TEXT,
                    "knowledge_key": KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {
                        "kind": "DIRECT_SITE_WITNESS",
                        "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                        "site_name": site.key,
                    },
                    "learned_by": {
                        "mode": "SITE_PRESENCE",
                        "validator": "v0.89.1",
                    },
                },
            )
            set_knowledge_level(informant, KNOWLEDGE_KEY, 1)

            refresh = refresh_fact_share_obligations(informant)
            obligation = _find_obligation(informant, mara_id)
            candidate = next(
                (
                    row
                    for row in collect_relationship_candidates(informant)
                    if str(row.get("relationship_obligation_id") or "") == wanted_obligation
                ),
                None,
            )
            check(
                "share-fact-identity-is-authoritative-before-decision-step",
                obligation is not None
                and str(obligation.get("kind") or "") == "SHARE_FACT"
                and str(obligation.get("fact_id") or "") == FACT_ID
                and candidate is not None
                and str(candidate.get("relationship_kind") or "") == "SHARE_FACT"
                and str(candidate.get("fact_id") or "") == FACT_ID
                and int(candidate.get("priority", 0) or 0) == PRIORITY,
                f"refresh={refresh.get('status')} candidate_kind={None if candidate is None else candidate.get('relationship_kind')}",
            )

            step = decision_step(informant, prepare_world_state=False)
            check(
                "npc-decision-resolves-share-fact-through-real-historical-relationship-completion-contract",
                step.get("status") == "GOAL_COMPLETED"
                and step.get("completion_source") == "RELATIONSHIP"
                and step.get("relationship_resolved") is True
                and step.get("relationship_reason") == "RESOLVED"
                and str(step.get("relationship_obligation_id") or "") == wanted_obligation
                and str(step.get("relationship_target_npc_id") or "") == mara_id
                and informant.location == mara.location
                and informant.location == away,
                f"status={step.get('status')} completion={step.get('completion_source')} resolved={step.get('relationship_resolved')} top_kind={step.get('relationship_kind')}",
            )

            mara_fact = find_knowledge_fact(mara, FACT_ID)
            history = list((mara_fact or {}).get("transfer_history") or [])
            transfer = history[-1] if history else {}
            check(
                "post-decision-authoritative-state-proves-exact-share-fact-transfer-occurred",
                mara_fact is not None
                and str(mara_fact.get("text") or "") == FACT_TEXT
                and int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0) >= 1
                and str(transfer.get("source_npc_id") or "") == informant_id
                and str(transfer.get("target_npc_id") or "") == mara_id
                and transfer.get("mode") == "DIRECT_LOCAL",
                f"history={len(history)} source={transfer.get('source_npc_id')} target={transfer.get('target_npc_id')}",
            )

            completed = _find_obligation(informant, mara_id)
            second_refresh = refresh_fact_share_obligations(informant)
            check(
                "completed-share-fact-obligation-remains-one-shot-under-targeted-packet-contract",
                completed is not None
                and completed.get("active") is False
                and str(completed.get("status") or "") == "completed"
                and not list(second_refresh.get("materialized") or [])
                and any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "ALREADY_COMPLETED"
                    for row in list(second_refresh.get("skipped") or [])
                ),
                f"active={None if completed is None else completed.get('active')} refresh={second_refresh.get('status')}",
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
            "STATE RESTORED: Informant/Mara locations, Knowledge/Facts, Informant relationship and decision state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.89 production unchanged; SHARE_FACT identity lives on the relationship obligation/candidate while npc_decision keeps its historical generic RELATIONSHIP completion packet"
        )
        self.caller.msg("========================================================")
