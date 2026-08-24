from evennia import Command

from services.fact_driven_decision import FACT_DRIVEN_DECISION_BUILD, choose_goal, decision_step
from services.fact_goal_engine import fact_goal_rules, find_decision_goal
from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts, knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from typeclasses.world_tick import simulate_npc_tick
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v57 import (
    ACTION_ID as V57_ACTION_ID,
    FACT_ID,
    FACT_TEXT,
    FACT_TOPIC,
    KNOWLEDGE_KEY,
)
from world.upgrade_pilot_v59 import GOAL_ID as INFORMANT_GOAL_ID
from world.upgrade_pilot_v60 import reset_v60_playtest_state
from world.upgrade_pilot_v61 import (
    GOAL_ID,
    PILOT_BUILD,
    RULE_ID,
    TARGET_ROOM_ID,
    TARGET_ROOM_KEY,
    ensure_v61_pilot_content,
    reset_v61_playtest_state,
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


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _goal_count(npc):
    total = 0
    for raw in _plain_list(getattr(npc.db, "decision_goals", [])):
        try:
            item = dict(raw)
        except Exception:
            continue
        if str(item.get("id") or "") == GOAL_ID:
            total += 1
    return total


def _rule_count(npc):
    return sum(1 for row in fact_goal_rules(npc) if str(row.get("id") or "") == RULE_ID)


def _pilot_fact(caller, site, manifest, informant):
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
            "attempt_id": "V061-VALIDATOR-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V061-VALIDATOR-SEED",
        },
        "transfer_history": [
            {
                "id": f"FACT_TRANSFER:{FACT_ID}:DBREF:{int(caller.id)}:NPC:{str(getattr(informant.db, 'npc_id', '') or '')}",
                "fact_id": FACT_ID,
                "mode": "DIRECT_LOCAL",
                "source_name": caller.key,
                "source_dbref": int(caller.id),
                "source_npc_id": "",
                "target_name": informant.key,
                "target_dbref": int(informant.id),
                "target_npc_id": str(getattr(informant.db, "npc_id", "") or ""),
                "shared_at": "V061-VALIDATOR-SEED",
            }
        ],
    }


class CmdSizaResetV61(Command):
    key = "siza-reset-v61"
    aliases = ["reset-v61"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v61_playtest_state()
        if not result.get("success"):
            self.caller.msg(f"[V0.61 RESET] FAIL | reason={result.get('reason')}")
            return
        mara = result.get("mara")
        fact = find_knowledge_fact(mara, FACT_ID)
        level = knowledge_levels(mara).get(KNOWLEDGE_KEY, 0)
        self.caller.msg(f"=== SIZA v0.61 RESET | {PILOT_BUILD} ===")
        self.caller.msg(
            f"PASS secondary-behavior reset | mara={mara.key}#{mara.id} @ {mara.location.key if mara.location else None} | "
            f"goal_removed={result.get('goal_removed')} | fact_preserved={fact is not None} | knowledge={level}"
        )
        self.caller.msg("No se tocaron el Fact transferido, su provenance, el Informante ni estados v0.57-v0.60.")
        self.caller.msg("========================================================")


class CmdSizaValidateV61(Command):
    key = "siza-validate-v61"
    aliases = ["validate-v61"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v61_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.61 VALIDATION] FAIL | context={context}")
            return

        informant = context.get("informant")
        mara = context.get("mara")
        manifest = context.get("manifest")
        informant_site = context.get("informant_site")
        mara_start = context.get("mara_start")
        destination = context.get("destination")

        original = {
            "informant_location": informant.location,
            "informant_knowledge": _clone(getattr(informant.db, "knowledge", {})),
            "informant_facts": _clone(getattr(informant.db, "knowledge_facts", [])),
            "informant_goals": _clone(getattr(informant.db, "decision_goals", [])),
            "informant_current_goal": _clone(getattr(informant.db, "current_goal", None)),
            "informant_current_activity": getattr(informant.db, "current_activity", None),
            "informant_destination_id": getattr(informant.db, "destination_id", None),
            "informant_decision_enabled": bool(getattr(informant.db, "decision_enabled", False)),
            "mara_location": mara.location,
            "mara_knowledge": _clone(getattr(mara.db, "knowledge", {})),
            "mara_facts": _clone(getattr(mara.db, "knowledge_facts", [])),
            "mara_goals": _clone(getattr(mara.db, "decision_goals", [])),
            "mara_rules": _clone(getattr(mara.db, "fact_goal_rules", [])),
            "mara_current_goal": _clone(getattr(mara.db, "current_goal", None)),
            "mara_current_activity": getattr(mara.db, "current_activity", None),
            "mara_destination_id": getattr(mara.db, "destination_id", None),
            "mara_decision_enabled": bool(getattr(mara.db, "decision_enabled", False)),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.61 | {PILOT_BUILD} ===")
        self.caller.msg(
            f"Chain: {informant.key}#{informant.id} -> {mara.key}#{mara.id} | fact={FACT_ID} | mara_goal={GOAL_ID} | target={TARGET_ROOM_KEY}"
        )

        try:
            reset_v60_playtest_state()
            reset_v61_playtest_state()
            informant.db.decision_enabled = True
            mara.db.decision_enabled = True

            check(
                "mara-fact-goal-rule-is-installed-once",
                _rule_count(mara) == 1,
                f"rules={_rule_count(mara)}",
            )

            decision_before = choose_goal(mara)
            check(
                "mara-does-not-materialize-secondary-goal-before-receiving-fact",
                _goal_count(mara) == 0
                and not any(str(row.get("id") or "") == GOAL_ID for row in (decision_before.get("candidates") or [])),
                f"goal_count={_goal_count(mara)} winner={((decision_before.get('selected') or {}).get('id'))}",
            )

            seed = _pilot_fact(self.caller, informant_site, manifest, informant)
            upsert_knowledge_fact(informant, seed)
            set_knowledge_level(informant, KNOWLEDGE_KEY, 1)

            i1 = decision_step(informant, prepare_world_state=False)
            i2 = decision_step(informant, prepare_world_state=False)
            i3 = decision_step(informant, prepare_world_state=False)
            mara_fact = find_knowledge_fact(mara, FACT_ID)
            history = _plain_list((mara_fact or {}).get("transfer_history"))
            check(
                "v060-propagation-delivers-known-fact-to-mara-before-secondary-behavior",
                i1.get("status") == "MOVED_GOAL"
                and i2.get("status") == "MOVED_GOAL"
                and i3.get("status") == "GOAL_COMPLETED"
                and mara_fact is not None
                and fact_knowledge_state(mara, mara_fact).get("known") is True
                and len(history) == 2,
                f"informant_steps={i1.get('status')},{i2.get('status')},{i3.get('status')} mara_known={None if mara_fact is None else fact_knowledge_state(mara, mara_fact).get('known')} history={len(history)}",
            )

            fact_before_behavior = _clone(mara_fact)
            decision = choose_goal(mara)
            selected = decision.get("selected") or {}
            goal = find_decision_goal(mara, GOAL_ID)
            check(
                "propagated-fact-materializes-one-persistent-mara-goal",
                _goal_count(mara) == 1
                and goal is not None
                and goal.get("active") is True
                and goal.get("source_fact_id") == FACT_ID
                and goal.get("fact_goal_rule_id") == RULE_ID,
                f"goals={_goal_count(mara)} active={None if goal is None else goal.get('active')}",
            )

            check(
                "mara-secondary-goal-wins-normal-decision-selection",
                selected.get("id") == GOAL_ID
                and selected.get("target_room_id") == TARGET_ROOM_ID
                and selected.get("target_name") == TARGET_ROOM_KEY
                and selected.get("path_length") == 3,
                f"winner={selected.get('id')} target={selected.get('target_name')} path={selected.get('path_length')}",
            )

            m1 = decision_step(mara, prepare_world_state=False)
            check(
                "mara-follows-real-exit-cantina-to-plaza",
                m1.get("status") == "MOVED_GOAL"
                and m1.get("goal_id") == GOAL_ID
                and m1.get("from") == "Cantina de Turno"
                and m1.get("to") == "Plaza de Recepcion",
                f"status={m1.get('status')} {m1.get('from')}->{m1.get('to')}",
            )

            m2 = decision_step(mara, prepare_world_state=False)
            check(
                "mara-follows-real-exit-plaza-to-calle",
                m2.get("status") == "MOVED_GOAL"
                and m2.get("goal_id") == GOAL_ID
                and m2.get("from") == "Plaza de Recepcion"
                and m2.get("to") == "Calle de Servicio",
                f"status={m2.get('status')} {m2.get('from')}->{m2.get('to')}",
            )

            m3 = decision_step(mara, prepare_world_state=False)
            completed_goal = find_decision_goal(mara, GOAL_ID)
            check(
                "mara-arrival-completes-and-disables-secondary-goal",
                m3.get("status") == "GOAL_COMPLETED"
                and m3.get("goal_id") == GOAL_ID
                and m3.get("from") == "Calle de Servicio"
                and m3.get("to") == TARGET_ROOM_KEY
                and mara.location == destination
                and completed_goal is not None
                and completed_goal.get("active") is False,
                f"status={m3.get('status')} location={mara.location.key if mara.location else None} active={None if completed_goal is None else completed_goal.get('active')}",
            )

            after = choose_goal(mara)
            check(
                "completed-secondary-goal-does-not-rematerialize",
                _goal_count(mara) == 1
                and find_decision_goal(mara, GOAL_ID).get("active") is False
                and str(((after.get("selected") or {}).get("id") or "")) != GOAL_ID,
                f"goals={_goal_count(mara)} winner={((after.get('selected') or {}).get('id'))}",
            )

            check(
                "mara-behavior-does-not-consume-or-rewrite-propagated-fact",
                _clone(find_knowledge_fact(mara, FACT_ID)) == fact_before_behavior
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1,
                f"fact_unchanged={_clone(find_knowledge_fact(mara, FACT_ID)) == fact_before_behavior} knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY)}",
            )

            reset_v61_playtest_state()
            mara.db.decision_enabled = True
            t1 = simulate_npc_tick(mara)
            t2 = simulate_npc_tick(mara)
            t3 = simulate_npc_tick(mara)
            check(
                "autonomous-world-tick-executes-same-secondary-behavior",
                t1.get("status") == "MOVED_GOAL"
                and t2.get("status") == "MOVED_GOAL"
                and t3.get("status") == "GOAL_COMPLETED"
                and t3.get("goal_id") == GOAL_ID
                and mara.location == destination,
                f"ticks={t1.get('status')},{t2.get('status')},{t3.get('status')} location={mara.location.key if mara.location else None}",
            )

            reset = reset_v61_playtest_state()
            check(
                "v061-reset-cleans-only-secondary-goal-and-preserves-mara-fact",
                reset.get("success") is True
                and _goal_count(mara) == 0
                and find_knowledge_fact(mara, FACT_ID) is not None
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1
                and mara.location == mara_start,
                f"goals={_goal_count(mara)} fact={find_knowledge_fact(mara, FACT_ID) is not None} location={mara.location.key if mara.location else None}",
            )

            ensure_v61_pilot_content()
            check(
                "v061-install-is-idempotent",
                _rule_count(mara) == 1,
                f"rules={_rule_count(mara)} build={FACT_DRIVEN_DECISION_BUILD}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if informant.location != original["informant_location"]:
                    informant.move_to(original["informant_location"], quiet=True)
            except Exception:
                pass
            informant.db.knowledge = original["informant_knowledge"]
            informant.db.knowledge_facts = original["informant_facts"]
            informant.db.decision_goals = original["informant_goals"]
            informant.db.current_goal = original["informant_current_goal"]
            informant.db.current_activity = original["informant_current_activity"]
            informant.db.destination_id = original["informant_destination_id"]
            informant.db.decision_enabled = original["informant_decision_enabled"]

            try:
                if mara.location != original["mara_location"]:
                    mara.move_to(original["mara_location"], quiet=True)
            except Exception:
                pass
            mara.db.knowledge = original["mara_knowledge"]
            mara.db.knowledge_facts = original["mara_facts"]
            mara.db.decision_goals = original["mara_goals"]
            mara.db.fact_goal_rules = original["mara_rules"]
            mara.db.current_goal = original["mara_current_goal"]
            mara.db.current_activity = original["mara_current_activity"]
            mara.db.destination_id = original["mara_destination_id"]
            mara.db.decision_enabled = original["mara_decision_enabled"]

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Informant/Mara locations, Knowledge/Facts, goals, Mara fact-goal rules and decision modes restored"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: propagated Fact -> second NPC goal -> autonomous secondary behavior"
        )
        self.caller.msg("========================================================")
