from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import (
    _find_obligation,
    _obligation_id,
    _remove_fact_knowledge,
    _remove_test_obligation,
    _target_room,
)
from services.fact_driven_decision import (
    FACT_DRIVEN_DECISION_BUILD,
    FACT_SHARE_DECISION_BUILD,
    choose_goal,
)
from services.fact_share_rule_engine import (
    FACT_SHARE_RULE_BUILD,
    FACT_SHARE_TARGET_AWARENESS_BUILD,
    refresh_fact_share_obligations,
)
from services.knowledge_context_engine import set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.relationship_engine import collect_relationship_candidates
from world.upgrade_pilot_v88 import FACT_ID, FACT_TEXT, FACT_TOPIC, KNOWLEDGE_KEY
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V090_VALIDATION_BUILD = "0.90.0-target-aware-redundant-fact-share-pruning"


def _seed_known_fact(npc, site, learned_mode):
    upsert_knowledge_fact(
        npc,
        {
            "id": FACT_ID,
            "topic": FACT_TOPIC,
            "aliases": ["cruce del sello blanco", "sello blanco presenciado"],
            "text": FACT_TEXT,
            "knowledge_key": KNOWLEDGE_KEY,
            "required_level": 1,
            "canon_status": "prototype",
            "source": {
                "kind": "DIRECT_SITE_WITNESS" if learned_mode == "SITE_PRESENCE" else "INDEPENDENT_ROUTE",
                "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                "site_name": site.key,
            },
            "learned_by": {
                "mode": learned_mode,
                "validator": "v0.90",
            },
        },
    )
    set_knowledge_level(npc, KNOWLEDGE_KEY, 1)


def _candidate_for(npc, obligation_id):
    return next(
        (
            row
            for row in collect_relationship_candidates(npc)
            if str(row.get("relationship_obligation_id") or "") == str(obligation_id)
        ),
        None,
    )


class CmdSizaValidateV90(Command):
    key = "siza-validate-v90"
    aliases = ["validate-v90"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.90 VALIDATION] FAIL | install={install}")
            return

        informant = install.get("informant")
        mara = install.get("mara")
        site = install.get("site")
        away = _target_room()
        if not informant or not mara or not site or not away:
            self.caller.msg("[V0.90 VALIDATION] FAIL | persistent context missing")
            return

        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        wanted_obligation = _obligation_id(mara_id)

        original_informant_location = informant.location
        original_mara_location = mara.location
        original_informant_knowledge = _clone(getattr(informant.db, "knowledge", {}))
        original_informant_facts = _clone(getattr(informant.db, "knowledge_facts", []))
        original_informant_relationships = _clone(getattr(informant.db, "relationships", {}))
        original_informant_goals = _clone(getattr(informant.db, "decision_goals", []))
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

        self.caller.msg(f"=== SIZA VALIDATION v0.90 | {V090_VALIDATION_BUILD} ===")
        self.caller.msg(
            "source knows Fact + target already knows -> no share goal; pending share becomes stale -> refresh retires before decision candidates -> no redundant travel or transfer"
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
            _seed_known_fact(mara, site, "INDEPENDENT_ROUTE")

            already_known = refresh_fact_share_obligations(informant)
            check(
                "target-already-knows-exact-fact-prevents-new-share-obligation",
                not list(already_known.get("materialized") or [])
                and any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "TARGET_ALREADY_KNOWS_FACT"
                    and row.get("retired_pending") is False
                    for row in list(already_known.get("skipped") or [])
                )
                and _find_obligation(informant, mara_id) is None,
                f"status={already_known.get('status')} skipped={already_known.get('skipped')}",
            )

            check(
                "historical-fact-share-and-decision-builds-remain-stable-with-v090-as-separate-capability",
                FACT_SHARE_RULE_BUILD == "0.89.0-fact-driven-social-share-rules"
                and FACT_SHARE_DECISION_BUILD == "0.89.0-fact-driven-social-share-wrapper"
                and FACT_DRIVEN_DECISION_BUILD == "0.59.0-fact-driven-decision-wrapper"
                and already_known.get("target_awareness_build") == FACT_SHARE_TARGET_AWARENESS_BUILD,
                f"rule={FACT_SHARE_RULE_BUILD} decision={FACT_SHARE_DECISION_BUILD} target_awareness={already_known.get('target_awareness_build')}",
            )

            _remove_fact_knowledge(mara)
            _remove_test_obligation(informant, mara_id)
            created = refresh_fact_share_obligations(informant)
            pending = _find_obligation(informant, mara_id)
            pending_candidate = _candidate_for(informant, wanted_obligation)
            check(
                "unknown-target-still-materializes-normal-share-fact-obligation-and-goal",
                any(str(row.get("obligation_id") or "") == wanted_obligation for row in list(created.get("materialized") or []))
                and pending is not None
                and pending.get("active") is True
                and str(pending.get("kind") or "") == "SHARE_FACT"
                and pending_candidate is not None,
                f"refresh={created.get('status')} candidate={pending_candidate is not None}",
            )

            _seed_known_fact(mara, site, "INDEPENDENT_ROUTE")
            mara_before_retire = _clone(find_knowledge_fact(mara, FACT_ID))
            retired = refresh_fact_share_obligations(informant)
            stale = _find_obligation(informant, mara_id)
            stale_candidate = _candidate_for(informant, wanted_obligation)
            mara_after_retire = _clone(find_knowledge_fact(mara, FACT_ID))
            check(
                "pending-share-is-retired-when-target-learns-independently-before-contact",
                any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "TARGET_ALREADY_KNOWS_FACT"
                    and row.get("retired_pending") is True
                    for row in list(retired.get("skipped") or [])
                )
                and stale is not None
                and stale.get("active") is False
                and str(stale.get("status") or "") == "completed"
                and stale.get("completion_reason") == "TARGET_ALREADY_KNOWS_FACT"
                and stale.get("completed_without_contact") is True
                and stale_candidate is None
                and informant.location == site
                and mara.location == away
                and mara_before_retire == mara_after_retire
                and not list((mara_after_retire or {}).get("transfer_history") or []),
                f"retired={retired.get('skipped')} candidate={stale_candidate} source_location={informant.location.key if informant.location else None}",
            )

            _remove_fact_knowledge(mara)
            _remove_test_obligation(informant, mara_id)
            refresh_fact_share_obligations(informant)
            _seed_known_fact(mara, site, "INDEPENDENT_ROUTE")
            wrapped = choose_goal(informant)
            wrapped_refresh = dict(wrapped.get("fact_share_refresh") or {})
            wrapped_candidates = list((wrapped.get("candidates") or []))
            wrapped_stale = _find_obligation(informant, mara_id)
            check(
                "fact-driven-decision-wrapper-prunes-stale-share-before-underlying-candidate-selection",
                any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "TARGET_ALREADY_KNOWS_FACT"
                    and row.get("retired_pending") is True
                    for row in list(wrapped_refresh.get("skipped") or [])
                )
                and not any(str(row.get("relationship_obligation_id") or "") == wanted_obligation for row in wrapped_candidates)
                and wrapped_stale is not None
                and wrapped_stale.get("active") is False
                and informant.location == site,
                f"refresh={wrapped_refresh.get('status')} candidates={len(wrapped_candidates)} selected={(wrapped.get('selected') or {}).get('id')}",
            )

            final_refresh = refresh_fact_share_obligations(informant)
            final_obligation = _find_obligation(informant, mara_id)
            check(
                "externally-satisfied-one-shot-obligation-stays-terminal-and-does-not-cycle",
                not list(final_refresh.get("materialized") or [])
                and any(
                    str(row.get("obligation_id") or "") == wanted_obligation
                    and row.get("reason") == "ALREADY_COMPLETED"
                    for row in list(final_refresh.get("skipped") or [])
                )
                and final_obligation is not None
                and final_obligation.get("active") is False
                and str(final_obligation.get("status") or "") == "completed",
                f"status={final_refresh.get('status')} skipped={final_refresh.get('skipped')}",
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
            informant.db.decision_goals = original_informant_goals
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
            "STATE RESTORED: Informant/Mara location, Knowledge/Facts, Informant relationships/goals/current decision state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.89 SHARE_FACT transfer/contact semantics remain unchanged; v0.90 only prunes target-redundant obligations before travel"
        )
        self.caller.msg("========================================================")
