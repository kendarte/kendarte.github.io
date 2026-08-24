from evennia import Command, search_object

from services.action_resolution_engine import action_resolution_history
from services.consequence_engine import consequence_rules, get_consequence_registry
from services.npc_simulation import find_npc
from services.object_action_engine import inspect_object_actions, object_action_history
from services.object_action_input_engine import route_object_action_input
from world.upgrade_pilot_v51 import (
    CONTAINER_ID,
    INSPECT_ACTION_ID,
    INSPECT_RULE_ID,
    MANIFEST_ID,
    MANIFEST_NAME,
    MANIFEST_VISIBLE_FIELD,
    OPEN_RULE_ID,
    PESCADERIA_ID,
    PILOT_BUILD,
    ensure_v51_pilot_content,
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


def _find_pescaderia():
    for obj in search_object("Pescaderia de Darsena"):
        if str(getattr(obj.db, "room_id", "") or "") == PESCADERIA_ID:
            return obj
    return None


class CmdSizaValidateV51(Command):
    """Install and validate the first persistent playable Pescaderia object-action loop."""

    key = "siza-validate-v51"
    aliases = ["validate-v51"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        site = _find_pescaderia()
        if not actor or not site:
            self.caller.msg("[V0.51 VALIDATION] FAIL | Informante C or Pescaderia missing")
            return

        job_tasks_before_install = _clone(getattr(site.db, "job_tasks", []))
        install = ensure_v51_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(
                f"[V0.51 VALIDATION] FAIL | persistent content install failed: {install.get('reason')}"
            )
            return

        container = install.get("container")
        manifest = install.get("manifest")
        registry = get_consequence_registry(create=True)
        if not container or not manifest or not registry:
            self.caller.msg("[V0.51 VALIDATION] FAIL | installed content/registry missing")
            return

        original_location = actor.location
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_container_state = _clone(getattr(container.db, "state", {}))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        container_dbref = int(container.id)
        manifest_dbref = int(manifest.id)
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.51 | {PILOT_BUILD} ===")
        self.caller.msg(
            f"Persistent site: {site.key} | dbref=#{site.id} | container=#{container.id} | manifest=#{manifest.id}"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []

            test_state = _plain_dict(original_container_state)
            test_state.update({"sealed": True, "opened_count": 0, "inspected": False})
            container.db.state = test_state

            test_world_state = _plain_dict(original_world_state)
            test_world_state.pop(MANIFEST_VISIBLE_FIELD, None)
            site.db.world_state = test_world_state

            check(
                "persistent-playable-content-is-installed-on-real-pescaderia",
                container.location == site
                and manifest.location == site
                and str(container.db.object_id or "") == CONTAINER_ID
                and str(manifest.db.object_id or "") == MANIFEST_ID,
                f"container={container.db.object_id}@{container.location.key if container.location else None} manifest={manifest.db.object_id}@{manifest.location.key if manifest.location else None}",
            )

            check(
                "v051-install-does-not-touch-existing-pescaderia-job-tasks",
                _clone(getattr(site.db, "job_tasks", [])) == job_tasks_before_install,
                f"job_tasks={len(list(getattr(site.db, 'job_tasks', []) or []))}",
            )

            opened = route_object_action_input(
                actor,
                "abrir cajon de reparto",
                attempt_id="V051-VALIDATE-OPEN",
            )
            opened_result = opened.get("action_result") or {}
            opened_state = _plain_dict(getattr(container.db, "state", {}))
            open_consequence = opened_result.get("action_consequence") or {}
            check(
                "real-text-opens-persistent-container-through-consequence-engine",
                opened.get("matched") is True
                and opened.get("status") == "COMPLETED"
                and open_consequence.get("status") == "PROCESSED"
                and opened_state.get("sealed") is False
                and opened_state.get("opened_count") == 1,
                f"status={opened.get('status')} consequence={open_consequence.get('status')} sealed={opened_state.get('sealed')} opened_count={opened_state.get('opened_count')}",
            )

            followup = next(
                (
                    row
                    for row in inspect_object_actions(actor, container)
                    if str(row.get("id") or "") == INSPECT_ACTION_ID
                ),
                None,
            )
            check(
                "persistent-object-state-change-unlocks-followup-action",
                followup is not None and followup.get("eligible") is True,
                f"eligible={None if followup is None else followup.get('eligible')} sealed={opened_state.get('sealed')}",
            )

            inspected = route_object_action_input(
                actor,
                "registrar cajon de reparto",
                attempt_id="V051-VALIDATE-INSPECT",
            )
            inspected_result = inspected.get("action_result") or {}
            inspected_state = _plain_dict(getattr(container.db, "state", {}))
            world_state = _plain_dict(getattr(site.db, "world_state", {}))
            inspect_consequence = inspected_result.get("action_consequence") or {}
            appearance = site.return_appearance(actor)
            check(
                "followup-real-text-reveals-persistent-manifest-in-real-room-look",
                inspected.get("matched") is True
                and inspected.get("status") == "COMPLETED"
                and inspect_consequence.get("status") == "PROCESSED"
                and inspected_state.get("inspected") is True
                and world_state.get(MANIFEST_VISIBLE_FIELD) == 1
                and MANIFEST_NAME in appearance,
                f"status={inspected.get('status')} inspected={inspected_state.get('inspected')} manifest_state={world_state.get(MANIFEST_VISIBLE_FIELD)} visible_in_look={MANIFEST_NAME in appearance}",
            )

            check(
                "persistent-object-identities-survive-complete-gameplay-chain",
                int(container.id) == container_dbref
                and int(manifest.id) == manifest_dbref
                and container.location == site
                and manifest.location == site
                and str(container.db.object_id or "") == CONTAINER_ID
                and str(manifest.db.object_id or "") == MANIFEST_ID,
                f"container_dbref={container.id} manifest_dbref={manifest.id}",
            )

            second_install = ensure_v51_pilot_content()
            current_state = _plain_dict(getattr(container.db, "state", {}))
            current_world_state = _plain_dict(getattr(site.db, "world_state", {}))
            ids_in_site = [
                str(getattr(obj.db, "object_id", "") or "")
                for obj in list(getattr(site, "contents", []) or [])
            ]
            rule_ids = [str(row.get("id") or "") for row in consequence_rules()]
            check(
                "v051-persistent-install-is-idempotent-and-preserves-gameplay-state",
                second_install.get("success") is True
                and ids_in_site.count(CONTAINER_ID) == 1
                and ids_in_site.count(MANIFEST_ID) == 1
                and rule_ids.count(OPEN_RULE_ID) == 1
                and rule_ids.count(INSPECT_RULE_ID) == 1
                and current_state.get("sealed") is False
                and current_state.get("opened_count") == 1
                and current_state.get("inspected") is True
                and current_world_state.get(MANIFEST_VISIBLE_FIELD) == 1,
                f"container_count={ids_in_site.count(CONTAINER_ID)} manifest_count={ids_in_site.count(MANIFEST_ID)} open_rules={rule_ids.count(OPEN_RULE_ID)} inspect_rules={rule_ids.count(INSPECT_RULE_ID)}",
            )

            check(
                "persistent-loop-uses-routine-actions-without-inventing-resolution",
                len(action_resolution_history(actor)) == 0
                and len(object_action_history(actor)) == 2,
                f"resolution_history={len(action_resolution_history(actor))} object_history={len(object_action_history(actor))}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_history
            container.db.state = original_container_state
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
            "GAMEPLAY STATE RESTORED: actor histories/location and pre-validation object/site state restored"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: Cajon de reparto de prueba + Manifiesto de carga de prueba + v0.51 consequence rules"
        )
        self.caller.msg("========================================================")
