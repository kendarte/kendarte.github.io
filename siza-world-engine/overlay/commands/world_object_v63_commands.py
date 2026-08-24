from evennia import Command

from services.consequence_engine import (
    NPC_KNOWLEDGE_FACT_CONSEQUENCE_BUILD,
    get_consequence_registry,
)
from services.fact_driven_decision import choose_goal, decision_step
from services.fact_goal_completion_engine import LEDGER_ATTR, apply_goal_completion_effects
from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts, knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.object_action_engine import object_action_history
from typeclasses.world_tick import simulate_npc_tick
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v57 import (
    ACTION_ID as V57_ACTION_ID,
    FACT_ID as V57_FACT_ID,
    FACT_TEXT as V57_FACT_TEXT,
    FACT_TOPIC as V57_FACT_TOPIC,
    KNOWLEDGE_KEY as V57_KNOWLEDGE_KEY,
)
from world.upgrade_pilot_v61 import GOAL_ID as V61_GOAL_ID
from world.upgrade_pilot_v62 import (
    ACTION_ID as V62_ACTION_ID,
    CONSEQUENCE_RULE_ID as V62_CONSEQUENCE_RULE_ID,
    VERIFIED_FIELD,
)
from world.upgrade_pilot_v63 import (
    FACT_ID,
    FACT_TEXT,
    KNOWLEDGE_KEY,
    PILOT_BUILD,
    RULE_ID,
    ensure_v63_pilot_content,
    reset_v63_playtest_state,
    v63_rule_count,
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


def _fact_count(entity, fact_id):
    return sum(1 for row in knowledge_facts(entity) if str(row.get("id") or "") == str(fact_id or ""))


def _v57_seed_fact(mara, manifest, site):
    return {
        "id": V57_FACT_ID,
        "topic": V57_FACT_TOPIC,
        "text": V57_FACT_TEXT,
        "knowledge_key": V57_KNOWLEDGE_KEY,
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
            "attempt_id": "V063-VALIDATOR-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V063-VALIDATOR-SEED",
        },
        "transfer_history": [
            {
                "id": f"V063-SEED:{V57_FACT_ID}",
                "fact_id": V57_FACT_ID,
                "mode": "VALIDATOR_SEED",
                "source_name": "validated propagation chain",
                "source_dbref": None,
                "source_npc_id": "TEST-NPC-KAL-DAR-INFORMANT-C",
                "target_name": mara.key,
                "target_dbref": int(mara.id),
                "target_npc_id": str(getattr(mara.db, "npc_id", "") or ""),
                "shared_at": "V063-VALIDATOR-SEED",
            }
        ],
    }


def _v62_history_count(mara):
    return sum(
        1
        for row in object_action_history(mara)
        if str(row.get("object_action_id") or "") == V62_ACTION_ID
    )


def _find_rule_result(consequence, rule_id):
    for raw in _plain_list((consequence or {}).get("results")):
        row = _plain_dict(raw)
        if str(row.get("rule_id") or "") == str(rule_id or ""):
            return row
    return {}


class CmdSizaV63Fact(Command):
    key = "siza-v63-fact"
    aliases = ["v63-fact"]
    locks = "cmd:all()"

    def func(self):
        context = ensure_v63_pilot_content()
        if not context.get("success"):
            self.caller.msg(f"[V0.63] FAIL | reason={context.get('reason')}")
            return
        mara = context.get("mara")
        fact = find_knowledge_fact(mara, FACT_ID)
        state = fact_knowledge_state(mara, fact) if fact else {}
        source = _plain_dict((fact or {}).get("source"))
        learned = _plain_dict((fact or {}).get("learned_by"))
        self.caller.msg(f"=== SIZA v0.63 NPC FACT | {PILOT_BUILD} ===")
        self.caller.msg(
            f"Mara: {mara.key}#{mara.id} | fact={FACT_ID} | exists={fact is not None} | "
            f"known={state.get('known')} | knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY, 0)}"
        )
        if fact:
            self.caller.msg(f"text={fact.get('text')}")
            self.caller.msg(
                f"source={source.get('object_name')} | object_id={source.get('object_id')} | site={source.get('site_name')} ({source.get('site_room_id')})"
            )
            self.caller.msg(
                f"learned_by={learned.get('action_id')} | object_action={learned.get('object_action_id')} | attempt={learned.get('attempt_id')} | outcome={learned.get('outcome')}"
            )
            self.caller.msg(f"transfer_history={len(_plain_list(fact.get('transfer_history')))}")
        self.caller.msg("========================================================")


class CmdSizaResetV63(Command):
    key = "siza-reset-v63"
    aliases = ["reset-v63"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v63_playtest_state()
        if not result.get("success"):
            self.caller.msg(f"[V0.63 RESET] FAIL | reason={result.get('reason')}")
            return
        mara = result.get("mara")
        self.caller.msg(f"=== SIZA v0.63 RESET | {PILOT_BUILD} ===")
        self.caller.msg(
            f"PASS self-discovery reset | mara={mara.key}#{mara.id} @ {mara.location.key if mara.location else None} | "
            f"fact_removed={result.get('fact_removed')} | knowledge_before={result.get('knowledge_before')} | verified={result.get('verified_after')}"
        )
        self.caller.msg(
            f"Transferred source Fact preserved={find_knowledge_fact(mara, V57_FACT_ID) is not None} | "
            f"source knowledge={knowledge_levels(mara).get(V57_KNOWLEDGE_KEY, 0)}"
        )
        self.caller.msg("========================================================")


class CmdSizaValidateV63(Command):
    key = "siza-validate-v63"
    aliases = ["validate-v63"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.63 VALIDATION] FAIL | context={context}")
            return

        mara = context.get("mara")
        manifest = context.get("manifest")
        start = context.get("start")
        destination = context.get("destination")
        registry = get_consequence_registry(create=True)

        original = {
            "location": mara.location,
            "knowledge": _clone(getattr(mara.db, "knowledge", {})),
            "facts": _clone(getattr(mara.db, "knowledge_facts", [])),
            "goals": _clone(getattr(mara.db, "decision_goals", [])),
            "completion_ledger": _clone(getattr(mara.db, LEDGER_ATTR, [])),
            "action_history": _clone(getattr(mara.db, "object_action_history", [])),
            "current_goal": _clone(getattr(mara.db, "current_goal", None)),
            "current_activity": getattr(mara.db, "current_activity", None),
            "destination_id": getattr(mara.db, "destination_id", None),
            "decision_enabled": bool(getattr(mara.db, "decision_enabled", False)),
            "manifest_state": _clone(getattr(manifest.db, "state", {})),
            "processed": _clone(getattr(registry.db, "processed_action_ids", [])),
            "log": _clone(getattr(registry.db, "action_log", [])),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.63 | {PILOT_BUILD} ===")
        self.caller.msg(
            f"NPC: {mara.key}#{mara.id} | source_action={V62_ACTION_ID} | new_fact={FACT_ID} | core={NPC_KNOWLEDGE_FACT_CONSEQUENCE_BUILD}"
        )

        try:
            reset_v63_playtest_state()
            if find_knowledge_fact(mara, V57_FACT_ID) is None:
                upsert_knowledge_fact(mara, _v57_seed_fact(mara, manifest, destination))
            set_knowledge_level(mara, V57_KNOWLEDGE_KEY, 1)
            mara.db.decision_enabled = True

            check(
                "npc-structured-fact-core-and-v063-rule-installed",
                NPC_KNOWLEDGE_FACT_CONSEQUENCE_BUILD == "0.63.0-npc-structured-knowledge-facts"
                and v63_rule_count() == 1,
                f"core={NPC_KNOWLEDGE_FACT_CONSEQUENCE_BUILD} rules={v63_rule_count()}",
            )

            check(
                "reset-removes-only-v063-discovery-and-preserves-transferred-source-fact",
                find_knowledge_fact(mara, FACT_ID) is None
                and knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) == 0
                and find_knowledge_fact(mara, V57_FACT_ID) is not None
                and knowledge_levels(mara).get(V57_KNOWLEDGE_KEY) == 1
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is False
                and mara.location == start,
                f"new_fact={find_knowledge_fact(mara, FACT_ID) is not None} source_fact={find_knowledge_fact(mara, V57_FACT_ID) is not None} verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)}",
            )

            source_fact_before = _clone(find_knowledge_fact(mara, V57_FACT_ID))
            decision = choose_goal(mara)
            selected = decision.get("selected") or {}
            check(
                "source-fact-still-drives-existing-v061-goal",
                selected.get("id") == V61_GOAL_ID and selected.get("target_name") == destination.key,
                f"winner={selected.get('id')} target={selected.get('target_name')}",
            )

            history_before = _v62_history_count(mara)
            s1 = decision_step(mara, prepare_world_state=False)
            s2 = decision_step(mara, prepare_world_state=False)
            s3 = decision_step(mara, prepare_world_state=False)
            completion = _plain_dict(s3.get("fact_goal_completion"))
            completion_rows = [_plain_dict(row) for row in _plain_list(completion.get("results"))]
            object_effect = next((row for row in completion_rows if row.get("effect_type") == "OBJECT_ACTION"), {})
            object_action = _plain_dict(object_effect.get("object_action"))
            consequence = _plain_dict(object_action.get("action_consequence"))

            check(
                "v062-object-verification-path-regression-remains-intact",
                s1.get("status") == "MOVED_GOAL"
                and s2.get("status") == "MOVED_GOAL"
                and s3.get("status") == "GOAL_COMPLETED"
                and object_effect.get("status") == "APPLIED"
                and object_action.get("status") == "COMPLETED"
                and object_action.get("object_action_id") == V62_ACTION_ID
                and mara.location == destination,
                f"steps={s1.get('status')},{s2.get('status')},{s3.get('status')} object_action={object_action.get('status')} location={mara.location.key if mara.location else None}",
            )

            v62_rule_result = _find_rule_result(consequence, V62_CONSEQUENCE_RULE_ID)
            check(
                "existing-state-effect-regression-still-persists-v062-verification",
                consequence.get("status") == "PROCESSED"
                and v62_rule_result.get("status") == "APPLIED"
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is True,
                f"consequence={consequence.get('status')} rule={v62_rule_result.get('status')} verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)}",
            )

            v63_rule_result = _find_rule_result(consequence, RULE_ID)
            applied_rows = [_plain_dict(row) for row in _plain_list(v63_rule_result.get("applied"))]
            applied = applied_rows[0] if applied_rows else {}
            check(
                "npc-core-applies-numeric-knowledge-and-structured-fact-together",
                v63_rule_result.get("status") == "APPLIED"
                and applied.get("knowledge_applied") is True
                and applied.get("knowledge_fact_applied") is True
                and applied.get("knowledge_after") == 1
                and applied.get("fact_id") == FACT_ID
                and applied.get("knowledge_fact_build") == NPC_KNOWLEDGE_FACT_CONSEQUENCE_BUILD,
                f"rule={v63_rule_result.get('status')} knowledge_applied={applied.get('knowledge_applied')} fact_applied={applied.get('knowledge_fact_applied')} fact={applied.get('fact_id')}",
            )

            new_fact = find_knowledge_fact(mara, FACT_ID)
            new_state = fact_knowledge_state(mara, new_fact) if new_fact else {}
            check(
                "mara-learns-one-new-known-fact-from-own-object-interaction",
                new_fact is not None
                and _fact_count(mara, FACT_ID) == 1
                and new_state.get("known") is True
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1
                and new_fact.get("text") == FACT_TEXT,
                f"facts={_fact_count(mara, FACT_ID)} known={new_state.get('known')} knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY)}",
            )

            source = _plain_dict((new_fact or {}).get("source"))
            check(
                "self-discovered-fact-points-to-real-manifest-and-real-site",
                source.get("object_id") == MANIFEST_ID
                and source.get("object_name") == manifest.key
                and source.get("site_room_id") == str(getattr(destination.db, "room_id", "") or "")
                and source.get("site_name") == destination.key,
                f"source={source}",
            )

            learned = _plain_dict((new_fact or {}).get("learned_by"))
            check(
                "self-discovered-fact-provenance-records-object-action-not-social-transfer",
                str(learned.get("action_id") or "").startswith("OBJECT_ACTION_COMPLETED:")
                and learned.get("object_action_id") == V62_ACTION_ID
                and learned.get("attempt_id") == object_action.get("attempt_id")
                and learned.get("outcome") == "COMPLETED"
                and len(_plain_list((new_fact or {}).get("transfer_history"))) == 0,
                f"learned_by={learned} transfer_history={len(_plain_list((new_fact or {}).get('transfer_history')))}",
            )

            check(
                "new-discovery-does-not-rewrite-original-transferred-fact",
                _clone(find_knowledge_fact(mara, V57_FACT_ID)) == source_fact_before
                and knowledge_levels(mara).get(V57_KNOWLEDGE_KEY) == 1,
                f"source_fact_unchanged={_clone(find_knowledge_fact(mara, V57_FACT_ID)) == source_fact_before}",
            )

            check(
                "existing-object-action-history-still-records-one-verification",
                _v62_history_count(mara) == history_before + 1,
                f"before={history_before} after={_v62_history_count(mara)}",
            )

            replay = apply_goal_completion_effects(mara, s3)
            check(
                "completion-replay-remains-idempotent-and-does-not-duplicate-new-fact",
                _fact_count(mara, FACT_ID) == 1
                and _v62_history_count(mara) == history_before + 1
                and all(_plain_dict(row).get("status") == "ALREADY_APPLIED" for row in _plain_list(replay.get("results"))),
                f"facts={_fact_count(mara, FACT_ID)} history={_v62_history_count(mara)} replay={replay.get('status')}",
            )

            reset_v63_playtest_state()
            if find_knowledge_fact(mara, V57_FACT_ID) is None:
                upsert_knowledge_fact(mara, _v57_seed_fact(mara, manifest, destination))
            set_knowledge_level(mara, V57_KNOWLEDGE_KEY, 1)
            mara.db.decision_enabled = True
            t1 = simulate_npc_tick(mara)
            t2 = simulate_npc_tick(mara)
            t3 = simulate_npc_tick(mara)
            tick_fact = find_knowledge_fact(mara, FACT_ID)
            check(
                "autonomous-world-tick-produces-same-self-discovered-fact",
                t1.get("status") == "MOVED_GOAL"
                and t2.get("status") == "MOVED_GOAL"
                and t3.get("status") == "GOAL_COMPLETED"
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is True
                and tick_fact is not None
                and fact_knowledge_state(mara, tick_fact).get("known") is True,
                f"ticks={t1.get('status')},{t2.get('status')},{t3.get('status')} verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)} fact={tick_fact is not None}",
            )

            reset = reset_v63_playtest_state()
            check(
                "v063-reset-cleans-new-discovery-but-preserves-source-fact",
                reset.get("success") is True
                and find_knowledge_fact(mara, FACT_ID) is None
                and knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) == 0
                and find_knowledge_fact(mara, V57_FACT_ID) is not None
                and knowledge_levels(mara).get(V57_KNOWLEDGE_KEY) == 1
                and _plain_dict(getattr(manifest.db, "state", {})).get(VERIFIED_FIELD) is False,
                f"new_fact={find_knowledge_fact(mara, FACT_ID) is not None} source_fact={find_knowledge_fact(mara, V57_FACT_ID) is not None} verified={_plain_dict(getattr(manifest.db, 'state', {})).get(VERIFIED_FIELD)}",
            )

            ensure_v63_pilot_content()
            check(
                "v063-install-is-idempotent",
                v63_rule_count() == 1,
                f"rules={v63_rule_count()}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if mara.location != original["location"]:
                    mara.move_to(original["location"], quiet=True)
            except Exception:
                pass
            mara.db.knowledge = original["knowledge"]
            mara.db.knowledge_facts = original["facts"]
            mara.db.decision_goals = original["goals"]
            setattr(mara.db, LEDGER_ATTR, original["completion_ledger"])
            mara.db.object_action_history = original["action_history"]
            mara.db.current_goal = original["current_goal"]
            mara.db.current_activity = original["current_activity"]
            mara.db.destination_id = original["destination_id"]
            mara.db.decision_enabled = original["decision_enabled"]
            manifest.db.state = original["manifest_state"]
            registry.db.processed_action_ids = original["processed"]
            registry.db.action_log = original["log"]

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} {'PASS' if passed == total else 'FAIL'}")
        self.caller.msg("")
        self.caller.msg("STATE RESTORED: Mara location/Knowledge/Facts/goals/completion ledger/object-action history, Manifest state and consequence log restored")
        self.caller.msg("")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: NPC Consequence knowledge_fact support + Mara direct-evidence Fact rule")
        self.caller.msg("")
        self.caller.msg("========================================================")
