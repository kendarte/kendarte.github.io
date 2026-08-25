from evennia import Command, search_object

from commands.world_input_v74_commands import _clone
from services.consequence_engine import get_consequence_registry
from services.fact_driven_decision import decision_step
from services.fact_goal_engine import find_decision_goal, refresh_fact_driven_goals
from services.knowledge_context_engine import knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact
from services.object_action_engine import object_action_history
from services.object_action_input_engine import route_object_action_input
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v86 import (
    ACTION_FIELD,
    ACTION_ID,
    ACTION_INPUT,
    KNOWLEDGE_KEY as V086_PLAYER_KNOWLEDGE_KEY,
    WORLD_FIELD as V086_WORLD_FIELD,
)
from world.upgrade_pilot_v87 import (
    FACT_ID,
    FACT_TEXT,
    GOAL_ID,
    GOAL_RULE_ID,
    KNOWLEDGE_KEY,
    PILOT_BUILD,
    RULE_ID,
    TARGET_ROOM_ID,
    TARGET_ROOM_KEY,
    ensure_v87_pilot_content,
    v87_goal_rule_count,
    v87_rule_count,
)


V087_VALIDATION_BUILD = "0.87.0-player-world-consequence-teaches-npc-fact-goal"


def _target_room():
    for obj in search_object(TARGET_ROOM_KEY):
        if str(getattr(obj.db, "room_id", "") or "") == TARGET_ROOM_ID:
            return obj
    return None


def _remove_key(mapping, wanted):
    return {
        str(key): value
        for key, value in dict(mapping or {}).items()
        if str(key) != str(wanted)
    }


def _remove_fact(rows, wanted):
    return [
        row for row in list(rows or [])
        if str((row or {}).get("id") or "") != str(wanted)
    ]


def _remove_goal(rows, wanted):
    return [
        row for row in list(rows or [])
        if str((row or {}).get("id") or "") != str(wanted)
    ]


class CmdSizaValidateV87(Command):
    key = "siza-validate-v87"
    aliases = ["validate-v87"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v87_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.87 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        manifest = install.get("manifest")
        mara = install.get("mara")
        target_room = _target_room()
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not mara or not target_room or not registry:
            self.caller.msg("[V0.87 VALIDATION] FAIL | persistent context missing")
            return

        original_actor_location = actor.location
        original_actor_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_actor_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_actor_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_actor_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_mara_location = mara.location
        original_mara_knowledge = _clone(getattr(mara.db, "knowledge", {}))
        original_mara_facts = _clone(getattr(mara.db, "knowledge_facts", []))
        original_mara_goals = _clone(getattr(mara.db, "decision_goals", []))
        original_mara_current_goal = _clone(getattr(mara.db, "current_goal", None))
        original_mara_destination_id = getattr(mara.db, "destination_id", None)
        original_mara_activity = getattr(mara.db, "current_activity", None)
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.87 | {V087_VALIDATION_BUILD} ===")
        self.caller.msg(
            "player completes existing Knowledge-gated world action -> consequence teaches exact structured Fact to Mara -> Fact materializes one-shot goal -> existing decision engine moves Mara"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)

            actor.db.object_action_history = []
            actor.db.action_resolution_history = []
            actor_levels = dict(original_actor_knowledge or {})
            actor_levels[V086_PLAYER_KNOWLEDGE_KEY] = max(
                int(actor_levels.get(V086_PLAYER_KNOWLEDGE_KEY, 0) or 0),
                1,
            )
            actor.db.knowledge = actor_levels

            mara.db.knowledge = _remove_key(original_mara_knowledge, KNOWLEDGE_KEY)
            mara.db.knowledge_facts = _remove_fact(original_mara_facts, FACT_ID)
            mara.db.decision_goals = _remove_goal(original_mara_goals, GOAL_ID)
            mara.db.current_goal = None
            mara.db.destination_id = None
            mara.db.current_activity = None

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state[ACTION_FIELD] = False
            manifest.db.state = manifest_state

            world_state = _clone(getattr(site.db, "world_state", {}))
            if not isinstance(world_state, dict):
                world_state = {}
            world_state[MANIFEST_VISIBLE_FIELD] = 1
            world_state.pop(V086_WORLD_FIELD, None)
            site.db.world_state = world_state
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            check(
                "v087-content-installs-one-explicit-npc-consequence-and-one-fact-goal-rule",
                v87_rule_count() == 1
                and v87_goal_rule_count(mara) == 1
                and find_knowledge_fact(mara, FACT_ID) is None
                and find_decision_goal(mara, GOAL_ID) is None,
                f"rules={v87_rule_count()} goal_rules={v87_goal_rule_count(mara)}",
            )

            before_history = len(object_action_history(actor))
            executed = route_object_action_input(actor, ACTION_INPUT)
            check(
                "existing-v086-natural-action-completes-and-emits-normal-consequence-pipeline",
                executed.get("status") == "COMPLETED"
                and str(executed.get("object_action_id") or "") == ACTION_ID
                and len(object_action_history(actor)) == before_history + 1,
                f"status={executed.get('status')} action={executed.get('object_action_id')}",
            )

            mara_fact = find_knowledge_fact(mara, FACT_ID)
            mara_level = int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0)
            check(
                "player-world-action-automatically-teaches-the-exact-structured-fact-to-mara",
                mara_fact is not None
                and str(mara_fact.get("text") or "") == FACT_TEXT
                and mara_level >= 1,
                f"fact={None if mara_fact is None else mara_fact.get('id')} level={mara_level}",
            )

            source = dict((mara_fact or {}).get("source") or {})
            learned_by = dict((mara_fact or {}).get("learned_by") or {})
            check(
                "npc-learned-fact-keeps-authored-world-consequence-provenance",
                source.get("kind") == "WORLD_CONSEQUENCE"
                and str(source.get("object_id") or "") == str(getattr(manifest.db, "object_id", "") or "")
                and str(learned_by.get("object_action_id") or "") == ACTION_ID
                and str(learned_by.get("outcome") or "") == "COMPLETED",
                f"source_kind={source.get('kind')} learned_action={learned_by.get('object_action_id')}",
            )

            goal_before_step = find_decision_goal(mara, GOAL_ID)
            check(
                "fact-goal-is-not-pre-materialized-before-the-decision-refresh",
                goal_before_step is None,
                f"goal_present={goal_before_step is not None}",
            )

            step = decision_step(mara, prepare_world_state=False)
            goal_after_step = find_decision_goal(mara, GOAL_ID)
            refresh = dict(step.get("fact_goal_refresh") or {})
            check(
                "existing-fact-driven-decision-materializes-the-goal-from-the-newly-known-fact",
                GOAL_ID in list(refresh.get("materialized") or [])
                and goal_after_step is not None
                and str(goal_after_step.get("source_fact_id") or "") == FACT_ID,
                f"materialized={refresh.get('materialized')} source_fact={(goal_after_step or {}).get('source_fact_id')}",
            )

            check(
                "existing-decision-engine-reacts-to-player-consequence-by-moving-mara-to-authored-target",
                step.get("status") == "GOAL_COMPLETED"
                and str(step.get("goal_id") or "") == GOAL_ID
                and mara.location == target_room
                and str(step.get("to") or "") == TARGET_ROOM_KEY,
                f"status={step.get('status')} location={mara.location.key if mara.location else None}",
            )

            completed_goal = find_decision_goal(mara, GOAL_ID)
            check(
                "npc-reaction-goal-completes-one-shot-and-is-not-left-active",
                completed_goal is not None
                and completed_goal.get("active") is False
                and str(completed_goal.get("source_fact_id") or "") == FACT_ID,
                f"active={None if completed_goal is None else completed_goal.get('active')}",
            )

            second_refresh = refresh_fact_driven_goals(mara)
            check(
                "known-fact-does-not-reactivate-the-completed-one-shot-goal",
                GOAL_ID not in list(second_refresh.get("materialized") or [])
                and (find_decision_goal(mara, GOAL_ID) or {}).get("active") is False,
                f"materialized={second_refresh.get('materialized')}",
            )

            second_install = ensure_v87_pilot_content()
            check(
                "v087-install-is-idempotent-and-does-not-erase-npc-learned-fact-or-completed-goal",
                second_install.get("success") is True
                and v87_rule_count() == 1
                and v87_goal_rule_count(mara) == 1
                and find_knowledge_fact(mara, FACT_ID) is not None
                and (find_decision_goal(mara, GOAL_ID) or {}).get("active") is False,
                f"rules={v87_rule_count()} goal_rules={v87_goal_rule_count(mara)}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_actor_location:
                    actor.move_to(original_actor_location, quiet=True)
            except Exception:
                pass
            try:
                if mara.location != original_mara_location:
                    mara.move_to(original_mara_location, quiet=True)
            except Exception:
                pass

            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.object_action_history = original_actor_object_history
            actor.db.action_resolution_history = original_actor_resolution_history

            mara.db.knowledge = original_mara_knowledge
            mara.db.knowledge_facts = original_mara_facts
            mara.db.decision_goals = original_mara_goals
            mara.db.current_goal = original_mara_current_goal
            mara.db.destination_id = original_mara_destination_id
            mara.db.current_activity = original_mara_activity

            manifest.db.state = original_manifest_state
            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    pass
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor Knowledge/action history, Mara location/Knowledge/Facts/goals/current activity, manifest/room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: v0.87 consequence rule and Fact-goal rule remain installed; core consequence/fact-goal/decision engines are unchanged"
        )
        self.caller.msg("========================================================")
