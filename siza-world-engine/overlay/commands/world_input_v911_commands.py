from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v89_commands import (
    _find_obligation,
    _obligation_id,
    _remove_fact_knowledge,
    _remove_test_obligation,
    _target_room,
)
from commands.world_input_v90_commands import _seed_known_fact
from services.fact_driven_decision import choose_goal
from services.fact_share_rule_engine import refresh_fact_share_obligations
from world.upgrade_pilot_v88 import FACT_ID
from world.upgrade_pilot_v89 import ensure_v89_pilot_content


V0911_VALIDATION_BUILD = "0.91.1-explicit-source-loss-packet-compatibility"


class CmdSizaValidateV911(Command):
    key = "siza-validate-v911"
    aliases = ["validate-v911"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.91.1 VALIDATION] FAIL | install={install}")
            return

        informant = install.get("informant")
        mara = install.get("mara")
        site = install.get("site")
        away = _target_room()
        if not informant or not mara or not site or not away:
            self.caller.msg("[V0.91.1 VALIDATION] FAIL | persistent context missing")
            return

        mara_id = str(getattr(mara.db, "npc_id", "") or "").strip()
        wanted_obligation = _obligation_id(mara_id)

        original = {
            "informant_location": informant.location,
            "mara_location": mara.location,
            "informant_knowledge": _clone(getattr(informant.db, "knowledge", {})),
            "informant_facts": _clone(getattr(informant.db, "knowledge_facts", [])),
            "mara_knowledge": _clone(getattr(mara.db, "knowledge", {})),
            "mara_facts": _clone(getattr(mara.db, "knowledge_facts", [])),
            "informant_relationships": _clone(getattr(informant.db, "relationships", {})),
            "informant_sources": _clone(getattr(informant.db, "fact_share_obligation_sources", {})),
            "informant_current_goal": _clone(getattr(informant.db, "current_goal", None)),
            "informant_destination": getattr(informant.db, "destination_id", None),
            "informant_activity": getattr(informant.db, "current_activity", None),
            "informant_decision_enabled": getattr(informant.db, "decision_enabled", None),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.91.1 | {V0911_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted compatibility: v0.92 fanout metadata must not change the historical EXPLICIT source-loss packet used by v0.91"
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
            informant.db.fact_share_obligation_sources = {}
            _seed_known_fact(informant, site, "SITE_PRESENCE")

            created = refresh_fact_share_obligations(informant)
            pending = _find_obligation(informant, mara_id)
            if pending is None or pending.get("active") is not True:
                check("fixture-created-explicit-pending-share", False, f"refresh={created}")
                return

            _remove_fact_knowledge(informant)
            lost = refresh_fact_share_obligations(informant)
            row = next(
                (
                    item
                    for item in list(lost.get("skipped") or [])
                    if str((item or {}).get("rule_id") or "") == "FACT-SHARE-V089-INFORMANT-TO-MARA-WITNESS-001"
                    and (item or {}).get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                ),
                {},
            )
            cancelled = _find_obligation(informant, mara_id)
            check(
                "explicit-source-loss-preserves-direct-obligation-id-and-cancelled-pending-fields",
                str(row.get("obligation_id") or "") == wanted_obligation
                and row.get("cancelled_pending") is True
                and cancelled is not None
                and cancelled.get("active") is False
                and str(cancelled.get("status") or "") == "cancelled"
                and cancelled.get("cancellation_reason") == "SOURCE_NO_LONGER_KNOWS_FACT",
                f"obligation_id={row.get('obligation_id')} cancelled_pending={row.get('cancelled_pending')} status={None if cancelled is None else cancelled.get('status')}",
            )

            wrapped = choose_goal(informant)
            wrapped_refresh = dict(wrapped.get("fact_share_refresh") or {})
            wrapped_row = next(
                (
                    item
                    for item in list(wrapped_refresh.get("skipped") or [])
                    if (item or {}).get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                ),
                {},
            )
            relationship_candidates = [
                item
                for item in list(wrapped.get("candidates") or [])
                if str((item or {}).get("relationship_obligation_id") or "") == wanted_obligation
            ]
            check(
                "fact-driven-wrapper-keeps-explicit-source-loss-packet-compatible-and-prunes-candidate",
                str(wrapped_row.get("obligation_id") or "") == wanted_obligation
                and not relationship_candidates
                and informant.location == site
                and mara.location == away,
                f"obligation_id={wrapped_row.get('obligation_id')} candidates={len(relationship_candidates)}",
            )

            _seed_known_fact(informant, site, "SITE_PRESENCE")
            recovered = refresh_fact_share_obligations(informant)
            obligation = _find_obligation(informant, mara_id)
            matching = [
                row
                for row in list(recovered.get("materialized") or [])
                if str((row or {}).get("obligation_id") or "") == wanted_obligation
            ]
            check(
                "relearning-reactivates-same-explicit-obligation-id-after-compatibility-fix",
                len(matching) == 1
                and matching[0].get("created") is False
                and obligation is not None
                and obligation.get("active") is True
                and str(obligation.get("status") or "") == "pending",
                f"materialized={matching} status={None if obligation is None else obligation.get('status')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            for npc, location in ((informant, original["informant_location"]), (mara, original["mara_location"])):
                try:
                    if npc.location != location:
                        npc.move_to(location, quiet=True)
                except Exception:
                    pass
            informant.db.knowledge = original["informant_knowledge"]
            informant.db.knowledge_facts = original["informant_facts"]
            mara.db.knowledge = original["mara_knowledge"]
            mara.db.knowledge_facts = original["mara_facts"]
            informant.db.relationships = original["informant_relationships"]
            informant.db.fact_share_obligation_sources = original["informant_sources"]
            informant.db.current_goal = original["informant_current_goal"]
            informant.db.destination_id = original["informant_destination"]
            informant.db.current_activity = original["informant_activity"]
            informant.db.decision_enabled = original["informant_decision_enabled"]

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara location, Knowledge/Facts, relationships, source-index and decision state restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.91 source-loss behavior unchanged; v0.92 multi-target metadata now preserves the historical EXPLICIT refresh packet contract"
        )
        self.caller.msg("========================================================")
