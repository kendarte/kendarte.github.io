from evennia import Command

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.accumulate_d6_resolution_engine import ACCUMULATE_D6_PROVIDER
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.direct_d6_resolution_engine import DIRECT_D6_PROVIDER
from services.npc_simulation import find_npc
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v52 import ANALYZE_ACTION_ID, ANALYZED_FIELD
from world.upgrade_pilot_v53 import (
    COMPLETE_FIELD,
    COMPLETE_RULE_ID,
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    PROGRESS_FIELD,
    PROGRESS_GOAL,
    PROGRESS_RULE_ID,
    RECONSTRUCT_ACTION_ID,
    SETBACK_RULE_ID,
    WORLD_COMPLETE_FIELD,
    ensure_v53_pilot_content,
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


def _item_id(raw):
    try:
        return str(raw.get("id") or "")
    except Exception:
        return ""


class CmdSizaValidateV53(Command):
    """Validate persistent ACCUMULATE d6 gameplay without regressing DIRECT player rolls."""

    key = "siza-validate-v53"
    aliases = ["validate-v53"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        install = ensure_v53_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg(
                f"[V0.53 VALIDATION] FAIL | actor/install missing | reason={install.get('reason')}"
            )
            return

        site = install.get("site")
        manifest = install.get("manifest")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not registry:
            self.caller.msg("[V0.53 VALIDATION] FAIL | persistent content/registry missing")
            return

        original_location = actor.location
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
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

        self.caller.msg(f"=== SIZA VALIDATION v0.53 | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"Harness NPC: {actor.key} | site={site.key}#{site.id} | manifest={manifest.key}#{manifest.id}"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            set_adventure_stat(actor, "PER", 4)
            set_adventure_stat(actor, "INT", 4)

            state = _plain_dict(original_manifest_state)
            state["analyzed"] = False
            state[PROGRESS_FIELD] = 0
            state[COMPLETE_FIELD] = False
            manifest.db.state = state

            world_state = _plain_dict(original_world_state)
            world_state[MANIFEST_VISIBLE_FIELD] = 1
            world_state.pop(ANALYZED_FIELD, None)
            world_state.pop(WORLD_COMPLETE_FIELD, None)
            site.db.world_state = world_state

            action_count = sum(
                1 for row in list(getattr(manifest.db, "object_actions", []) or [])
                if _item_id(row) == RECONSTRUCT_ACTION_ID
            )
            rule_ids = {
                str(row.get("id") or "")
                for row in consequence_rules()
                if str(row.get("id") or "") in {PROGRESS_RULE_ID, SETBACK_RULE_ID, COMPLETE_RULE_ID}
            }
            presentation_count = sum(
                1 for row in list(getattr(site.db, "state_presentations", []) or [])
                if _item_id(row) == PRESENTATION_ID
            )
            check(
                "persistent-accumulate-content-is-installed-once",
                action_count == 1 and len(rule_ids) == 3 and presentation_count == 1,
                f"actions={action_count} rules={len(rule_ids)} presentations={presentation_count}",
            )

            blocked = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V053-BLOCKED",
            )
            check(
                "accumulate-action-is-blocked-until-prerequisite-analysis",
                blocked.get("matched") is True
                and blocked.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={blocked.get('status')}",
            )

            direct_pending = route_object_action_input(
                actor,
                "analizar manifiesto",
                attempt_id="V053-DIRECT-REGRESSION",
            )
            direct = resolve_pending_object_action_roll(
                actor,
                attempt_id="V053-DIRECT-REGRESSION",
                forced_roll=3,
            )
            direct_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "generic-player-roll-preserves-v052-direct-resolution",
                direct_pending.get("status") == "PENDING_RESOLUTION"
                and direct.get("status") == "RESOLVED"
                and direct.get("mode") == "DIRECT"
                and direct.get("outcome") == "SUCCESS"
                and direct.get("provider") == DIRECT_D6_PROVIDER
                and direct_state.get("analyzed") is True,
                f"mode={direct.get('mode')} outcome={direct.get('outcome')} provider={direct.get('provider')}",
            )

            zero_pending = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V053-FAIL-ZERO",
            )
            zero_packet = zero_pending.get("action_result") or {}
            check(
                "real-input-enters-authored-accumulate-pending-resolution",
                zero_pending.get("status") == "PENDING_RESOLUTION"
                and zero_packet.get("resolution_mode") == "ACCUMULATE"
                and zero_packet.get("actor_stat") == "INT"
                and zero_packet.get("actor_stat_value") == 4
                and zero_packet.get("difficulty") == 7,
                f"status={zero_pending.get('status')} mode={zero_packet.get('resolution_mode')} stat={zero_packet.get('actor_stat_value')} difficulty={zero_packet.get('difficulty')}",
            )

            zero_fail = resolve_pending_object_action_roll(
                actor,
                attempt_id="V053-FAIL-ZERO",
                forced_roll=2,
            )
            zero_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "failed-accumulate-roll-at-zero-produces-failure-without-negative-progress",
                zero_fail.get("status") == "RESOLVED"
                and zero_fail.get("mode") == "ACCUMULATE"
                and zero_fail.get("outcome") == "FAILURE"
                and zero_fail.get("progress_before") == 0
                and zero_state.get(PROGRESS_FIELD) == 0,
                f"d6={zero_fail.get('die')} outcome={zero_fail.get('outcome')} progress={zero_state.get(PROGRESS_FIELD)}",
            )

            progress_pending = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V053-PROGRESS-1",
            )
            progress = resolve_pending_object_action_roll(
                actor,
                attempt_id="V053-PROGRESS-1",
                forced_roll=3,
            )
            progress_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "successful-accumulate-roll-persists-progress",
                progress_pending.get("status") == "PENDING_RESOLUTION"
                and progress.get("status") == "RESOLVED"
                and progress.get("outcome") == "PROGRESS"
                and progress.get("provider") == ACCUMULATE_D6_PROVIDER
                and progress_state.get(PROGRESS_FIELD) == 1,
                f"outcome={progress.get('outcome')} progress={progress_state.get(PROGRESS_FIELD)}/{PROGRESS_GOAL}",
            )

            setback_pending = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V053-SETBACK-1",
            )
            setback = resolve_pending_object_action_roll(
                actor,
                attempt_id="V053-SETBACK-1",
                forced_roll=2,
            )
            setback_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "failed-accumulate-roll-after-progress-produces-persistent-setback",
                setback_pending.get("status") == "PENDING_RESOLUTION"
                and setback.get("status") == "RESOLVED"
                and setback.get("outcome") == "SETBACK"
                and setback_state.get(PROGRESS_FIELD) == 0,
                f"outcome={setback.get('outcome')} progress={setback_state.get(PROGRESS_FIELD)}/{PROGRESS_GOAL}",
            )

            retry_pending = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V053-PROGRESS-2",
            )
            retry = resolve_pending_object_action_roll(
                actor,
                attempt_id="V053-PROGRESS-2",
                forced_roll=3,
            )
            retry_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "accumulate-action-remains-retryable-after-setback",
                retry_pending.get("status") == "PENDING_RESOLUTION"
                and retry.get("outcome") == "PROGRESS"
                and retry_state.get(PROGRESS_FIELD) == 1,
                f"outcome={retry.get('outcome')} progress={retry_state.get(PROGRESS_FIELD)}/{PROGRESS_GOAL}",
            )

            complete_pending = route_object_action_input(
                actor,
                "reconstruir secuencia del manifiesto",
                attempt_id="V053-COMPLETE",
            )
            complete = resolve_pending_object_action_roll(
                actor,
                attempt_id="V053-COMPLETE",
                forced_roll=3,
            )
            complete_state = _plain_dict(getattr(manifest.db, "state", {}))
            complete_world = _plain_dict(getattr(site.db, "world_state", {}))
            appearance = site.return_appearance(actor)
            complete_result = complete.get("action_result") or {}
            complete_consequence = complete_result.get("action_consequence") or {}
            check(
                "final-accumulate-success-completes-and-mutates-persistent-world",
                complete_pending.get("status") == "PENDING_RESOLUTION"
                and complete.get("status") == "RESOLVED"
                and complete.get("outcome") == "COMPLETE"
                and complete_state.get(PROGRESS_FIELD) == PROGRESS_GOAL
                and complete_state.get(COMPLETE_FIELD) is True
                and complete_world.get(WORLD_COMPLETE_FIELD) == 1
                and complete_consequence.get("status") == "PROCESSED"
                and PRESENTATION_TEXT in appearance,
                f"outcome={complete.get('outcome')} progress={complete_state.get(PROGRESS_FIELD)}/{PROGRESS_GOAL} complete={complete_state.get(COMPLETE_FIELD)} visible_text={PRESENTATION_TEXT in appearance}",
            )

            final_action = next(
                (
                    row for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == RECONSTRUCT_ACTION_ID
                ),
                None,
            )
            check(
                "completed-accumulate-action-locks-itself-by-object-state",
                final_action is not None
                and final_action.get("eligible") is False
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in final_action.get("blockers") or []),
                f"eligible={None if final_action is None else final_action.get('eligible')}",
            )

            complete_resolution = next(
                (
                    row for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V053-COMPLETE:RESOLUTION"
                ),
                None,
            )
            audit = _plain_dict((complete_resolution or {}).get("resolution_data"))
            check(
                "accumulate-resolution-persists-auditable-progress-data",
                complete_resolution is not None
                and complete_resolution.get("provider") == ACCUMULATE_D6_PROVIDER
                and audit.get("die") == 3
                and audit.get("actor_stat") == "INT"
                and audit.get("progress_before") == 1
                and audit.get("progress_projected") == PROGRESS_GOAL
                and audit.get("progress_goal") == PROGRESS_GOAL,
                f"provider={(complete_resolution or {}).get('provider')} data={audit}",
            )

            second_install = ensure_v53_pilot_content()
            action_count_after = sum(
                1 for row in list(getattr(manifest.db, "object_actions", []) or [])
                if _item_id(row) == RECONSTRUCT_ACTION_ID
            )
            rule_ids_after = [
                str(row.get("id") or "") for row in consequence_rules()
                if str(row.get("id") or "") in {PROGRESS_RULE_ID, SETBACK_RULE_ID, COMPLETE_RULE_ID}
            ]
            presentation_count_after = sum(
                1 for row in list(getattr(site.db, "state_presentations", []) or [])
                if _item_id(row) == PRESENTATION_ID
            )
            preserved = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "v053-install-is-idempotent-and-preserves-completed-progress",
                second_install.get("success") is True
                and action_count_after == 1
                and len(rule_ids_after) == 3
                and len(set(rule_ids_after)) == 3
                and presentation_count_after == 1
                and preserved.get(PROGRESS_FIELD) == PROGRESS_GOAL
                and preserved.get(COMPLETE_FIELD) is True,
                f"actions={action_count_after} rules={len(rule_ids_after)} presentations={presentation_count_after} progress={preserved.get(PROGRESS_FIELD)} complete={preserved.get(COMPLETE_FIELD)}",
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
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_history
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
            "GAMEPLAY STATE RESTORED: actor location/stats/histories, manifest state, room state and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: ACCUMULATE manifest action + progress/setback/complete consequences + room presentation"
        )
        self.caller.msg("========================================================")
