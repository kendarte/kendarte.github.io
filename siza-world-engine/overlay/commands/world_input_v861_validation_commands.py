from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v861_commands import handle_action_proposal_result_v861
from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry
from services.knowledge_context_engine import knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import resolve_pending_object_action_roll
from services.ranked_fact_conversation_engine import (
    fact_topic_match_score,
    resolve_ranked_talk_with_disclosure_and_acquisition,
    select_best_known_topic_fact,
)
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
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    WORLD_FIELD,
    ensure_v86_pilot_content,
    v86_rule_count,
)


V0861_VALIDATION_BUILD = "0.86.1-ranked-single-fact-cross-system-regression"
DECOY_FACT_ID = "FACT-V0861-DECOY-GENERIC-SELLO"
DECOY_KNOWLEDGE_KEY = "V0861_DECOY_GENERIC_SELLO"
DECOY_TEXT = "El informante conoce un sello operativo genérico que no corresponde a la auditoría consultada."
SEMANTIC_FACT_PHRASE = "me acerco al Informante de Prueba C y le saco el tema del sello blanco de auditoria"


def _action_row(actor, manifest):
    return next(
        (row for row in inspect_object_actions(actor, manifest) if str(row.get("id") or "") == ACTION_ID),
        None,
    )


def _count_id(rows, wanted):
    count = 0
    for raw in list(rows or []):
        try:
            if str(raw.get("id") or "") == str(wanted):
                count += 1
        except Exception:
            continue
    return count


def _accepted_talk(capability):
    return {
        "status": "ACCEPTED",
        "accepted": True,
        "proposal": {
            "kind": "INTERACTION",
            "capability_id": str(capability.get("capability_id") or ""),
            "confidence": 1.0,
            "reason": "V0861_MODEL_REASON_MUST_NOT_SELECT_FACT",
        },
        "capability": dict(capability),
    }


class CmdSizaValidateV861(Command):
    key = "siza-validate-v861"
    aliases = ["validate-v861"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v86_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.86.1 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        manifest = install.get("manifest")
        informant = install.get("informant")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not informant or not registry:
            self.caller.msg("[V0.86.1 VALIDATION] FAIL | persistent context missing")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.86.1 | {V0861_VALIDATION_BUILD} ===")
        self.caller.msg(
            "generic public decoy Fact first -> ranked exact Fact selected once -> disclosure and transfer share same fact_id -> CONFRONT unlock -> acquired Knowledge unlocks authored world action"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if informant.location != site:
                informant.move_to(site, quiet=True)

            actor.db.knowledge = {
                str(key): value
                for key, value in dict(original_actor_knowledge or {}).items()
                if str(key) not in {KNOWLEDGE_KEY, DECOY_KNOWLEDGE_KEY}
            }
            actor.db.knowledge_facts = [
                row for row in list(original_actor_facts or [])
                if str((row or {}).get("id") or "") not in {FACT_ID, DECOY_FACT_ID}
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
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            upsert_knowledge_fact(
                informant,
                {
                    "id": DECOY_FACT_ID,
                    "topic": "sello operativo genérico",
                    "aliases": ["sello"],
                    "text": DECOY_TEXT,
                    "knowledge_key": DECOY_KNOWLEDGE_KEY,
                    "required_level": 1,
                    "canon_status": "prototype",
                    "source": {"kind": "V0861_DECOY"},
                    "learned_by": {"provider": "V0861_VALIDATOR"},
                },
            )
            set_knowledge_level(informant, DECOY_KNOWLEDGE_KEY, 1)
            desired_fact = find_knowledge_fact(informant, FACT_ID)
            decoy_fact = find_knowledge_fact(informant, DECOY_FACT_ID)
            rows = [decoy_fact] + [
                row for row in list(getattr(informant.db, "knowledge_facts", []) or [])
                if str((row or {}).get("id") or "") != DECOY_FACT_ID
            ]
            informant.db.knowledge_facts = rows

            selected = select_best_known_topic_fact(informant, "sello blanco de auditoria")
            desired_score = fact_topic_match_score(desired_fact, "sello blanco de auditoria")
            decoy_score = fact_topic_match_score(decoy_fact, "sello blanco de auditoria")
            check(
                "ranked-selector-prefers-specific-audit-fact-over-earlier-public-one-token-decoy",
                selected is not None
                and selected.get("fact_id") == FACT_ID
                and int(desired_score) > int(decoy_score),
                f"selected={(selected or {}).get('fact_id')} desired_score={desired_score} decoy_score={decoy_score}",
            )

            before_action = _action_row(actor, manifest)
            check(
                "authored-world-action-remains-knowledge-blocked-before-ranked-fact-acquisition",
                before_action is not None
                and before_action.get("eligible") is False
                and any(
                    str(row.get("kind") or "") == "KNOWLEDGE" and str(row.get("id") or "") == KNOWLEDGE_KEY
                    for row in before_action.get("blockers") or []
                ),
                f"eligible={None if before_action is None else before_action.get('eligible')}",
            )

            blocked = resolve_ranked_talk_with_disclosure_and_acquisition(actor, EXPLICIT_FACT_PHRASE)
            check(
                "ranked-explicit-talk-blocks-the-specific-fact-before-state-gate-and-does-not-transfer-decoy",
                blocked.get("selected_fact_id") == FACT_ID
                and (blocked.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and find_knowledge_fact(actor, FACT_ID) is None
                and find_knowledge_fact(actor, DECOY_FACT_ID) is None,
                f"selected={blocked.get('selected_fact_id')} acquisition={(blocked.get('knowledge_acquisition') or {}).get('status')}",
            )

            talk_cap = next(
                (
                    row for row in build_local_capability_catalog(actor)
                    if str(row.get("kind") or "") == "INTERACTION"
                    and int(row.get("target_dbref") or 0) == int(informant.id)
                ),
                None,
            )
            rendered = {}

            def fake_renderer(*args, **kwargs):
                rendered["called"] = True
                return {"status": "V0861_FAKE_RENDER", "queued": True}

            semantic = handle_action_proposal_result_v861(
                actor,
                _accepted_talk(talk_cap),
                raw_player_input=SEMANTIC_FACT_PHRASE,
                emit_messages=False,
                render_async_callable=fake_renderer,
            ) if talk_cap else {}
            check(
                "semantic-talk-wiring-uses-the-same-ranked-fact-id-and-cannot-render-through-a-blocked-gate",
                talk_cap is not None
                and semantic.get("selected_fact_id") == FACT_ID
                and (semantic.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED"
                and not rendered.get("called"),
                f"selected={semantic.get('selected_fact_id')} acquisition={(semantic.get('knowledge_acquisition') or {}).get('status')}",
            )

            pending_loss = route_object_action_input(actor, "presionar informante")
            loss = resolve_pending_object_action_roll(
                actor,
                attempt_id=pending_loss.get("attempt_id"),
                forced_roll=1,
                forced_target_roll=6,
            )
            still_blocked = resolve_ranked_talk_with_disclosure_and_acquisition(actor, EXPLICIT_FACT_PHRASE)
            check(
                "failed-real-confrontation-keeps-ranked-specific-fact-blocked",
                pending_loss.get("status") == "PENDING_RESOLUTION"
                and loss.get("status") == "RESOLVED"
                and loss.get("outcome") == "TARGET_WIN"
                and (still_blocked.get("knowledge_acquisition") or {}).get("status") == "DISCLOSURE_BLOCKED",
                f"outcome={loss.get('outcome')} acquisition={(still_blocked.get('knowledge_acquisition') or {}).get('status')}",
            )

            pending_win = route_object_action_input(actor, "presionar informante")
            win = resolve_pending_object_action_roll(
                actor,
                attempt_id=pending_win.get("attempt_id"),
                forced_roll=6,
                forced_target_roll=1,
            )
            check(
                "actor-win-real-confrontation-still-owns-the-authoritative-disclosure-state",
                pending_win.get("status") == "PENDING_RESOLUTION"
                and win.get("status") == "RESOLVED"
                and win.get("outcome") == "ACTOR_WIN"
                and bool((_clone(getattr(informant.db, "state", {})) or {}).get(CONFRONTED_FIELD)) is True,
                f"outcome={win.get('outcome')}",
            )

            acquired = resolve_ranked_talk_with_disclosure_and_acquisition(actor, EXPLICIT_FACT_PHRASE)
            acquired_fact = find_knowledge_fact(actor, FACT_ID)
            player_level = int(knowledge_levels(actor).get(KNOWLEDGE_KEY, 0) or 0)
            check(
                "post-confrontation-ranked-talk-transfers-exact-specific-fact-and-required-knowledge-key",
                acquired.get("selected_fact_id") == FACT_ID
                and (acquired.get("knowledge_acquisition") or {}).get("status") == "FACT_ACQUIRED"
                and acquired_fact is not None
                and str(acquired_fact.get("text") or "") == FACT_TEXT
                and find_knowledge_fact(actor, DECOY_FACT_ID) is None
                and player_level >= 1,
                f"selected={acquired.get('selected_fact_id')} acquisition={(acquired.get('knowledge_acquisition') or {}).get('status')} level={player_level}",
            )

            unlocked = _action_row(actor, manifest)
            check(
                "acquired-ranked-fact-immediately-unlocks-the-same-authored-world-action",
                unlocked is not None
                and unlocked.get("eligible") is True
                and not any(str(row.get("kind") or "") == "KNOWLEDGE" for row in unlocked.get("blockers") or []),
                f"eligible={None if unlocked is None else unlocked.get('eligible')} blockers={[] if unlocked is None else unlocked.get('blockers')}",
            )

            before_history = len(object_action_history(actor))
            executed = route_object_action_input(actor, ACTION_INPUT)
            check(
                "real-natural-object-input-executes-unlocked-action-without-llm",
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
                "completed-ranked-knowledge-action-mutates-object-room-state-and-presentation-through-existing-consequence-engine",
                consequence.get("status") == "PROCESSED"
                and bool((manifest_after or {}).get(ACTION_FIELD)) is True
                and (world_after or {}).get(WORLD_FIELD) == 1
                and PRESENTATION_TEXT in appearance,
                f"consequence={consequence.get('status')} object_state={(manifest_after or {}).get(ACTION_FIELD)} room_state={(world_after or {}).get(WORLD_FIELD)}",
            )

            completed = _action_row(actor, manifest)
            check(
                "completed-action-self-locks-by-object-state-while-acquired-knowledge-remains",
                completed is not None
                and completed.get("eligible") is False
                and any(
                    str(row.get("kind") or "") == "OBJECT_STATE" and str(row.get("id") or "") == ACTION_FIELD
                    for row in completed.get("blockers") or []
                )
                and int(knowledge_levels(actor).get(KNOWLEDGE_KEY, 0) or 0) >= 1,
                f"eligible={None if completed is None else completed.get('eligible')} knowledge={knowledge_levels(actor).get(KNOWLEDGE_KEY)}",
            )

            second_install = ensure_v86_pilot_content()
            check(
                "v086-content-install-remains-idempotent-after-ranked-talk-fix-and-does-not-reset-completion",
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
                    pass
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor/Informant locations, stats, Knowledge/Facts/social state, histories, holder policies, manifest/room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: one ranked fact_id now owns disclosure + conversation memory + authoritative transfer; v0.54 CONFRONT and existing Knowledge/Object Action/Consequence engines remain unchanged"
        )
        self.caller.msg("========================================================")
