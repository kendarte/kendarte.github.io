from evennia import Command

from services.fact_driven_decision import FACT_DRIVEN_DECISION_BUILD, choose_goal, decision_step
from services.fact_goal_engine import (
    FACT_GOAL_BUILD,
    fact_goal_rules,
    find_decision_goal,
    refresh_fact_driven_goals,
    remove_fact_goal,
)
from services.knowledge_context_engine import knowledge_facts, knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.npc_simulation import find_npc
from typeclasses.world_tick import simulate_npc_tick
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v57 import (
    ACTION_ID as V57_ACTION_ID,
    FACT_ID,
    FACT_TEXT,
    FACT_TOPIC,
    KNOWLEDGE_KEY,
)
from world.upgrade_pilot_v59 import (
    GOAL_ACTIVITY,
    GOAL_ID,
    PILOT_BUILD,
    RULE_ID,
    TARGET_ROOM_ID,
    TARGET_ROOM_KEY,
    ensure_v59_pilot_content,
    reset_v59_playtest_state,
)


def _clone(value):
    if hasattr(value, "items"):
        try:
            return {str(key): _clone(item) for key, item in value.items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_clone(item) for item in value]
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        try:
            return [_clone(item) for item in value]
        except Exception:
            pass
    return value


def _goal_count(npc):
    try:
        rows = list(getattr(npc.db, "decision_goals", []) or [])
    except Exception:
        rows = []
    total = 0
    for raw in rows:
        try:
            item = dict(raw)
        except Exception:
            continue
        if str(item.get("id") or "") == GOAL_ID:
            total += 1
    return total


def _rule_count(npc):
    return sum(1 for row in fact_goal_rules(npc) if str(row.get("id") or "") == RULE_ID)


def _pilot_fact(site, manifest):
    return {
        "id": FACT_ID,
        "topic": FACT_TOPIC,
        "text": FACT_TEXT,
        "knowledge_key": KNOWLEDGE_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": MANIFEST_ID,
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
            "object_dbref": int(manifest.id),
            "site_dbref": int(site.id),
        },
        "learned_by": {
            "object_action_id": V57_ACTION_ID,
            "attempt_id": "V059-VALIDATOR-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V059-VALIDATOR-SEED",
        },
    }


class CmdSizaFactGoalsV59(Command):
    """Inspect fact-driven goal rules and the resulting authored goal on one NPC."""

    key = "siza-fact-goals"
    aliases = ["fact-goals"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("Uso: siza-fact-goals <NPC>")
            return
        known = {str(row.get("id") or "") for row in knowledge_facts(npc)}
        self.caller.msg(f"=== SIZA FACT GOALS | {FACT_GOAL_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | location={npc.location.key if npc.location else None}")
        for rule in fact_goal_rules(npc):
            goal = dict(rule.get("goal") or {})
            materialized = find_decision_goal(npc, goal.get("id"))
            self.caller.msg(
                f"  rule={rule.get('id')} | fact={rule.get('fact_id')} | "
                f"fact_record={str(rule.get('fact_id') or '') in known} | goal={goal.get('id')} | "
                f"materialized={materialized is not None} | active={None if materialized is None else materialized.get('active')}"
            )
        self.caller.msg("========================================================")


class CmdSizaResetV59(Command):
    """Reset only the v0.59 fact-driven goal playtest state."""

    key = "siza-reset-v59"
    aliases = ["reset-v59"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v59_playtest_state()
        if not result.get("success"):
            self.caller.msg(f"[V0.59 RESET] FAIL | reason={result.get('reason')}")
            return
        target = result.get("target")
        fact = find_knowledge_fact(target, FACT_ID)
        level = knowledge_levels(target).get(KNOWLEDGE_KEY, 0)
        self.caller.msg(f"=== SIZA v0.59 RESET | {FACT_DRIVEN_DECISION_BUILD} ===")
        self.caller.msg(
            f"PASS fact-goal reset | target={target.key}#{target.id} | location={target.location.key if target.location else None} | "
            f"goal_removed={result.get('goal_removed')} | fact_preserved={fact is not None} | knowledge={level}"
        )
        self.caller.msg("No se tocaron Facts/Knowledge v0.57-v0.58 ni otros goals del NPC.")
        self.caller.msg("========================================================")


class CmdSizaValidateV59(Command):
    """Validate Fact -> goal -> decision movement -> one-shot completion -> autonomous tick."""

    key = "siza-validate-v59"
    aliases = ["validate-v59"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v59_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.59 VALIDATION] FAIL | context={context}")
            return

        target = context.get("target")
        site = context.get("site")
        manifest = context.get("manifest")
        destination = context.get("destination")
        original_location = target.location
        original_knowledge = _clone(getattr(target.db, "knowledge", {}))
        original_facts = _clone(getattr(target.db, "knowledge_facts", []))
        original_goals = _clone(getattr(target.db, "decision_goals", []))
        original_rules = _clone(getattr(target.db, "fact_goal_rules", []))
        original_current_goal = _clone(getattr(target.db, "current_goal", None))
        original_current_activity = getattr(target.db, "current_activity", None)
        original_destination_id = getattr(target.db, "destination_id", None)
        original_decision_enabled = bool(getattr(target.db, "decision_enabled", False))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.59 | {FACT_DRIVEN_DECISION_BUILD} ===")
        self.caller.msg(
            f"NPC: {target.key}#{target.id} | fact={FACT_ID} | goal={GOAL_ID} | destination={destination.key}#{destination.id}"
        )

        try:
            if target.location != site:
                target.move_to(site, quiet=True)
            remove_fact_goal(target, GOAL_ID)
            target.db.current_goal = None
            target.db.current_activity = None
            target.db.destination_id = None
            target.db.decision_enabled = True

            levels = knowledge_levels(target)
            levels.pop(KNOWLEDGE_KEY, None)
            target.db.knowledge = levels
            target.db.knowledge_facts = [
                row for row in knowledge_facts(target) if str(row.get("id") or "") != FACT_ID
            ]

            check(
                "fact-goal-rule-is-installed-once",
                _rule_count(target) == 1,
                f"rules={_rule_count(target)} build={PILOT_BUILD}",
            )

            before = refresh_fact_driven_goals(target)
            decision_without = choose_goal(target)
            check(
                "unknown-fact-does-not-materialize-goal",
                before.get("materialized") == []
                and _goal_count(target) == 0
                and not any(str(row.get("id") or "") == GOAL_ID for row in (decision_without.get("candidates") or [])),
                f"materialized={before.get('materialized')} goals={_goal_count(target)}",
            )

            upsert_knowledge_fact(target, _pilot_fact(site, manifest))
            set_knowledge_level(target, KNOWLEDGE_KEY, 1)
            decision = choose_goal(target)
            selected = decision.get("selected") or {}
            goal = find_decision_goal(target, GOAL_ID)
            check(
                "known-fact-materializes-persistent-authored-goal-once",
                _goal_count(target) == 1
                and goal is not None
                and goal.get("active") is True
                and goal.get("source_fact_id") == FACT_ID
                and goal.get("fact_goal_rule_id") == RULE_ID,
                f"goals={_goal_count(target)} active={None if goal is None else goal.get('active')}",
            )

            check(
                "fact-driven-goal-wins-normal-decision-selection",
                selected.get("id") == GOAL_ID
                and selected.get("target_room_id") == TARGET_ROOM_ID
                and selected.get("target_name") == TARGET_ROOM_KEY
                and selected.get("path_length") == 3,
                f"winner={selected.get('id')} target={selected.get('target_name')} path={selected.get('path_length')}",
            )

            step1 = decision_step(target, prepare_world_state=False)
            check(
                "decision-step-follows-real-exit-pescaderia-to-calle",
                step1.get("status") == "MOVED_GOAL"
                and step1.get("goal_id") == GOAL_ID
                and step1.get("from") == "Pescaderia de Darsena"
                and step1.get("to") == "Calle de Servicio",
                f"status={step1.get('status')} {step1.get('from')}->{step1.get('to')}",
            )

            step2 = decision_step(target, prepare_world_state=False)
            check(
                "decision-step-follows-real-exit-calle-to-plaza",
                step2.get("status") == "MOVED_GOAL"
                and step2.get("goal_id") == GOAL_ID
                and step2.get("from") == "Calle de Servicio"
                and step2.get("to") == "Plaza de Recepcion",
                f"status={step2.get('status')} {step2.get('from')}->{step2.get('to')}",
            )

            step3 = decision_step(target, prepare_world_state=False)
            completed_goal = find_decision_goal(target, GOAL_ID)
            check(
                "arrival-completes-and-disables-one-shot-fact-goal",
                step3.get("status") == "GOAL_COMPLETED"
                and step3.get("goal_id") == GOAL_ID
                and step3.get("from") == "Plaza de Recepcion"
                and step3.get("to") == TARGET_ROOM_KEY
                and target.location == destination
                and completed_goal is not None
                and completed_goal.get("active") is False,
                f"status={step3.get('status')} location={target.location.key if target.location else None} active={None if completed_goal is None else completed_goal.get('active')}",
            )

            after_completion = choose_goal(target)
            check(
                "completed-goal-is-not-rematerialized-or-selected-again",
                _goal_count(target) == 1
                and find_decision_goal(target, GOAL_ID).get("active") is False
                and str(((after_completion.get("selected") or {}).get("id") or "")) != GOAL_ID,
                f"goals={_goal_count(target)} winner={((after_completion.get('selected') or {}).get('id'))}",
            )

            fact_after = find_knowledge_fact(target, FACT_ID)
            check(
                "behavior-does-not-consume-or-mutate-underlying-knowledge",
                fact_after is not None
                and fact_after.get("text") == FACT_TEXT
                and knowledge_levels(target).get(KNOWLEDGE_KEY) == 1,
                f"fact={fact_after is not None} knowledge={knowledge_levels(target).get(KNOWLEDGE_KEY)}",
            )

            remove_fact_goal(target, GOAL_ID)
            if target.location != site:
                target.move_to(site, quiet=True)
            target.db.current_goal = None
            target.db.destination_id = None
            target.db.decision_enabled = True
            tick_result = simulate_npc_tick(target)
            check(
                "autonomous-world-tick-uses-same-fact-driven-decision-wrapper",
                tick_result.get("goal_id") == GOAL_ID
                and tick_result.get("status") == "MOVED_GOAL"
                and tick_result.get("from") == "Pescaderia de Darsena"
                and tick_result.get("to") == "Calle de Servicio"
                and tick_result.get("fact_driven_build") == FACT_DRIVEN_DECISION_BUILD,
                f"status={tick_result.get('status')} goal={tick_result.get('goal_id')} build={tick_result.get('fact_driven_build')}",
            )

            reset = reset_v59_playtest_state()
            check(
                "v059-reset-removes-only-goal-and-preserves-transferred-fact",
                reset.get("success") is True
                and _goal_count(target) == 0
                and find_knowledge_fact(target, FACT_ID) is not None
                and knowledge_levels(target).get(KNOWLEDGE_KEY) == 1
                and target.location == site,
                f"goals={_goal_count(target)} fact={find_knowledge_fact(target, FACT_ID) is not None} location={target.location.key if target.location else None}",
            )

            ensure_v59_pilot_content()
            check(
                "v059-install-is-idempotent",
                _rule_count(target) == 1,
                f"rules={_rule_count(target)}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if target.location != original_location:
                    target.move_to(original_location, quiet=True)
            except Exception:
                pass
            target.db.knowledge = original_knowledge
            target.db.knowledge_facts = original_facts
            target.db.decision_goals = original_goals
            target.db.fact_goal_rules = original_rules
            target.db.current_goal = original_current_goal
            target.db.current_activity = original_current_activity
            target.db.destination_id = original_destination_id
            target.db.decision_enabled = original_decision_enabled

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: NPC location/Knowledge/Facts/goals/current activity/destination/decision mode restored"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: Fact->Goal rules + decision wrapper + autonomous world-tick integration"
        )
        self.caller.msg("========================================================")
