from evennia import Command

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.direct_d6_resolution_engine import DIRECT_D6_PROVIDER
from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts, knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import KNOWLEDGE_FACT_BUILD, find_knowledge_fact, remove_knowledge_fact
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_recipient_consequence_engine import APPLIED_ACTIONS_ATTR, apply_player_actor_consequences
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v56 import KNOWLEDGE_KEY as V56_KNOWLEDGE_KEY, SHIFT_FIELD
from world.upgrade_pilot_v57 import (
    ACTION_ID,
    FACT_ID,
    FACT_TEXT,
    FACT_TOPIC,
    KNOWLEDGE_KEY,
    RECORDED_FIELD,
    RULE_ID,
    ensure_v57_pilot_content,
    reset_v57_world_state,
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


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _count_action(obj, action_id):
    return sum(
        1
        for row in list(getattr(obj.db, "object_actions", []) or [])
        if str(getattr(row, "get", lambda *_: None)("id") or "") == str(action_id or "")
    )


def _count_fact(actor, fact_id):
    return sum(1 for row in knowledge_facts(actor) if str(row.get("id") or "") == str(fact_id or ""))


class CmdSizaMyKnowledgeV57(Command):
    """Inspect the caller's persistent Knowledge levels and structured Knowledge Facts."""

    key = "siza-my-knowledge"
    aliases = ["my-knowledge", "mis-conocimientos"]
    locks = "cmd:all()"

    def func(self):
        levels = knowledge_levels(self.caller)
        facts = knowledge_facts(self.caller)
        self.caller.msg(f"=== SIZA MY KNOWLEDGE | {KNOWLEDGE_FACT_BUILD} ===")
        self.caller.msg(f"Character: {self.caller.key}#{self.caller.id}")
        self.caller.msg(f"Levels: {levels or {}}")
        if not facts:
            self.caller.msg("Facts: NONE")
            self.caller.msg("========================================================")
            return

        self.caller.msg(f"Facts: {len(facts)}")
        for fact in facts:
            state = fact_knowledge_state(self.caller, fact)
            source = _plain_dict(fact.get("source"))
            learned = _plain_dict(fact.get("learned_by"))
            self.caller.msg(
                f"  {fact.get('id')} | known={bool(state.get('known'))} | "
                f"knowledge={state.get('knowledge_key')} {state.get('level')}/{state.get('required_level')}"
            )
            self.caller.msg(f"    topic={fact.get('topic')}")
            self.caller.msg(f"    text={fact.get('text')}")
            self.caller.msg(
                f"    source={source.get('object_name')} | object_id={source.get('object_id')} | "
                f"site={source.get('site_name')} ({source.get('site_room_id')})"
            )
            self.caller.msg(
                f"    learned_by={learned.get('object_action_id')} | attempt={learned.get('attempt_id')} | "
                f"provider={learned.get('provider')} | outcome={learned.get('outcome')}"
            )
        self.caller.msg("========================================================")


class CmdSizaValidateV57(Command):
    """Validate persistent structured Knowledge Facts with provenance on a real Character."""

    key = "siza-validate-v57"
    aliases = ["validate-v57"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = self.caller
        install = ensure_v57_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg(
                f"[V0.57 VALIDATION] FAIL | actor/install missing | reason={install.get('reason')}"
            )
            return

        site = install.get("site")
        manifest = install.get("manifest")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not registry:
            self.caller.msg("[V0.57 VALIDATION] FAIL | persistent content/registry missing")
            return

        original_location = actor.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_player_applied = _clone(getattr(actor.db, APPLIED_ACTIONS_ATTR, []))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.57 | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"Harness Character: {actor.key}#{actor.id} | fact={FACT_ID} | manifest={manifest.key}#{manifest.id}"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            setattr(actor.db, APPLIED_ACTIONS_ATTR, [])
            set_adventure_stat(actor, "INT", 4)

            levels = knowledge_levels(actor)
            levels.pop(V56_KNOWLEDGE_KEY, None)
            levels.pop(KNOWLEDGE_KEY, None)
            actor.db.knowledge = levels
            remove_knowledge_fact(actor, FACT_ID)

            state = _plain_dict(original_manifest_state)
            state[SHIFT_FIELD] = True
            state[RECORDED_FIELD] = False
            manifest.db.state = state

            check(
                "persistent-knowledge-fact-content-is-installed-once",
                _count_action(manifest, ACTION_ID) == 1
                and sum(1 for row in consequence_rules() if str(row.get('id') or '') == RULE_ID) == 1,
                f"actions={_count_action(manifest, ACTION_ID)} rules={sum(1 for row in consequence_rules() if str(row.get('id') or '') == RULE_ID)}",
            )

            blocked_knowledge = route_object_action_input(actor, "consolidar hallazgo manifiesto")
            blockers_knowledge = ((blocked_knowledge.get("action_result") or {}).get("blockers") or [])
            check(
                "fact-action-is-blocked-without-v056-knowledge",
                blocked_knowledge.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and any(str(row.get("kind") or "") == "KNOWLEDGE" for row in blockers_knowledge)
                and len(object_action_history(actor)) == 0,
                f"status={blocked_knowledge.get('status')} blockers={[row.get('kind') for row in blockers_knowledge]}",
            )

            set_knowledge_level(actor, V56_KNOWLEDGE_KEY, 1)
            state[SHIFT_FIELD] = False
            manifest.db.state = state
            blocked_state = route_object_action_input(actor, "consolidar hallazgo manifiesto")
            blockers_state = ((blocked_state.get("action_result") or {}).get("blockers") or [])
            check(
                "fact-action-is-blocked-until-v056-shift-is-identified",
                blocked_state.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in blockers_state)
                and len(object_action_history(actor)) == 0,
                f"status={blocked_state.get('status')} blockers={[row.get('kind') for row in blockers_state]}",
            )

            state[SHIFT_FIELD] = True
            manifest.db.state = state
            pending = route_object_action_input(
                actor,
                "consolidar hallazgo manifiesto",
                attempt_id="V057-FACT",
            )
            resolution = next(
                (
                    row
                    for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V057-FACT:RESOLUTION"
                ),
                None,
            )
            check(
                "real-player-input-enters-direct-fact-action",
                pending.get("status") == "PENDING_RESOLUTION"
                and resolution is not None
                and resolution.get("mode") == "DIRECT"
                and resolution.get("actor_stat") == "INT"
                and resolution.get("actor_stat_value") == 4
                and resolution.get("difficulty") == 8,
                f"status={pending.get('status')} stat={None if resolution is None else resolution.get('actor_stat_value')} difficulty={None if resolution is None else resolution.get('difficulty')}",
            )

            learned = resolve_pending_object_action_roll(actor, attempt_id="V057-FACT", forced_roll=4)
            bridge = learned.get("player_recipient_consequence") or {}
            learned_state = _plain_dict(getattr(manifest.db, "state", {}))
            fact = find_knowledge_fact(actor, FACT_ID)
            check(
                "success-persists-knowledge-level-and-structured-fact",
                learned.get("status") == "RESOLVED"
                and learned.get("outcome") == "SUCCESS"
                and bridge.get("status") == "APPLIED"
                and knowledge_levels(actor).get(KNOWLEDGE_KEY) == 1
                and fact is not None
                and learned_state.get(RECORDED_FIELD) is True,
                f"outcome={learned.get('outcome')} bridge={bridge.get('status')} knowledge={knowledge_levels(actor).get(KNOWLEDGE_KEY)} fact={fact is not None} recorded={learned_state.get(RECORDED_FIELD)}",
            )

            fact_state = fact_knowledge_state(actor, fact or {})
            source = _plain_dict((fact or {}).get("source"))
            learned_by = _plain_dict((fact or {}).get("learned_by"))
            check(
                "fact-persists-text-source-and-learning-provenance",
                fact is not None
                and fact.get("topic") == FACT_TOPIC
                and fact.get("text") == FACT_TEXT
                and fact_state.get("known") is True
                and source.get("object_id") == MANIFEST_ID
                and source.get("site_room_id") == str(getattr(site.db, "room_id", "") or "")
                and learned_by.get("object_action_id") == ACTION_ID
                and learned_by.get("attempt_id") == "V057-FACT"
                and learned_by.get("provider") == DIRECT_D6_PROVIDER
                and learned_by.get("outcome") == "SUCCESS",
                f"known={fact_state.get('known')} source={source} learned_by={learned_by}",
            )

            check(
                "fact-is-queryable-through-normal-knowledge-context",
                any(
                    str(row.get("id") or "") == FACT_ID
                    and fact_knowledge_state(actor, row).get("known") is True
                    for row in knowledge_facts(actor)
                ),
                f"facts={_count_fact(actor, FACT_ID)}",
            )

            locked = next(
                (
                    row
                    for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == ACTION_ID
                ),
                None,
            )
            check(
                "completed-fact-action-locks-itself-by-object-state",
                locked is not None
                and locked.get("eligible") is False
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in (locked.get("blockers") or [])),
                f"eligible={None if locked is None else locked.get('eligible')}",
            )

            replay_packet = {
                "action_id": "OBJECT_ACTION_RESOLVED:V057-FACT",
                "action_type": "OBJECT_ACTION_RESOLVED",
                "actor_npc_id": "",
                "actor_dbref": int(actor.id),
                "actor_name": actor.key,
                "object_action_id": ACTION_ID,
                "attempt_id": "V057-FACT",
                "resolution_id": "V057-FACT:RESOLUTION",
                "outcome": "SUCCESS",
                "provider": DIRECT_D6_PROVIDER,
                "site_dbref": int(site.id),
                "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                "site_name": site.key,
                "object_dbref": int(manifest.id),
                "object_id": MANIFEST_ID,
                "object_name": manifest.key,
            }
            replay = apply_player_actor_consequences(actor, replay_packet)
            check(
                "fact-consequence-is-idempotent-per-action",
                replay.get("status") == "ALREADY_APPLIED"
                and knowledge_levels(actor).get(KNOWLEDGE_KEY) == 1
                and _count_fact(actor, FACT_ID) == 1,
                f"status={replay.get('status')} knowledge={knowledge_levels(actor).get(KNOWLEDGE_KEY)} facts={_count_fact(actor, FACT_ID)}",
            )

            second_install = ensure_v57_pilot_content()
            check(
                "v057-install-is-idempotent-and-preserves-learned-fact",
                second_install.get("success") is True
                and _count_action(manifest, ACTION_ID) == 1
                and sum(1 for row in consequence_rules() if str(row.get('id') or '') == RULE_ID) == 1
                and _plain_dict(getattr(manifest.db, "state", {})).get(RECORDED_FIELD) is True
                and knowledge_levels(actor).get(KNOWLEDGE_KEY) == 1
                and _count_fact(actor, FACT_ID) == 1,
                f"actions={_count_action(manifest, ACTION_ID)} facts={_count_fact(actor, FACT_ID)} recorded={_plain_dict(getattr(manifest.db, 'state', {})).get(RECORDED_FIELD)}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            actor.db.adventure_stats = original_stats
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_history
            setattr(actor.db, APPLIED_ACTIONS_ATTR, original_player_applied)
            manifest.db.state = original_manifest_state
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: Character location/stats/Knowledge/Facts/histories, player consequence ledger, manifest state and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: fact-learning action + Knowledge consequence + structured provenance schema"
        )
        self.caller.msg("========================================================")


class CmdSizaResetV57(Command):
    """Reset only v0.57 state and remove only its test Knowledge/Fact from caller."""

    key = "siza-reset-v57"
    aliases = ["reset-v57"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v57_world_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.57 RESET] FAIL | reason={result.get('reason')} | build={PLAYER_ROLL_BUILD}"
            )
            return

        levels = knowledge_levels(self.caller)
        before = levels.pop(KNOWLEDGE_KEY, None)
        self.caller.db.knowledge = levels
        fact_removed = remove_knowledge_fact(self.caller, FACT_ID)
        self.caller.msg(f"=== SIZA v0.57 RESET | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"PASS Knowledge Fact playtest reset | manifest={result.get('manifest').key}#{result.get('manifest').id} | "
            f"recorded=False | {KNOWLEDGE_KEY}: {before if before is not None else 'UNSET'} -> UNSET | fact_removed={fact_removed}"
        )
        self.caller.msg("No se tocaron estados v0.51-v0.56, jobs, NPCs, exits, skills ni otros Knowledge/Facts.")
        self.caller.msg("========================================================")
