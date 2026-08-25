from evennia import Command

from commands.world_input_v74_commands import _clone
from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry
from services.interaction_engine import parse_interaction_intent
from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import find_knowledge_fact
from services.npc_fact_disclosure_state_engine import (
    evaluate_fact_disclosure_v85,
    resolve_interaction_with_disclosure_and_acquisition_v85,
)
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import resolve_pending_object_action_roll
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v54 import CONFRONTED_FIELD, TARGET_STAT, WORLD_CONFRONTED_FIELD
from world.upgrade_pilot_v86 import (
    ACTION_FIELD,
    ACTION_ID,
    ACTION_INPUT,
    EXPLICIT_FACT_PHRASE,
    FACT_ID,
    FACT_TEXT,
    KNOWLEDGE_KEY,
    PILOT_BUILD,
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    RULE_ID,
    WORLD_FIELD,
    ensure_v86_pilot_content,
    v86_rule_count,
)


V086_VALIDATION_BUILD = "0.86.0-acquired-npc-fact-unlocks-authored-world-action"


def _action_row(actor, manifest):
    return next(
        (
            row
            for row in inspect_object_actions(actor, manifest)
            if str(row.get("id") or "") == ACTION_ID
        ),
        None,
    )


def _count_id(rows, wanted):
    total = 0
    for raw in list(rows or []):
        try:
            value = str(raw.get("id") or "")
        except Exception:
            continue
        if value == str(wanted):
            total += 1
    return total


class CmdSizaValidateV86(Command):
    key = "siza-validate-v86"
    aliases = ["validate-v86"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v86_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.86 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        manifest = install.get("manifest")
        informant = install.get("informant")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not informant or not registry:
            self.caller.msg("[V0.86 VALIDATION] FAIL | persistent context missing")
            return

        original_actor_location = actor.location
        original_informant_location = informant.location
        original_actor_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_informant_stats = _clone(getattr(informant.db, "adventure_stats", {}))
        original_actor_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_actor_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_actor_memories = _clone(getattr(actor.db, "memories", []))
        original_actor_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_actor_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_actor_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_informant_knowledge = _clone(getattr(informant.db, "knowledge", {}))
        original_informant_facts = _clone(getattr(informant.db, "knowledge_facts", []))
        original_informant_memories = _clone(getattr(informant.db, "memories", []))
        original_informant_relationships = _clone(getattr(informant.db, "relationships", {}))
        original_informant_state = _clone(getattr(informant.db, "state", {}))
        original_informant_policies = _clone(getattr(informant.db, "fact_disclosure_policies", {}))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.86 | {V086_VALIDATION_BUILD} ===")
        self.caller.msg(
            "NPC Fact blocked by disclosure -> real CONFRONT unlock -> Fact transfer raises player Knowledge -> same authored manifest action changes from KNOWLEDGE-blocked to executable -> consequence mutates world"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if informant.location != site:
                informant.move_to(site, quiet=True)

            # Isolate player state while retaining the newly installed persistent NPC Fact/policy/action/rule.
            actor_levels = {
                str(key): value
                for key, value in dict(original_actor_knowledge or {}).items()
                if str(key) != KNOWLEDGE_KEY
            }
            actor.db.knowledge = actor_levels
            actor.db.knowledge_facts = [
                row
                for row in list(original_actor_facts or [])
                if str((row or {}).get("id") or "") != FACT_ID
            ]
            actor.db.object_action_history = []
            actor.db.action_resolution_history = []
            actor.db.memories = _clone(original_actor_memories)
            actor.db.relationships = _clone(original_actor_relationships)

            set_adventure_stat(actor, "PSI", 4)
            set_adventure_stat(informant, TARGET_STAT, 4)

            informant_state = _clone(getattr(informant.db, "state", {}))
            if not isinstance(informant_state, dict):
                informant_state = {}
            informant_state[CONFRONTED_FIELD] = False
            informant.db.state = informant_state

            manifest_state = _clone(getattr(manifest.db, "state", {}))
            if not isinstance(manifest_state, dict):
                manifest_state = {}
            manifest_state[ACTION_FIELD] = False
            manifest.db.state = manifest_state

            world_state = _clone(getattr(site.db, "world_state", {}))
            if not isinstance(world_state, dict):
                world_state = {}
            world_state[MANIFEST_VISIBLE_FIELD] = 1
            world_state.pop(WORLD_CONFRONTED_FIELD, None)
            world_state.pop(WORLD_FIELD, None)
            site.db.world_state = world_state

            installed_fact = find_knowledge_fact(informant, FACT_ID)
            policy_gate = evaluate_fact_disclosure_v85(informant, actor, installed_fact)
            check(
                "persistent-v086-content-is-installed-once-with-clean-fact-and-holder-local-policy",
                installed_fact is not None
                and "disclosure" not in installed_fact
                and policy_gate.get("policy_source") == "NPC_LOCAL_POLICY"
                and _count_id(getattr(manifest.db, "object_actions", []), ACTION_ID) == 1
                and v86_rule_count() == 1
                and _count_id(getattr(site.db, "state_presentations", []), PRESENTATION_ID) == 1,
                f"actions={_count_id(getattr(manifest.db, 'object_actions', []), ACTION_ID)} rules={v86_rule_count()} presentations={_count_id(getattr(site.db, 'state_presentations', []), PRESENTATION_ID)}",
            )

            before_action = _action_row(actor, manifest)
            knowledge_blockers = [
                row
                for row in (before_action or {}).get("blockers") or []
                if str(row.get("kind") or "") == "KNOWLEDGE"
            ]
            check(
                "authored-manifest-action-is-visible-but-blocked-by-player-knowledge-before-fact-acquisition",
                before_action is not None
                and before_action.get("eligible") is False
                and any(str(row.get("id") or "") == KNOWLEDGE_KEY for row in knowledge_blockers),
                f"eligible={None if before_action is None else before_action.get('eligible')} blockers={knowledge_blockers}",
            )

            blocked_talk = resolve_interaction_with_disclosure_and_acquisition_v85(
                actor,
                parse_interaction_intent(EXPLICIT_FACT_PHRASE),
            )
            check(
                "same-fact-cannot-be-acquired-before-authored-informant-state-gate-is-met",
                (blocked_talk.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and find_knowledge_fact(actor, FACT_ID) is None
                and int(knowledge_levels(actor).get(KNOWLEDGE_KEY, 0) or 0) == 0,
                f"acquisition={(blocked_talk.get('knowledge_acquisition') or {}).get('status')}",
            )

            pending_loss = route_object_action_input(actor, "presionar informante")
            loss = resolve_pending_object_action_roll(
                actor,
                attempt_id=pending_loss.get("attempt_id"),
                forced_roll=1,
                forced_target_roll=6,
            )
            after_loss_action = _action_row(actor, manifest)
            check(
                "failed-real-confrontation-keeps-both-disclosure-and-knowledge-gated-action-blocked",
                pending_loss.get("status") == "PENDING_RESOLUTION"
                and loss.get("status") == "RESOLVED"
                and loss.get("outcome") == "TARGET_WIN"
                and bool((_clone(getattr(informant.db, "state", {})) or {}).get(CONFRONTED_FIELD)) is False
                and after_loss_action is not None
                and after_loss_action.get("eligible") is False
                and any(str(row.get("kind") or "") == "KNOWLEDGE" for row in after_loss_action.get("blockers") or []),
                f"outcome={loss.get('outcome')} action_eligible={None if after_loss_action is None else after_loss_action.get('eligible')}",
            )

            pending_win = route_object_action_input(actor, "presionar informante")
            win = resolve_pending_object_action_roll(
                actor,
                attempt_id=pending_win.get("attempt_id"),
                forced_roll=6,
                forced_target_roll=1,
            )
            check(
                "actor-win-real-confrontation-sets-the-existing-authoritative-disclosure-state",
                pending_win.get("status") == "PENDING_RESOLUTION"
                and win.get("status") == "RESOLVED"
                and win.get("outcome") == "ACTOR_WIN"
                and bool((_clone(getattr(informant.db, "state", {})) or {}).get(CONFRONTED_FIELD)) is True,
                f"outcome={win.get('outcome')} conceded={(_clone(getattr(informant.db, 'state', {})) or {}).get(CONFRONTED_FIELD)}",
            )

            acquired_packet = resolve_interaction_with_disclosure_and_acquisition_v85(
                actor,
                parse_interaction_intent(EXPLICIT_FACT_PHRASE),
            )
            acquired_fact = find_knowledge_fact(actor, FACT_ID)
            check(
                "post-confrontation-talk-acquires-the-clean-authoritative-fact",
                (acquired_packet.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired_fact is not None
                and str(acquired_fact.get("text") or "") == FACT_TEXT
                and "disclosure" not in acquired_fact,
                f"acquisition={(acquired_packet.get('knowledge_acquisition') or {}).get('status')}",
            )

            player_level = int(knowledge_levels(actor).get(KNOWLEDGE_KEY, 0) or 0)
            check(
                "fact-transfer-raises-the-exact-player-knowledge-key-required-by-the-world-action",
                player_level >= 1,
                f"knowledge={KNOWLEDGE_KEY}:{player_level}",
            )

            unlocked_action = _action_row(actor, manifest)
            check(
                "same-authored-action-becomes-eligible-immediately-from-acquired-npc-knowledge",
                unlocked_action is not None
                and unlocked_action.get("eligible") is True
                and not any(str(row.get("kind") or "") == "KNOWLEDGE" for row in unlocked_action.get("blockers") or []),
                f"eligible={None if unlocked_action is None else unlocked_action.get('eligible')} blockers={[] if unlocked_action is None else unlocked_action.get('blockers')}",
            )

            before_history = len(object_action_history(actor))
            executed = route_object_action_input(actor, ACTION_INPUT)
            check(
                "real-natural-object-input-now-executes-the-knowledge-gated-action-without-llm",
                executed.get("status") == "COMPLETED"
                and str(executed.get("object_action_id") or "") == ACTION_ID
                and len(object_action_history(actor)) == before_history + 1,
                f"status={executed.get('status')} action={executed.get('object_action_id')}",
            )

            manifest_after = _clone(getattr(manifest.db, "state", {}))
            world_after = _clone(getattr(site.db, "world_state", {}))
            appearance = str(site.return_appearance(actor) or "")
            consequence = (executed.get("action_result") or {}).get("action_consequence") or {}
            check(
                "completed-knowledge-action-flows-through-existing-consequence-engine-and-room-presentation",
                consequence.get("status") == "PROCESSED"
                and bool((manifest_after or {}).get(ACTION_FIELD)) is True
                and (world_after or {}).get(WORLD_FIELD) == 1
                and PRESENTATION_TEXT in appearance,
                f"consequence={consequence.get('status')} object_state={(manifest_after or {}).get(ACTION_FIELD)} room_state={(world_after or {}).get(WORLD_FIELD)}",
            )

            completed_action = _action_row(actor, manifest)
            check(
                "completed-action-locks-itself-by-authored-object-state-not-by-consuming-knowledge",
                completed_action is not None
                and completed_action.get("eligible") is False
                and any(
                    str(row.get("kind") or "") == "OBJECT_STATE"
                    and str(row.get("id") or "") == ACTION_FIELD
                    for row in completed_action.get("blockers") or []
                )
                and int(knowledge_levels(actor).get(KNOWLEDGE_KEY, 0) or 0) >= 1,
                f"eligible={None if completed_action is None else completed_action.get('eligible')} knowledge={knowledge_levels(actor).get(KNOWLEDGE_KEY)}",
            )

            second_install = ensure_v86_pilot_content()
            check(
                "v086-install-is-idempotent-and-does-not-reset-completed-world-state",
                second_install.get("success") is True
                and _count_id(getattr(manifest.db, "object_actions", []), ACTION_ID) == 1
                and v86_rule_count() == 1
                and _count_id(getattr(site.db, "state_presentations", []), PRESENTATION_ID) == 1
                and bool((_clone(getattr(manifest.db, "state", {})) or {}).get(ACTION_FIELD)) is True
                and (_clone(getattr(site.db, "world_state", {})) or {}).get(WORLD_FIELD) == 1,
                f"actions={_count_id(getattr(manifest.db, 'object_actions', []), ACTION_ID)} rules={v86_rule_count()} completed={(_clone(getattr(manifest.db, 'state', {})) or {}).get(ACTION_FIELD)}",
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
                if informant.location != original_informant_location:
                    informant.move_to(original_informant_location, quiet=True)
            except Exception:
                pass

            actor.db.adventure_stats = original_actor_stats
            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.memories = original_actor_memories
            actor.db.relationships = original_actor_relationships
            actor.db.object_action_history = original_actor_object_history
            actor.db.action_resolution_history = original_actor_resolution_history

            informant.db.adventure_stats = original_informant_stats
            informant.db.knowledge = original_informant_knowledge
            informant.db.knowledge_facts = original_informant_facts
            informant.db.memories = original_informant_memories
            informant.db.relationships = original_informant_relationships
            informant.db.state = original_informant_state
            informant.db.fact_disclosure_policies = original_informant_policies
            manifest.db.state = original_manifest_state

            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    site.db.world_state = None
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Informant locations, stats, Knowledge/Facts/social state, histories, NPC/manifest/room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: clean Informant Fact + holder-local disclosure policy + Knowledge-gated manifest action + consequence + presentation"
        )
        self.caller.msg("========================================================")
