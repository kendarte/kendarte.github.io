from evennia import Command

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.direct_d6_resolution_engine import (
    DIRECT_D6_BUILD,
    calculate_direct_d6,
    resolve_pending_object_action_d6,
)
from services.npc_simulation import find_npc
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v52 import (
    ANALYZE_ACTION_ID,
    ANALYZE_RULE_ID,
    ANALYZED_FIELD,
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    ensure_v52_pilot_content,
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


class CmdSizaValidateV52(Command):
    """Validate the first player-facing DIRECT d6 provider on persistent Pescaderia content."""

    key = "siza-validate-v52"
    aliases = ["validate-v52"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        install = ensure_v52_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg(
                f"[V0.52 VALIDATION] FAIL | actor/install missing | reason={install.get('reason')}"
            )
            return

        site = install.get("site")
        manifest = install.get("manifest")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not registry:
            self.caller.msg("[V0.52 VALIDATION] FAIL | persistent content/registry missing")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.52 | {DIRECT_D6_BUILD} ===")
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

            state = _plain_dict(original_manifest_state)
            state["analyzed"] = False
            manifest.db.state = state
            world_state = _plain_dict(original_world_state)
            world_state.pop(MANIFEST_VISIBLE_FIELD, None)
            world_state.pop(ANALYZED_FIELD, None)
            site.db.world_state = world_state

            action_rows = [
                row
                for row in list(getattr(manifest.db, "object_actions", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == ANALYZE_ACTION_ID
            ]
            rules = [row for row in consequence_rules() if str(row.get("id") or "") == ANALYZE_RULE_ID]
            presentations = [
                row
                for row in list(getattr(site.db, "state_presentations", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == PRESENTATION_ID
            ]
            check(
                "persistent-checked-manifest-content-is-installed-once",
                len(action_rows) == 1 and len(rules) == 1 and len(presentations) == 1,
                f"actions={len(action_rows)} rules={len(rules)} presentations={len(presentations)}",
            )

            hidden = route_object_action_input(
                actor,
                "examinar manifiesto",
                attempt_id="V052-HIDDEN",
            )
            check(
                "hidden-manifest-cannot-start-player-check",
                hidden.get("matched") is True
                and hidden.get("status") == "OBJECT_NOT_VISIBLE"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={hidden.get('status')}",
            )

            world_state[MANIFEST_VISIBLE_FIELD] = 1
            site.db.world_state = world_state
            pending_fail = route_object_action_input(
                actor,
                "examinar manifiesto",
                attempt_id="V052-FAIL-ATTEMPT",
            )
            pending_fail_result = pending_fail.get("action_result") or {}
            check(
                "real-input-enters-authored-direct-pending-resolution",
                pending_fail.get("status") == "PENDING_RESOLUTION"
                and pending_fail_result.get("actor_stat") == "PER"
                and pending_fail_result.get("actor_stat_value") == 4
                and pending_fail_result.get("difficulty") == 7,
                f"status={pending_fail.get('status')} stat={pending_fail_result.get('actor_stat_value')} difficulty={pending_fail_result.get('difficulty')}",
            )

            failed = resolve_pending_object_action_d6(
                actor,
                attempt_id="V052-FAIL-ATTEMPT",
                forced_roll=2,
            )
            fail_state = _plain_dict(getattr(manifest.db, "state", {}))
            fail_world = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "d6-plus-stat-below-difficulty-resolves-failure-without-side-effect",
                failed.get("status") == "RESOLVED"
                and failed.get("outcome") == "FAILURE"
                and failed.get("die") == 2
                and failed.get("total") == 6
                and fail_state.get("analyzed") is False
                and ANALYZED_FIELD not in fail_world,
                f"d6={failed.get('die')} total={failed.get('total')} outcome={failed.get('outcome')} analyzed={fail_state.get('analyzed')}",
            )

            followup = next(
                (
                    row
                    for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == ANALYZE_ACTION_ID
                ),
                None,
            )
            check(
                "failed-direct-check-leaves-authored-action-retryable",
                followup is not None and followup.get("eligible") is True,
                f"eligible={None if followup is None else followup.get('eligible')}",
            )

            pending_success = route_object_action_input(
                actor,
                "analizar manifiesto",
                attempt_id="V052-SUCCESS-ATTEMPT",
            )
            succeeded = resolve_pending_object_action_d6(
                actor,
                attempt_id="V052-SUCCESS-ATTEMPT",
                forced_roll=3,
            )
            success_result = succeeded.get("action_result") or {}
            consequence = success_result.get("action_consequence") or {}
            check(
                "d6-plus-stat-equal-difficulty-resolves-success",
                pending_success.get("status") == "PENDING_RESOLUTION"
                and succeeded.get("status") == "RESOLVED"
                and succeeded.get("outcome") == "SUCCESS"
                and succeeded.get("die") == 3
                and succeeded.get("total") == 7
                and consequence.get("status") == "PROCESSED",
                f"d6={succeeded.get('die')} total={succeeded.get('total')} outcome={succeeded.get('outcome')} consequence={consequence.get('status')}",
            )

            success_state = _plain_dict(getattr(manifest.db, "state", {}))
            success_world = _plain_dict(getattr(site.db, "world_state", {}))
            appearance = site.return_appearance(actor)
            check(
                "successful-player-roll-mutates-persistent-object-and-room-presentation",
                success_state.get("analyzed") is True
                and success_world.get(ANALYZED_FIELD) == 1
                and PRESENTATION_TEXT in appearance,
                f"analyzed={success_state.get('analyzed')} room_state={success_world.get(ANALYZED_FIELD)} visible_text={PRESENTATION_TEXT in appearance}",
            )

            resolution_rows = action_resolution_history(actor)
            success_resolution = next(
                (
                    row
                    for row in resolution_rows
                    if str(row.get("resolution_id") or "") == "V052-SUCCESS-ATTEMPT:RESOLUTION"
                ),
                None,
            )
            resolution_data = _plain_dict((success_resolution or {}).get("resolution_data"))
            check(
                "player-roll-persists-auditable-d6-resolution-data",
                success_resolution is not None
                and success_resolution.get("provider") == "SIZA_DIRECT_D6"
                and resolution_data.get("die") == 3
                and resolution_data.get("actor_stat_value") == 4
                and resolution_data.get("total") == 7
                and resolution_data.get("difficulty") == 7,
                f"provider={(success_resolution or {}).get('provider')} data={resolution_data}",
            )

            second_install = ensure_v52_pilot_content()
            action_count = sum(
                1
                for row in list(getattr(manifest.db, "object_actions", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == ANALYZE_ACTION_ID
            )
            rule_count = sum(1 for row in consequence_rules() if str(row.get("id") or "") == ANALYZE_RULE_ID)
            presentation_count = sum(
                1
                for row in list(getattr(site.db, "state_presentations", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == PRESENTATION_ID
            )
            current_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "v052-install-is-idempotent-and-preserves-success-state",
                second_install.get("success") is True
                and action_count == 1
                and rule_count == 1
                and presentation_count == 1
                and current_state.get("analyzed") is True,
                f"actions={action_count} rules={rule_count} presentations={presentation_count} analyzed={current_state.get('analyzed')}",
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
            "PERSISTENT CONTENT RETAINED: checked manifest action + SUCCESS consequence + room presentation"
        )
        self.caller.msg("========================================================")
