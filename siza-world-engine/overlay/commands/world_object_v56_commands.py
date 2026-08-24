from evennia import Command

from services.action_resolution_engine import action_resolution_history, adventure_stats, set_adventure_stat
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.knowledge_context_engine import knowledge_levels
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_recipient_consequence_engine import (
    APPLIED_ACTIONS_ATTR,
    PLAYER_RECIPIENT_BUILD,
    apply_player_actor_consequences,
)
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v55 import SYNCED_FIELD
from world.upgrade_pilot_v56 import (
    DEDUCED_FIELD,
    DEDUCE_ACTION_ID,
    DEDUCE_RULE_ID,
    FOLLOW_ACTION_ID,
    FOLLOW_RULE_ID,
    KNOWLEDGE_KEY,
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    SHIFT_FIELD,
    WORLD_SHIFT_FIELD,
    ensure_v56_pilot_content,
    reset_v56_world_state,
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


def _count_by_id(rows, wanted):
    return sum(
        1
        for row in list(rows or [])
        if str(getattr(row, "get", lambda *_: None)("id") or "") == str(wanted or "")
    )


class CmdSizaValidateV56(Command):
    """Validate that a real player Character can learn Knowledge from an action consequence."""

    key = "siza-validate-v56"
    aliases = ["validate-v56"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = self.caller
        install = ensure_v56_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg(
                f"[V0.56 VALIDATION] FAIL | actor/install missing | reason={install.get('reason')}"
            )
            return

        site = install.get("site")
        manifest = install.get("manifest")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not registry:
            self.caller.msg("[V0.56 VALIDATION] FAIL | persistent content/registry missing")
            return

        original_location = actor.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_player_applied = _clone(getattr(actor.db, APPLIED_ACTIONS_ATTR, []))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.56 | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"Harness Character: {actor.key}#{actor.id} | npc_id={str(getattr(actor.db, 'npc_id', '') or '') or 'NONE'} | "
            f"manifest={manifest.key}#{manifest.id}"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            setattr(actor.db, APPLIED_ACTIONS_ATTR, [])
            set_adventure_stat(actor, "INT", 4)

            levels = knowledge_levels(actor)
            levels.pop(KNOWLEDGE_KEY, None)
            actor.db.knowledge = levels

            state = _plain_dict(original_manifest_state)
            state[SYNCED_FIELD] = True
            state[DEDUCED_FIELD] = False
            state[SHIFT_FIELD] = False
            manifest.db.state = state
            world_state = _plain_dict(original_world_state)
            world_state.pop(WORLD_SHIFT_FIELD, None)
            site.db.world_state = world_state

            action_count_deduce = _count_by_id(getattr(manifest.db, "object_actions", []), DEDUCE_ACTION_ID)
            action_count_follow = _count_by_id(getattr(manifest.db, "object_actions", []), FOLLOW_ACTION_ID)
            rule_count_deduce = sum(
                1 for row in consequence_rules() if str(row.get("id") or "") == DEDUCE_RULE_ID
            )
            rule_count_follow = sum(
                1 for row in consequence_rules() if str(row.get("id") or "") == FOLLOW_RULE_ID
            )
            presentation_count = _count_by_id(getattr(site.db, "state_presentations", []), PRESENTATION_ID)
            check(
                "persistent-player-knowledge-content-is-installed-once",
                action_count_deduce == 1
                and action_count_follow == 1
                and rule_count_deduce == 1
                and rule_count_follow == 1
                and presentation_count == 1,
                f"actions={action_count_deduce + action_count_follow} rules={rule_count_deduce + rule_count_follow} presentations={presentation_count}",
            )

            check(
                "validator-is-using-real-character-without-npc-id",
                not str(getattr(actor.db, "npc_id", "") or "").strip(),
                f"dbref=#{actor.id} bridge={PLAYER_RECIPIENT_BUILD}",
            )

            state[DEDUCED_FIELD] = True
            manifest.db.state = state
            blocked = route_object_action_input(actor, "identificar turno manifiesto")
            blockers = ((blocked.get("action_result") or {}).get("blockers") or [])
            check(
                "follow-up-action-is-blocked-by-missing-player-knowledge",
                blocked.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and any(str(row.get("kind") or "") == "KNOWLEDGE" for row in blockers)
                and len(object_action_history(actor)) == 0,
                f"status={blocked.get('status')} blockers={[row.get('kind') for row in blockers]}",
            )

            state[DEDUCED_FIELD] = False
            manifest.db.state = state
            pending = route_object_action_input(
                actor,
                "deducir ciclo manifiesto",
                attempt_id="V056-DEDUCE",
            )
            resolution = next(
                (
                    row
                    for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V056-DEDUCE:RESOLUTION"
                ),
                None,
            )
            check(
                "real-player-input-enters-direct-learning-action",
                pending.get("status") == "PENDING_RESOLUTION"
                and resolution is not None
                and resolution.get("mode") == "DIRECT"
                and resolution.get("actor_stat") == "INT"
                and resolution.get("actor_stat_value") == 4
                and resolution.get("difficulty") == 7,
                f"status={pending.get('status')} stat={None if resolution is None else resolution.get('actor_stat_value')} difficulty={None if resolution is None else resolution.get('difficulty')}",
            )

            learned = resolve_pending_object_action_roll(
                actor,
                attempt_id="V056-DEDUCE",
                forced_roll=3,
            )
            bridge = learned.get("player_recipient_consequence") or {}
            bridge_rows = bridge.get("results") or []
            learned_levels = knowledge_levels(actor)
            learned_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "successful-action-teaches-knowledge-to-real-character",
                learned.get("status") == "RESOLVED"
                and learned.get("outcome") == "SUCCESS"
                and learned_state.get(DEDUCED_FIELD) is True
                and bridge.get("status") == "APPLIED"
                and learned_levels.get(KNOWLEDGE_KEY) == 1
                and any(row.get("knowledge_key") == KNOWLEDGE_KEY for row in bridge_rows),
                f"outcome={learned.get('outcome')} bridge={bridge.get('status')} knowledge={learned_levels.get(KNOWLEDGE_KEY)} deduced={learned_state.get(DEDUCED_FIELD)}",
            )

            follow = next(
                (
                    row
                    for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == FOLLOW_ACTION_ID
                ),
                None,
            )
            check(
                "learned-knowledge-unlocks-follow-up-action",
                follow is not None and follow.get("eligible") is True,
                f"eligible={None if follow is None else follow.get('eligible')}",
            )

            completed = route_object_action_input(
                actor,
                "identificar turno manifiesto",
                attempt_id="V056-FOLLOW",
            )
            final_state = _plain_dict(getattr(manifest.db, "state", {}))
            final_world = _plain_dict(getattr(site.db, "world_state", {}))
            appearance = site.return_appearance(actor)
            check(
                "knowledge-unlocked-routine-mutates-persistent-world",
                completed.get("status") == "COMPLETED"
                and final_state.get(SHIFT_FIELD) is True
                and final_world.get(WORLD_SHIFT_FIELD) == 1
                and PRESENTATION_TEXT in appearance,
                f"status={completed.get('status')} shift={final_state.get(SHIFT_FIELD)} room_state={final_world.get(WORLD_SHIFT_FIELD)} visible_text={PRESENTATION_TEXT in appearance}",
            )

            locked = next(
                (
                    row
                    for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == FOLLOW_ACTION_ID
                ),
                None,
            )
            check(
                "completed-knowledge-follow-up-locks-itself",
                locked is not None
                and locked.get("eligible") is False
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in (locked.get("blockers") or [])),
                f"eligible={None if locked is None else locked.get('eligible')}",
            )

            replay_packet = {
                "action_id": "OBJECT_ACTION_RESOLVED:V056-DEDUCE",
                "action_type": "OBJECT_ACTION_RESOLVED",
                "actor_npc_id": "",
                "actor_dbref": int(actor.id),
                "actor_name": actor.key,
                "object_action_id": DEDUCE_ACTION_ID,
                "attempt_id": "V056-DEDUCE",
                "resolution_id": "V056-DEDUCE:RESOLUTION",
                "outcome": "SUCCESS",
                "provider": learned.get("provider"),
                "site_dbref": int(site.id),
                "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                "site_name": site.key,
                "object_dbref": int(manifest.id),
                "object_id": str(getattr(manifest.db, "object_id", "") or ""),
            }
            replay = apply_player_actor_consequences(actor, replay_packet)
            check(
                "player-knowledge-consequence-is-idempotent-per-action",
                replay.get("status") == "ALREADY_APPLIED"
                and knowledge_levels(actor).get(KNOWLEDGE_KEY) == 1,
                f"status={replay.get('status')} knowledge={knowledge_levels(actor).get(KNOWLEDGE_KEY)}",
            )

            second_install = ensure_v56_pilot_content()
            final_action_count = _count_by_id(getattr(manifest.db, "object_actions", []), DEDUCE_ACTION_ID) + _count_by_id(
                getattr(manifest.db, "object_actions", []), FOLLOW_ACTION_ID
            )
            final_rule_count = sum(
                1
                for row in consequence_rules()
                if str(row.get("id") or "") in {DEDUCE_RULE_ID, FOLLOW_RULE_ID}
            )
            preserve_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "v056-install-is-idempotent-and-preserves-played-state",
                second_install.get("success") is True
                and final_action_count == 2
                and final_rule_count == 2
                and preserve_state.get(DEDUCED_FIELD) is True
                and preserve_state.get(SHIFT_FIELD) is True
                and knowledge_levels(actor).get(KNOWLEDGE_KEY) == 1,
                f"actions={final_action_count} rules={final_rule_count} deduced={preserve_state.get(DEDUCED_FIELD)} shift={preserve_state.get(SHIFT_FIELD)} knowledge={knowledge_levels(actor).get(KNOWLEDGE_KEY)}",
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
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_history
            setattr(actor.db, APPLIED_ACTIONS_ATTR, original_player_applied)
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
            "STATE RESTORED: Character location/stats/Knowledge/histories, player consequence ledger, manifest state, room state and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: learning action + ACTOR Knowledge consequence + Knowledge-gated follow-up + presentation"
        )
        self.caller.msg("========================================================")


class CmdSizaResetV56(Command):
    """Reset only v0.56 prototype state and remove only its test Knowledge key from caller."""

    key = "siza-reset-v56"
    aliases = ["reset-v56"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v56_world_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.56 RESET] FAIL | reason={result.get('reason')} | build={PLAYER_ROLL_BUILD}"
            )
            return

        levels = knowledge_levels(self.caller)
        before = levels.pop(KNOWLEDGE_KEY, None)
        self.caller.db.knowledge = levels
        self.caller.msg(f"=== SIZA v0.56 RESET | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"PASS player-knowledge playtest reset | manifest={result.get('manifest').key}#{result.get('manifest').id} | "
            f"deduced=False | shift_identified=False | {KNOWLEDGE_KEY}: {before if before is not None else 'UNSET'} -> UNSET"
        )
        self.caller.msg("Pista de turno identificado visible=False")
        self.caller.msg("No se tocaron estados v0.51-v0.55, jobs, NPCs, exits, skills ni otros Knowledge.")
        self.caller.msg("========================================================")
