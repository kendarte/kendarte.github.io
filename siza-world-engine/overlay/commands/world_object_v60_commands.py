from evennia import Command

from services.consequence_engine import get_consequence_registry
from services.fact_driven_decision import FACT_DRIVEN_DECISION_BUILD, choose_goal, decision_step
from services.fact_goal_completion_engine import (
    FACT_GOAL_COMPLETION_BUILD,
    LEDGER_ATTR,
    apply_goal_completion_effects,
    completion_rules,
)
from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts, knowledge_levels, set_knowledge_level
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
from world.upgrade_pilot_v59 import GOAL_ID
from world.upgrade_pilot_v60 import (
    COMPLETION_RULE_ID,
    MARA_NPC_ID,
    PILOT_BUILD,
    ensure_v60_pilot_content,
    reset_v60_playtest_state,
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


def _rule_count(npc):
    return sum(1 for row in completion_rules(npc) if str(row.get("id") or "") == COMPLETION_RULE_ID)


def _fact_count(entity):
    return sum(1 for row in knowledge_facts(entity) if str(row.get("id") or "") == FACT_ID)


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
            "attempt_id": "V060-VALIDATOR-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V060-VALIDATOR-SEED",
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
                "shared_at": "V060-VALIDATOR-SEED",
            }
        ],
    }


class CmdSizaFactCompletionsV60(Command):
    key = "siza-fact-completions"
    aliases = ["fact-completions"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("Uso: siza-fact-completions <NPC>")
            return
        ledger = [str(value) for value in _plain_list(getattr(npc.db, LEDGER_ATTR, [])) if value]
        self.caller.msg(f"=== SIZA FACT COMPLETIONS | {FACT_GOAL_COMPLETION_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | location={npc.location.key if npc.location else None}")
        rows = completion_rules(npc)
        if not rows:
            self.caller.msg("Rules: NONE")
        for rule in rows:
            action_id = f"FACT_GOAL_COMPLETION:{rule.get('goal_id')}:{rule.get('id')}"
            self.caller.msg(
                f"  rule={rule.get('id')} | goal={rule.get('goal_id')} | effect={rule.get('effect_type')} | "
                f"fact={rule.get('fact_id')} | target_npc_id={rule.get('target_npc_id')} | applied={action_id in ledger}"
            )
        self.caller.msg("========================================================")


class CmdSizaResetV60(Command):
    key = "siza-reset-v60"
    aliases = ["reset-v60"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v60_playtest_state()
        if not result.get("success"):
            self.caller.msg(f"[V0.60 RESET] FAIL | reason={result.get('reason')}")
            return
        informant = result.get("informant")
        mara = result.get("mara")
        self.caller.msg(f"=== SIZA v0.60 RESET | {FACT_DRIVEN_DECISION_BUILD} ===")
        self.caller.msg(
            f"PASS propagation reset | informant={informant.key}#{informant.id} @ {informant.location.key if informant.location else None} | "
            f"mara={mara.key}#{mara.id} @ {mara.location.key if mara.location else None} | "
            f"goal_removed={result.get('goal_removed')} | ledger_removed={result.get('ledger_removed')} | "
            f"mara_fact_removed={result.get('mara_fact_removed')}"
        )
        self.caller.msg("Se preservó el Fact/Knowledge del Informante; se limpió solo la copia v0.60 de Mara y el estado de ejecución del goal.")
        self.caller.msg("========================================================")


class CmdSizaValidateV60(Command):
    key = "siza-validate-v60"
    aliases = ["validate-v60"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v60_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.60 VALIDATION] FAIL | context={context}")
            return

        informant = context.get("informant")
        mara = context.get("mara")
        site = context.get("site")
        destination = context.get("destination")
        manifest = context.get("manifest")
        registry = get_consequence_registry(create=True)

        original = {
            "informant_location": informant.location,
            "informant_knowledge": _clone(getattr(informant.db, "knowledge", {})),
            "informant_facts": _clone(getattr(informant.db, "knowledge_facts", [])),
            "informant_goals": _clone(getattr(informant.db, "decision_goals", [])),
            "informant_completion_rules": _clone(getattr(informant.db, "fact_goal_completion_rules", [])),
            "informant_ledger": _clone(getattr(informant.db, LEDGER_ATTR, [])),
            "informant_current_goal": _clone(getattr(informant.db, "current_goal", None)),
            "informant_current_activity": getattr(informant.db, "current_activity", None),
            "informant_destination_id": getattr(informant.db, "destination_id", None),
            "informant_decision_enabled": bool(getattr(informant.db, "decision_enabled", False)),
            "mara_location": mara.location,
            "mara_knowledge": _clone(getattr(mara.db, "knowledge", {})),
            "mara_facts": _clone(getattr(mara.db, "knowledge_facts", [])),
            "processed": _clone(getattr(registry.db, "processed_action_ids", [])),
            "log": _clone(getattr(registry.db, "action_log", [])),
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.60 | {FACT_GOAL_COMPLETION_BUILD} ===")
        self.caller.msg(
            f"Source NPC: {informant.key}#{informant.id} -> target={mara.key}#{mara.id} | fact={FACT_ID} | goal={GOAL_ID}"
        )

        try:
            reset_v60_playtest_state()
            seed = _pilot_fact(self.caller, site, manifest, informant)
            upsert_knowledge_fact(informant, seed)
            set_knowledge_level(informant, KNOWLEDGE_KEY, 1)
            informant.db.decision_enabled = True

            check(
                "completion-rule-is-installed-once",
                _rule_count(informant) == 1,
                f"rules={_rule_count(informant)} build={PILOT_BUILD}",
            )

            check(
                "reset-starts-with-mara-unaware-and-colocated-at-destination",
                _fact_count(mara) == 0
                and knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) == 0
                and mara.location == destination
                and informant.location == site,
                f"mara_facts={_fact_count(mara)} knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY, 0)} mara_location={mara.location.key if mara.location else None}",
            )

            decision = choose_goal(informant)
            selected = decision.get("selected") or {}
            check(
                "known-fact-still-materializes-v059-goal",
                selected.get("id") == GOAL_ID and selected.get("target_name") == destination.key,
                f"winner={selected.get('id')} target={selected.get('target_name')}",
            )

            source_before = _clone(find_knowledge_fact(informant, FACT_ID))
            step1 = decision_step(informant, prepare_world_state=False)
            step2 = decision_step(informant, prepare_world_state=False)
            step3 = decision_step(informant, prepare_world_state=False)
            completion = _plain_dict(step3.get("fact_goal_completion"))
            effect_rows = _plain_list(completion.get("results"))
            effect = _plain_dict(effect_rows[0]) if effect_rows else {}
            transfer = _plain_dict(effect.get("transfer"))

            check(
                "goal-completion-automatically-shares-fact-to-mara",
                step1.get("status") == "MOVED_GOAL"
                and step2.get("status") == "MOVED_GOAL"
                and step3.get("status") == "GOAL_COMPLETED"
                and completion.get("status") == "APPLIED"
                and effect.get("status") == "APPLIED"
                and transfer.get("reason") == "FACT_TRANSFERRED"
                and transfer.get("target_npc_id") == MARA_NPC_ID,
                f"steps={step1.get('status')},{step2.get('status')},{step3.get('status')} completion={completion.get('status')} transfer={transfer.get('reason')}",
            )

            mara_fact = find_knowledge_fact(mara, FACT_ID)
            check(
                "mara-receives-known-knowledge-and-one-fact",
                mara_fact is not None
                and _fact_count(mara) == 1
                and knowledge_levels(mara).get(KNOWLEDGE_KEY) == 1
                and fact_knowledge_state(mara, mara_fact).get("known") is True,
                f"facts={_fact_count(mara)} knowledge={knowledge_levels(mara).get(KNOWLEDGE_KEY)} known={None if mara_fact is None else fact_knowledge_state(mara, mara_fact).get('known')}",
            )

            source_meta = _plain_dict((mara_fact or {}).get("source"))
            learned_meta = _plain_dict((mara_fact or {}).get("learned_by"))
            check(
                "multi-hop-transfer-preserves-original-evidence-and-learning",
                source_meta.get("object_id") == MANIFEST_ID
                and learned_meta.get("object_action_id") == V57_ACTION_ID
                and (mara_fact or {}).get("text") == FACT_TEXT,
                f"source={source_meta} learned_by={learned_meta}",
            )

            history = [_plain_dict(row) for row in _plain_list((mara_fact or {}).get("transfer_history"))]
            check(
                "mara-retains-full-admin-informant-mara-transfer-chain",
                len(history) == 2
                and history[0].get("source_name") == self.caller.key
                and history[0].get("target_name") == informant.key
                and history[1].get("source_name") == informant.key
                and history[1].get("target_name") == mara.key,
                f"history={[(row.get('source_name'), row.get('target_name')) for row in history]}",
            )

            consequence = _plain_dict(transfer.get("action_consequence"))
            check(
                "npc-to-npc-propagation-emits-knowledge-fact-shared-world-action",
                consequence.get("status") == "PROCESSED"
                and str(consequence.get("action_id") or "").startswith("KNOWLEDGE_FACT_SHARED:FACT_TRANSFER:"),
                f"status={consequence.get('status')} action_id={consequence.get('action_id')}",
            )

            replay = apply_goal_completion_effects(informant, step3)
            replay_rows = _plain_list(replay.get("results"))
            replay_effect = _plain_dict(replay_rows[0]) if replay_rows else {}
            mara_after_replay = find_knowledge_fact(mara, FACT_ID)
            check(
                "completion-effect-is-idempotent-and-does-not-duplicate-chain",
                replay_effect.get("status") == "ALREADY_APPLIED"
                and _fact_count(mara) == 1
                and len(_plain_list((mara_after_replay or {}).get("transfer_history"))) == 2,
                f"status={replay_effect.get('status')} facts={_fact_count(mara)} history={len(_plain_list((mara_after_replay or {}).get('transfer_history')))}",
            )

            check(
                "propagation-does-not-mutate-informant-source-fact",
                _clone(find_knowledge_fact(informant, FACT_ID)) == source_before,
                f"source_unchanged={_clone(find_knowledge_fact(informant, FACT_ID)) == source_before}",
            )

            reset_v60_playtest_state()
            upsert_knowledge_fact(informant, seed)
            set_knowledge_level(informant, KNOWLEDGE_KEY, 1)
            informant.db.decision_enabled = True
            tick1 = simulate_npc_tick(informant)
            tick2 = simulate_npc_tick(informant)
            tick3 = simulate_npc_tick(informant)
            tick_completion = _plain_dict(tick3.get("fact_goal_completion"))
            check(
                "autonomous-world-tick-completes-same-npc-to-npc-propagation",
                tick1.get("status") == "MOVED_GOAL"
                and tick2.get("status") == "MOVED_GOAL"
                and tick3.get("status") == "GOAL_COMPLETED"
                and tick_completion.get("status") == "APPLIED"
                and find_knowledge_fact(mara, FACT_ID) is not None,
                f"ticks={tick1.get('status')},{tick2.get('status')},{tick3.get('status')} completion={tick_completion.get('status')}",
            )

            reset = reset_v60_playtest_state()
            check(
                "v060-reset-cleans-only-propagation-target-and-preserves-informant-fact",
                reset.get("success") is True
                and find_knowledge_fact(mara, FACT_ID) is None
                and knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) == 0
                and find_knowledge_fact(informant, FACT_ID) is not None
                and knowledge_levels(informant).get(KNOWLEDGE_KEY) == 1
                and informant.location == site
                and mara.location == destination,
                f"mara_fact={find_knowledge_fact(mara, FACT_ID) is not None} informant_fact={find_knowledge_fact(informant, FACT_ID) is not None}",
            )

            ensure_v60_pilot_content()
            check(
                "v060-install-is-idempotent",
                _rule_count(informant) == 1,
                f"rules={_rule_count(informant)}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if informant.location != original["informant_location"]:
                    informant.move_to(original["informant_location"], quiet=True)
            except Exception:
                pass
            try:
                if mara.location != original["mara_location"]:
                    mara.move_to(original["mara_location"], quiet=True)
            except Exception:
                pass
            informant.db.knowledge = original["informant_knowledge"]
            informant.db.knowledge_facts = original["informant_facts"]
            informant.db.decision_goals = original["informant_goals"]
            informant.db.fact_goal_completion_rules = original["informant_completion_rules"]
            setattr(informant.db, LEDGER_ATTR, original["informant_ledger"])
            informant.db.current_goal = original["informant_current_goal"]
            informant.db.current_activity = original["informant_current_activity"]
            informant.db.destination_id = original["informant_destination_id"]
            informant.db.decision_enabled = original["informant_decision_enabled"]
            mara.db.knowledge = original["mara_knowledge"]
            mara.db.knowledge_facts = original["mara_facts"]
            registry.db.processed_action_ids = original["processed"]
            registry.db.action_log = original["log"]

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: Informant/Mara locations, Knowledge/Facts, goals, completion rules/ledger and consequence log restored")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: GOAL_COMPLETED -> SHARE_FACT + multi-hop provenance + autonomous tick dispatch")
        self.caller.msg("========================================================")
