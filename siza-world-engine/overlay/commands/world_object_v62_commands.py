from evennia import Command

from services.consequence_engine import get_consequence_registry
from services.fact_driven_decision import choose_goal, decision_step
from services.fact_goal_completion_engine import (
    FACT_GOAL_OBJECT_ACTION_BUILD,
    LEDGER_ATTR,
    apply_goal_completion_effects,
    completion_rules,
)
from services.fact_goal_engine import find_decision_goal
from services.knowledge_context_engine import knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.object_action_engine import find_object_action, object_action_history
from typeclasses.world_tick import simulate_npc_tick
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v57 import (
    ACTION_ID as V57_ACTION_ID,
    FACT_ID,
    FACT_TEXT,
    FACT_TOPIC,
    KNOWLEDGE_KEY,
)
from world.upgrade_pilot_v61 import GOAL_ID as V61_GOAL_ID
from world.upgrade_pilot_v62 import (
    ACTION_ID,
    COMPLETION_RULE_ID,
    CONSEQUENCE_RULE_ID,
    PILOT_BUILD,
    VERIFIED_FIELD,
    ensure_v62_pilot_content,
    reset_v62_playtest_state,
    v62_completion_rule_count,
    v62_consequence_rule_count,
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


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _pilot_fact(mara, manifest, site):
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
            "attempt_id": "V062-VALIDATOR-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V062-VALIDATOR-SEED",
        },
        "transfer_history": [
            {
                "id": f"V062-SEED:{FACT_ID}",
                "fact_id": FACT_ID,
                "mode": "VALIDATOR_SEED",
                "source_name": "validated propagation chain",
                "source_dbref": None,
                "source_npc_id": "TEST-NPC-KAL-DAR-INFORMANT-C",
                "target_name": mara.key,
                "target_dbref": int(mara.id),
                "target_npc_id": str(getattr(mara.db, "npc_id", "") or ""),
                "shared_at": "V062-VALIDATOR-SEED",
            }
        ],
    }


def _goal_count(npc):
    total = 0
    for raw in _plain_list(getattr(npc.db, "decision_goals", [])):
        try:
            item = dict(raw)
        except Exception:
            continue
        if str(item.get("id") or "") == V61_GOAL_ID:
            total += 1
    return total


def _history_count(npc):
    return sum(1 for row in object_action_history(npc) if str(row.get("object_action_id") or "") == ACTION_ID)


class CmdSizaV62ManifestState(Command):
    key = "siza-v62-manifest"
    aliases = ["v62-manifest"]
    locks = "cmd:all()"

    def func(self):
        context = ensure_v62_pilot_content()
        if not context.get("success"):
            self.caller.msg(f"[V0.62] FAIL | reason={context.get('reason')}")
            return
        mara = context.get("mara")
        manifest = context.get("manifest")
        state = _plain_dict(getattr(manifest.db, "state", {}))
        ledger = [str(value) for value in _plain_list(getattr(mara.db, LEDGER_ATTR, [])) if value]
        completion_action_id = f"FACT_GOAL_COMPLETION:{V61_GOAL_ID}:{COMPLETION_RULE_ID}"
        action = find_object_action(mara, manifest, ACTION_ID, eligible_only=False)
        self.caller.msg(f"=== SIZA v0.62 MANIFEST | {PILOT_BUILD} ===")
        self.caller.msg(
            f"Manifest: {manifest.key}#{manifest.id} | {VERIFIED_FIELD}={state.get(VERIFIED_FIELD)}"
        )
        self.caller.msg(
            f"Mara: {mara.key}#{mara.id} @ {mara.location.key if mara.location else None} | "
            f"completion_applied={completion_action_id in ledger} | object_action_history={_history_count(mara)}"
        )
        self.caller.msg(
            f"Object action: {ACTION_ID} | available_record={action is not None} | "
            f"eligible={None if action is None else action.get('eligible')} | blockers={None if action is None else action.get('blockers')}"
        )
        self.caller.msg("========================================================")


class CmdSizaResetV62(Command):
    key = "siza-reset-v62"
    aliases = ["reset-v62"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v62_playtest_state()
        if not result.get("success"):
            self.caller.msg(f"[V0.62 RESET] FAIL | reason={result.get('reason')}")
            return
        mara = result.get("mara")
        manifest = result.get("manifest")
        self.caller.msg(f"=== SIZA v0.62 RESET | {PILOT_BUILD} ===")
        self.caller.msg(
            f"PASS verification reset | mara={mara.key}#{mara.id} @ {mara.location.key if mara.location else None} | "
            f"goal_removed={result.get('goal_removed')} | {VERIFIED_FIELD}: {result.get('verified_before')} -> {result.get('verified_after')} | "
            f"ledger_removed={result.get('ledger_removed')}"
        )
        self.caller.msg(
            f"Fact preserved={find_knowledge_fact(mara, FACT_ID) is not None} | knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY, 0)} | manifest={manifest.key}#{manifest.id}"
        )
        self.caller.msg("No se tocaron Facts/provenance de Mara ni estados anteriores del Manifiesto.")
        self.caller.msg("========================================================")


class CmdSizaValidateV62(Command):
    key = "siza-validate-v62"
    aliases = ["validate-v62"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v62_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.62 VALIDATION] FAIL | context={context}")
            return

        mara = context.get("mara")
        manifest = context.get("manifest")
        start = context.get("start")
        destination = context.get("destination")
        registry = get_consequence_registry(create=True)

        original = {
            "mara_location": mara.location,
            "mara_knowledge": _clone(getattr(mara.db, "knowledge", {})),
            "mara_facts": _clone(getattr(mara.db, "knowledge_facts", [])),
            "mara_goals": _clone(getattr(mara.db, "decision_goals", [])),
            "mara_rules": _clone(getattr(mara.db, "fact_goal_rules", [])),
            "mara_completion_rules": _clone(getattr(mara.db, "fact_goal_completion_rules", [])),
            "mara_completion_ledger": _clone(getattr(mara.db, LEDGER_ATTR, [])),
            "mara_action_history": _clone(getattr(mara.db, "object_action_history", [])),
            "mara_current_goal": _clone(getattr(mara.db, "current_goal", None)),
            "mara_current_activity": getattr(mara.db, "current_activity", None),
            "mara_destination_id": getattr(mara.db, "destination_id", None),
            "mara_decision_enabled": bool(getattr(mara.db, "decision_enabled", False)),
            "manifest_state": _clone(getattr(manifest.db, "state", {})),
            "manifest_actions": _clone(getattr(manifest.db, "object_actions", [])),
            "processed": _clone(getattr(registry.db, "processed_action_ids", [])),
            "log": _clone(getattr(registry.db, "action_log", [])),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.62 | {PILOT_BUILD} ===")
        self.caller.msg(
            f"NPC: {mara.key}#{mara.id} | goal={V61_GOAL_ID} -> object={manifest.key}#{manifest.id} | action={ACTION_ID}"
        )

        try:
            reset_v62_playtest_state()
            if find_knowledge_fact(mara, FACT_ID) is None:
                upsert_knowledge_fact(mara, _pilot_fact(mara, manifest, destination))
            set_knowledge_level(mara, KNOWLEDGE_KEY, 1)
            mara.db.decision_enabled = True

            check(
                "v062-rules-and-authored-object-action-installed-once",
                v62_completion_rule_count() == 1
                and v62_consequence_rule_count() == 1
                and sum(1 for row in _plain_list(getattr(manifest.db, "object_actions", [])) if str((_plain_dict(row)).get("id") or "") == ACTION_ID) == 1,
                f"completion_rules={v62_completion_rule_count()} consequence_rules={v62_consequence_rule_count()}",
            )

            check(
                "reset-starts-unverified-and-preserves-mara-fact",
                _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is False
                and find_knowledge_fact(mara, FACT_ID) is not None
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1
                and mara.location == start,
                f"verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)} fact={find_knowledge_fact(mara, FACT_ID) is not None} location={mara.location.key if mara.location else None}",
            )

            decision = choose_goal(mara)
            selected = decision.get("selected") or {}
            check(
                "known-fact-still-drives-mara-v061-goal",
                selected.get("id") == V61_GOAL_ID and selected.get("target_name") == destination.key,
                f"winner={selected.get('id')} target={selected.get('target_name')}",
            )

            fact_before = _clone(find_knowledge_fact(mara, FACT_ID))
            h_before = _history_count(mara)
            s1 = decision_step(mara, prepare_world_state=False)
            s2 = decision_step(mara, prepare_world_state=False)
            s3 = decision_step(mara, prepare_world_state=False)
            completion = _plain_dict(s3.get("fact_goal_completion"))
            rows = _plain_list(completion.get("results"))
            object_effect = next((_plain_dict(row) for row in rows if _plain_dict(row).get("rule_id") == COMPLETION_RULE_ID), {})
            object_action = _plain_dict(object_effect.get("object_action"))

            check(
                "goal-completion-dispatches-authored-object-action",
                s1.get("status") == "MOVED_GOAL"
                and s2.get("status") == "MOVED_GOAL"
                and s3.get("status") == "GOAL_COMPLETED"
                and completion.get("status") == "APPLIED"
                and object_effect.get("effect_type") == "OBJECT_ACTION"
                and object_effect.get("status") == "APPLIED"
                and object_action.get("status") == "COMPLETED"
                and object_action.get("object_action_id") == ACTION_ID,
                f"steps={s1.get('status')},{s2.get('status')},{s3.get('status')} completion={completion.get('status')} effect={object_effect.get('status')} object_action={object_action.get('status')}",
            )

            check(
                "mara-object-action-runs-only-after-reaching-real-manifest-location",
                s3.get("to") == destination.key
                and mara.location == destination
                and object_action.get("site_room_id") == str(getattr(destination.db, "room_id", "") or "")
                and object_action.get("object_id") == MANIFEST_ID,
                f"location={mara.location.key if mara.location else None} action_site={object_action.get('site_room_id')} object={object_action.get('object_id')}",
            )

            state_after = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "object-action-consequence-persists-manifest-verification-state",
                state_after.get(VERIFIED_FIELD) is True,
                f"{VERIFIED_FIELD}={state_after.get(VERIFIED_FIELD)}",
            )

            consequence = _plain_dict(object_action.get("action_consequence"))
            check(
                "verification-flows-through-existing-consequence-engine",
                consequence.get("status") == "PROCESSED"
                and str(consequence.get("action_id") or "").startswith("OBJECT_ACTION_COMPLETED:")
                and any(str((_plain_dict(row)).get("rule_id") or "") == CONSEQUENCE_RULE_ID for row in _plain_list(consequence.get("results"))),
                f"status={consequence.get('status')} action_id={consequence.get('action_id')}",
            )

            check(
                "mara-object-action-is-recorded-in-existing-object-action-history",
                _history_count(mara) == h_before + 1
                and any(str(row.get("object_action_id") or "") == ACTION_ID and row.get("status") == "COMPLETED" for row in object_action_history(mara)),
                f"before={h_before} after={_history_count(mara)}",
            )

            replay = apply_goal_completion_effects(mara, s3)
            replay_rows = _plain_list(replay.get("results"))
            replay_effect = next((_plain_dict(row) for row in replay_rows if _plain_dict(row).get("rule_id") == COMPLETION_RULE_ID), {})
            check(
                "goal-completion-object-action-is-idempotent",
                replay_effect.get("status") == "ALREADY_APPLIED"
                and _history_count(mara) == h_before + 1
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is True,
                f"status={replay_effect.get('status')} history={_history_count(mara)} verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)}",
            )

            check(
                "verification-does-not-consume-or-rewrite-mara-fact",
                _clone(find_knowledge_fact(mara, FACT_ID)) == fact_before
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1,
                f"fact_unchanged={_clone(find_knowledge_fact(mara, FACT_ID)) == fact_before} knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY)}",
            )

            completed_goal = find_decision_goal(mara, V61_GOAL_ID)
            after = choose_goal(mara)
            check(
                "verified-one-shot-goal-remains-completed-and-inactive",
                completed_goal is not None
                and completed_goal.get("active") is False
                and str(((after.get("selected") or {}).get("id") or "")) != V61_GOAL_ID,
                f"active={None if completed_goal is None else completed_goal.get('active')} winner={((after.get('selected') or {}).get('id'))}",
            )

            reset_v62_playtest_state()
            mara.db.decision_enabled = True
            h_tick_before = _history_count(mara)
            t1 = simulate_npc_tick(mara)
            t2 = simulate_npc_tick(mara)
            t3 = simulate_npc_tick(mara)
            tick_completion = _plain_dict(t3.get("fact_goal_completion"))
            tick_rows = _plain_list(tick_completion.get("results"))
            tick_effect = next((_plain_dict(row) for row in tick_rows if _plain_dict(row).get("rule_id") == COMPLETION_RULE_ID), {})
            check(
                "autonomous-world-tick-executes-same-object-verification",
                t1.get("status") == "MOVED_GOAL"
                and t2.get("status") == "MOVED_GOAL"
                and t3.get("status") == "GOAL_COMPLETED"
                and tick_effect.get("status") == "APPLIED"
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is True
                and _history_count(mara) == h_tick_before + 1,
                f"ticks={t1.get('status')},{t2.get('status')},{t3.get('status')} effect={tick_effect.get('status')} verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)}",
            )

            reset = reset_v62_playtest_state()
            check(
                "v062-reset-cleans-only-verification-execution-state",
                reset.get("success") is True
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is False
                and find_knowledge_fact(mara, FACT_ID) is not None
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1
                and mara.location == start,
                f"verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)} fact={find_knowledge_fact(mara, FACT_ID) is not None} location={mara.location.key if mara.location else None}",
            )

            ensure_v62_pilot_content()
            check(
                "v062-install-is-idempotent",
                v62_completion_rule_count() == 1
                and v62_consequence_rule_count() == 1
                and sum(1 for row in _plain_list(getattr(manifest.db, "object_actions", [])) if str((_plain_dict(row)).get("id") or "") == ACTION_ID) == 1,
                f"completion_rules={v62_completion_rule_count()} consequence_rules={v62_consequence_rule_count()} build={FACT_GOAL_OBJECT_ACTION_BUILD}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if mara.location != original["mara_location"]:
                    mara.move_to(original["mara_location"], quiet=True)
            except Exception:
                pass
            mara.db.knowledge = original["mara_knowledge"]
            mara.db.knowledge_facts = original["mara_facts"]
            mara.db.decision_goals = original["mara_goals"]
            mara.db.fact_goal_rules = original["mara_rules"]
            mara.db.fact_goal_completion_rules = original["mara_completion_rules"]
            setattr(mara.db, LEDGER_ATTR, original["mara_completion_ledger"])
            mara.db.object_action_history = original["mara_action_history"]
            mara.db.current_goal = original["mara_current_goal"]
            mara.db.current_activity = original["mara_current_activity"]
            mara.db.destination_id = original["mara_destination_id"]
            mara.db.decision_enabled = original["mara_decision_enabled"]
            manifest.db.state = original["manifest_state"]
            manifest.db.object_actions = original["manifest_actions"]
            registry.db.processed_action_ids = original["processed"]
            registry.db.action_log = original["log"]

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Mara location/Knowledge/Facts/goals/completion ledger/object-action history, Manifest state/actions and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: GOAL_COMPLETED -> OBJECT_ACTION -> Consequence Engine -> persistent object state"
        )
        self.caller.msg("========================================================")
