from evennia import Command

from services.action_resolution_engine import action_resolution_history, adventure_stats, set_adventure_stat
from services.confront_d6_resolution_engine import CONFRONT_D6_PROVIDER
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.npc_simulation import find_npc
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v54 import (
    CONFRONT_ACTION_ID,
    CONFRONTED_FIELD,
    CONFRONT_RULE_ID,
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    TARGET_STAT,
    WORLD_CONFRONTED_FIELD,
    ensure_v54_pilot_content,
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


class CmdSizaValidateV54(Command):
    """Validate player-facing opposed CONFRONT checks on a persistent NPC target."""

    key = "siza-validate-v54"
    aliases = ["validate-v54"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Trabajador B")
        install = ensure_v54_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg(
                f"[V0.54 VALIDATION] FAIL | actor/install missing | reason={install.get('reason')}"
            )
            return

        site = install.get("site")
        target = install.get("target")
        registry = get_consequence_registry(create=True)
        if not site or not target or not registry:
            self.caller.msg("[V0.54 VALIDATION] FAIL | persistent content/registry missing")
            return

        original_actor_location = actor.location
        original_target_location = target.location
        original_actor_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_target_stats = _clone(getattr(target.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_target_state = _clone(getattr(target.db, "state", {}))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.54 | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"Harness actor: {actor.key} | target={target.key}#{target.id} | site={site.key}#{site.id}"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if target.location != site:
                target.move_to(site, quiet=True)
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            set_adventure_stat(actor, "PSI", 4)
            set_adventure_stat(target, TARGET_STAT, 4)

            target_state = _plain_dict(original_target_state)
            target_state[CONFRONTED_FIELD] = False
            target.db.state = target_state
            world_state = _plain_dict(original_world_state)
            world_state.pop(WORLD_CONFRONTED_FIELD, None)
            site.db.world_state = world_state

            action_count = sum(
                1
                for row in list(getattr(target.db, "object_actions", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == CONFRONT_ACTION_ID
            )
            rule_count = sum(
                1 for row in consequence_rules() if str(row.get("id") or "") == CONFRONT_RULE_ID
            )
            presentation_count = sum(
                1
                for row in list(getattr(site.db, "state_presentations", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == PRESENTATION_ID
            )
            check(
                "persistent-confront-content-is-installed-once",
                action_count == 1
                and rule_count == 1
                and presentation_count == 1
                and adventure_stats(target).get(TARGET_STAT) == 4,
                f"actions={action_count} rules={rule_count} presentations={presentation_count} target_{TARGET_STAT}=4",
            )

            pending_target_win = route_object_action_input(
                actor,
                "presionar informante",
                attempt_id="V054-TARGET-WIN",
            )
            resolution = next(
                (
                    row
                    for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V054-TARGET-WIN:RESOLUTION"
                ),
                None,
            )
            check(
                "real-input-enters-authored-confront-pending-resolution",
                pending_target_win.get("status") == "PENDING_RESOLUTION"
                and resolution is not None
                and resolution.get("mode") == "CONFRONT"
                and resolution.get("actor_stat") == "PSI"
                and resolution.get("actor_stat_value") == 4
                and resolution.get("target_stat") == TARGET_STAT
                and resolution.get("target_stat_value") == 4,
                f"status={pending_target_win.get('status')} actor=4 target={None if resolution is None else resolution.get('target_stat_value')}",
            )

            target_win = resolve_pending_object_action_roll(
                actor,
                attempt_id="V054-TARGET-WIN",
                forced_roll=2,
                forced_target_roll=5,
            )
            state_after_target_win = _plain_dict(getattr(target.db, "state", {}))
            world_after_target_win = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "opposed-roll-can-produce-target-win-without-world-mutation",
                target_win.get("status") == "RESOLVED"
                and target_win.get("outcome") == "TARGET_WIN"
                and target_win.get("actor_total") == 6
                and target_win.get("target_total") == 9
                and state_after_target_win.get(CONFRONTED_FIELD) is False
                and WORLD_CONFRONTED_FIELD not in world_after_target_win,
                f"actor={target_win.get('actor_total')} target={target_win.get('target_total')} outcome={target_win.get('outcome')}",
            )

            retry_after_target = next(
                (
                    row
                    for row in inspect_object_actions(actor, target)
                    if str(row.get("id") or "") == CONFRONT_ACTION_ID
                ),
                None,
            )
            check(
                "target-win-leaves-confront-retryable",
                retry_after_target is not None and retry_after_target.get("eligible") is True,
                f"eligible={None if retry_after_target is None else retry_after_target.get('eligible')}",
            )

            pending_tie = route_object_action_input(
                actor,
                "confrontar informante",
                attempt_id="V054-TIE",
            )
            tie = resolve_pending_object_action_roll(
                actor,
                attempt_id="V054-TIE",
                forced_roll=3,
                forced_target_roll=3,
            )
            state_after_tie = _plain_dict(getattr(target.db, "state", {}))
            check(
                "opposed-roll-can-produce-tie-without-consequence",
                pending_tie.get("status") == "PENDING_RESOLUTION"
                and tie.get("status") == "RESOLVED"
                and tie.get("outcome") == "TIE"
                and tie.get("actor_total") == 7
                and tie.get("target_total") == 7
                and state_after_tie.get(CONFRONTED_FIELD) is False,
                f"actor={tie.get('actor_total')} target={tie.get('target_total')} outcome={tie.get('outcome')}",
            )

            retry_after_tie = next(
                (
                    row
                    for row in inspect_object_actions(actor, target)
                    if str(row.get("id") or "") == CONFRONT_ACTION_ID
                ),
                None,
            )
            check(
                "tie-leaves-confront-retryable",
                retry_after_tie is not None and retry_after_tie.get("eligible") is True,
                f"eligible={None if retry_after_tie is None else retry_after_tie.get('eligible')}",
            )

            pending_actor_win = route_object_action_input(
                actor,
                "presionar informante",
                attempt_id="V054-ACTOR-WIN",
            )
            actor_win = resolve_pending_object_action_roll(
                actor,
                attempt_id="V054-ACTOR-WIN",
                forced_roll=6,
                forced_target_roll=2,
            )
            consequence = (actor_win.get("action_result") or {}).get("action_consequence") or {}
            check(
                "opposed-roll-actor-win-flows-through-consequence-engine",
                pending_actor_win.get("status") == "PENDING_RESOLUTION"
                and actor_win.get("status") == "RESOLVED"
                and actor_win.get("outcome") == "ACTOR_WIN"
                and actor_win.get("actor_total") == 10
                and actor_win.get("target_total") == 6
                and consequence.get("status") == "PROCESSED",
                f"actor={actor_win.get('actor_total')} target={actor_win.get('target_total')} outcome={actor_win.get('outcome')} consequence={consequence.get('status')}",
            )

            success_state = _plain_dict(getattr(target.db, "state", {}))
            success_world = _plain_dict(getattr(site.db, "world_state", {}))
            appearance = site.return_appearance(actor)
            check(
                "actor-win-mutates-target-and-room-presentation",
                success_state.get(CONFRONTED_FIELD) is True
                and success_world.get(WORLD_CONFRONTED_FIELD) == 1
                and PRESENTATION_TEXT in appearance,
                f"cedio={success_state.get(CONFRONTED_FIELD)} room_state={success_world.get(WORLD_CONFRONTED_FIELD)} visible_text={PRESENTATION_TEXT in appearance}",
            )

            locked = next(
                (
                    row
                    for row in inspect_object_actions(actor, target)
                    if str(row.get("id") or "") == CONFRONT_ACTION_ID
                ),
                None,
            )
            check(
                "completed-confront-locks-itself-by-target-state",
                locked is not None
                and locked.get("eligible") is False
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in (locked.get("blockers") or [])),
                f"eligible={None if locked is None else locked.get('eligible')}",
            )

            success_resolution = next(
                (
                    row
                    for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V054-ACTOR-WIN:RESOLUTION"
                ),
                None,
            )
            data = _plain_dict((success_resolution or {}).get("resolution_data"))
            check(
                "confront-resolution-persists-both-sides-audit-data",
                success_resolution is not None
                and success_resolution.get("provider") == CONFRONT_D6_PROVIDER
                and data.get("actor_die") == 6
                and data.get("actor_stat_value") == 4
                and data.get("actor_total") == 10
                and data.get("target_die") == 2
                and data.get("target_stat_value") == 4
                and data.get("target_total") == 6,
                f"provider={(success_resolution or {}).get('provider')} data={data}",
            )

            second_install = ensure_v54_pilot_content()
            final_action_count = sum(
                1
                for row in list(getattr(target.db, "object_actions", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == CONFRONT_ACTION_ID
            )
            final_rule_count = sum(
                1 for row in consequence_rules() if str(row.get("id") or "") == CONFRONT_RULE_ID
            )
            final_presentation_count = sum(
                1
                for row in list(getattr(site.db, "state_presentations", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == PRESENTATION_ID
            )
            final_state = _plain_dict(getattr(target.db, "state", {}))
            check(
                "v054-install-is-idempotent-and-preserves-actor-win-state",
                second_install.get("success") is True
                and final_action_count == 1
                and final_rule_count == 1
                and final_presentation_count == 1
                and final_state.get(CONFRONTED_FIELD) is True,
                f"actions={final_action_count} rules={final_rule_count} presentations={final_presentation_count} cedio={final_state.get(CONFRONTED_FIELD)}",
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
                if target.location != original_target_location:
                    target.move_to(original_target_location, quiet=True)
            except Exception:
                pass
            actor.db.adventure_stats = original_actor_stats
            target.db.adventure_stats = original_target_stats
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_history
            target.db.state = original_target_state
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
            "STATE RESTORED: actor/target locations and stats, histories, target state, room state and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: CONFRONT action + ACTOR_WIN consequence + room presentation"
        )
        self.caller.msg("========================================================")
