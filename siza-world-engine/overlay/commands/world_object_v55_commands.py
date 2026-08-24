from evennia import Command

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.npc_simulation import find_npc
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from services.synchronize_d6_resolution_engine import SYNCHRONIZE_D6_PROVIDER
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v53 import COMPLETE_FIELD
from world.upgrade_pilot_v55 import (
    PRESENTATION_ID,
    PRESENTATION_TEXT,
    SYNC_ACTION_ID,
    SYNC_PARITY,
    SYNC_RULE_ID,
    SYNCED_FIELD,
    SYNC_STAT,
    WORLD_SYNCED_FIELD,
    ensure_v55_pilot_content,
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


class CmdSizaValidateV55(Command):
    """Validate player-facing SYNCHRONIZE parity checks on the persistent manifest."""

    key = "siza-validate-v55"
    aliases = ["validate-v55"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Trabajador B")
        install = ensure_v55_pilot_content()
        if not actor or not bool(install.get("success")):
            self.caller.msg(
                f"[V0.55 VALIDATION] FAIL | actor/install missing | reason={install.get('reason')}"
            )
            return

        site = install.get("site")
        manifest = install.get("manifest")
        registry = get_consequence_registry(create=True)
        if not site or not manifest or not registry:
            self.caller.msg("[V0.55 VALIDATION] FAIL | persistent content/registry missing")
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

        self.caller.msg(f"=== SIZA VALIDATION v0.55 | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"Harness actor: {actor.key} | manifest={manifest.key}#{manifest.id} | site={site.key}#{site.id}"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            set_adventure_stat(actor, SYNC_STAT, 4)

            state = _plain_dict(original_manifest_state)
            state[COMPLETE_FIELD] = False
            state[SYNCED_FIELD] = False
            manifest.db.state = state
            world_state = _plain_dict(original_world_state)
            world_state[MANIFEST_VISIBLE_FIELD] = 1
            world_state.pop(WORLD_SYNCED_FIELD, None)
            site.db.world_state = world_state

            action_count = sum(
                1
                for row in list(getattr(manifest.db, "object_actions", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == SYNC_ACTION_ID
            )
            rule_count = sum(
                1 for row in consequence_rules() if str(row.get("id") or "") == SYNC_RULE_ID
            )
            presentation_count = sum(
                1
                for row in list(getattr(site.db, "state_presentations", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == PRESENTATION_ID
            )
            check(
                "persistent-synchronize-content-is-installed-once",
                action_count == 1 and rule_count == 1 and presentation_count == 1,
                f"actions={action_count} rules={rule_count} presentations={presentation_count}",
            )

            blocked = route_object_action_input(actor, "sincronizar sellos manifiesto")
            check(
                "synchronize-action-is-blocked-until-route-reconstructed",
                blocked.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={blocked.get('status')}",
            )

            state[COMPLETE_FIELD] = True
            manifest.db.state = state
            pending_miss = route_object_action_input(
                actor,
                "sincronizar sellos manifiesto",
                attempt_id="V055-MISS",
            )
            resolution = next(
                (
                    row
                    for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V055-MISS:RESOLUTION"
                ),
                None,
            )
            metadata = _plain_dict((resolution or {}).get("metadata"))
            check(
                "real-input-enters-authored-synchronize-pending-resolution",
                pending_miss.get("status") == "PENDING_RESOLUTION"
                and resolution is not None
                and resolution.get("mode") == "SYNCHRONIZE"
                and resolution.get("actor_stat") == SYNC_STAT
                and resolution.get("actor_stat_value") == 4
                and metadata.get("parity") == SYNC_PARITY,
                f"status={pending_miss.get('status')} stat={None if resolution is None else resolution.get('actor_stat_value')} parity={metadata.get('parity')}",
            )

            miss = resolve_pending_object_action_roll(
                actor,
                attempt_id="V055-MISS",
                forced_roll=1,
            )
            miss_state = _plain_dict(getattr(manifest.db, "state", {}))
            miss_world = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "odd-total-produces-miss-without-world-mutation",
                miss.get("status") == "RESOLVED"
                and miss.get("outcome") == "MISS"
                and miss.get("total") == 5
                and miss.get("result_parity") == "ODD"
                and miss_state.get(SYNCED_FIELD) is False
                and WORLD_SYNCED_FIELD not in miss_world,
                f"d6={miss.get('die')} total={miss.get('total')} parity={miss.get('result_parity')} outcome={miss.get('outcome')}",
            )

            retry = next(
                (
                    row
                    for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == SYNC_ACTION_ID
                ),
                None,
            )
            check(
                "miss-leaves-synchronize-action-retryable",
                retry is not None and retry.get("eligible") is True,
                f"eligible={None if retry is None else retry.get('eligible')}",
            )

            pending_sync = route_object_action_input(
                actor,
                "alinear sellos manifiesto",
                attempt_id="V055-SYNC",
            )
            synced = resolve_pending_object_action_roll(
                actor,
                attempt_id="V055-SYNC",
                forced_roll=2,
            )
            consequence = (synced.get("action_result") or {}).get("action_consequence") or {}
            check(
                "even-total-produces-sync-through-consequence-engine",
                pending_sync.get("status") == "PENDING_RESOLUTION"
                and synced.get("status") == "RESOLVED"
                and synced.get("outcome") == "SYNC"
                and synced.get("total") == 6
                and synced.get("result_parity") == "EVEN"
                and consequence.get("status") == "PROCESSED",
                f"d6={synced.get('die')} total={synced.get('total')} parity={synced.get('result_parity')} outcome={synced.get('outcome')} consequence={consequence.get('status')}",
            )

            sync_state = _plain_dict(getattr(manifest.db, "state", {}))
            sync_world = _plain_dict(getattr(site.db, "world_state", {}))
            appearance = site.return_appearance(actor)
            check(
                "sync-mutates-manifest-and-room-presentation",
                sync_state.get(SYNCED_FIELD) is True
                and sync_world.get(WORLD_SYNCED_FIELD) == 1
                and PRESENTATION_TEXT in appearance,
                f"synced={sync_state.get(SYNCED_FIELD)} room_state={sync_world.get(WORLD_SYNCED_FIELD)} visible_text={PRESENTATION_TEXT in appearance}",
            )

            locked = next(
                (
                    row
                    for row in inspect_object_actions(actor, manifest)
                    if str(row.get("id") or "") == SYNC_ACTION_ID
                ),
                None,
            )
            check(
                "completed-synchronize-action-locks-itself-by-object-state",
                locked is not None
                and locked.get("eligible") is False
                and any(str(row.get("kind") or "") == "OBJECT_STATE" for row in (locked.get("blockers") or [])),
                f"eligible={None if locked is None else locked.get('eligible')}",
            )

            success_resolution = next(
                (
                    row
                    for row in action_resolution_history(actor)
                    if str(row.get("resolution_id") or "") == "V055-SYNC:RESOLUTION"
                ),
                None,
            )
            data = _plain_dict((success_resolution or {}).get("resolution_data"))
            check(
                "synchronize-resolution-persists-auditable-parity-data",
                success_resolution is not None
                and success_resolution.get("provider") == SYNCHRONIZE_D6_PROVIDER
                and data.get("die") == 2
                and data.get("actor_stat_value") == 4
                and data.get("total") == 6
                and data.get("required_parity") == "EVEN"
                and data.get("result_parity") == "EVEN",
                f"provider={(success_resolution or {}).get('provider')} data={data}",
            )

            second_install = ensure_v55_pilot_content()
            final_action_count = sum(
                1
                for row in list(getattr(manifest.db, "object_actions", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == SYNC_ACTION_ID
            )
            final_rule_count = sum(
                1 for row in consequence_rules() if str(row.get("id") or "") == SYNC_RULE_ID
            )
            final_presentation_count = sum(
                1
                for row in list(getattr(site.db, "state_presentations", []) or [])
                if str(getattr(row, "get", lambda *_: None)("id") or "") == PRESENTATION_ID
            )
            final_state = _plain_dict(getattr(manifest.db, "state", {}))
            check(
                "v055-install-is-idempotent-and-preserves-sync-state",
                second_install.get("success") is True
                and final_action_count == 1
                and final_rule_count == 1
                and final_presentation_count == 1
                and final_state.get(SYNCED_FIELD) is True,
                f"actions={final_action_count} rules={final_rule_count} presentations={final_presentation_count} synced={final_state.get(SYNCED_FIELD)}",
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
            "STATE RESTORED: actor location/stats/histories, manifest state, room state and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: SYNCHRONIZE action + SYNC consequence + room presentation"
        )
        self.caller.msg("========================================================")
