import uuid

from evennia import Command

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.exit_state_gate_engine import EXIT_STATE_GATE_BUILD, inspect_exit_state
from services.npc_simulation import find_npc
from services.world_action_engine import begin_world_action, resolve_world_action, world_action_history


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


def _real_exit_from(site):
    try:
        exits = list(site.exits or [])
    except Exception:
        exits = []
    if not exits:
        try:
            exits = [obj for obj in list(site.contents or []) if getattr(obj, "destination", None)]
        except Exception:
            exits = []
    return next((obj for obj in exits if getattr(obj, "destination", None)), None)


def _restore_attribute(obj, key, had_value, value):
    if had_value:
        setattr(obj.db, key, value)
        return
    try:
        obj.attributes.remove(key)
    except Exception:
        setattr(obj.db, key, None)


class CmdSizaValidateV46(Command):
    """Validate consequence-driven persistent exit gates without leaving test state."""

    key = "siza-validate-v46"
    aliases = ["validate-v46"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.46 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        exit_obj = _real_exit_from(site)
        if not exit_obj or not exit_obj.destination:
            self.caller.msg("[V0.46 VALIDATION] FAIL | persistent source exit/destination missing")
            return

        destination = exit_obj.destination
        registry = get_consequence_registry(create=True)

        original_location = actor.location
        original_narration = _clone(getattr(actor.db, "siza_narration", None))
        had_narration = bool(actor.attributes.has("siza_narration"))
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_world_action_history = _clone(getattr(actor.db, "world_action_history", []))
        original_actions = _clone(getattr(site.db, "world_actions", []))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))

        had_exit_requirements = bool(exit_obj.attributes.has("state_requirements"))
        original_exit_requirements = _clone(getattr(exit_obj.db, "state_requirements", None))
        had_exit_message = bool(exit_obj.attributes.has("state_block_message"))
        original_exit_message = _clone(getattr(exit_obj.db, "state_block_message", None))
        original_door_state = _clone(getattr(exit_obj.db, "door_state", None))
        original_is_locked = _clone(getattr(exit_obj.db, "is_locked", None))

        original_rules = _clone(getattr(registry.db, "rules", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        suffix = uuid.uuid4().hex[:10]
        flag = f"v046_route_open_{suffix}"
        prerequisite_id = f"V046-PREREQUISITE-{suffix}"
        rule_id = f"V046-OPEN-ROUTE-{suffix}"
        fail_attempt = f"V046-FAIL-{suffix}"
        success_attempt = f"V046-SUCCESS-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.46 | {EXIT_STATE_GATE_BUILD} ===")
        self.caller.msg(
            f"Harness NPC: {actor.key} | site={site.key} | exit={exit_obj.key} -> {destination.key}"
        )

        try:
            actor.db.siza_narration = False
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.world_action_history = []
            site.db.world_state = {}
            set_adventure_stat(actor, "PER", 4)

            exit_obj.db.door_state = "open"
            exit_obj.db.is_locked = False
            exit_obj.db.state_block_message = "La ruta de prueba v0.46 aun no esta habilitada."
            exit_obj.db.state_requirements = [
                {
                    "field": flag,
                    "op": "EQ",
                    "value": 1,
                    "name": "Ruta habilitada",
                }
            ]

            site.db.world_actions = [
                {
                    "id": prerequisite_id,
                    "name": "Habilitar ruta de prueba v0.46",
                    "enabled": True,
                    "check": {
                        "id": f"CHECK-{prerequisite_id}",
                        "trigger": "OBSTACLE",
                        "mode": "DIRECT",
                        "stat": "PER",
                        "difficulty": 7,
                    },
                    "canon_status": "prototype",
                }
            ]

            upsert_consequence_rule(
                {
                    "id": rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "EXPLICIT",
                    "recipient_ids": [actor_id],
                    "when": {
                        "action_type": "WORLD_ACTION_RESOLVED",
                        "world_action_id": prerequisite_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_SITE",
                            "namespace": "world_state",
                            "field": flag,
                            "op": "SET",
                            "value": 1,
                        }
                    ],
                }
            )

            initial = inspect_exit_state(exit_obj)
            blocker = next(iter(initial.get("blockers") or []), None)
            check(
                "real-persistent-exit-carries-live-state-gate",
                initial.get("eligible") is False
                and blocker is not None
                and blocker.get("field") == flag
                and initial.get("source_dbref") == int(site.id),
                f"eligible={initial.get('eligible')} blocker={blocker} source_dbref={initial.get('source_dbref')}",
            )

            blocked_result = exit_obj.at_traverse(actor, destination)
            check(
                "unmet-world-state-blocks-real-traverse-before-move",
                blocked_result is False and actor.location == site,
                f"result={blocked_result} location={actor.location.key if actor.location else None}",
            )

            pending_fail = begin_world_action(actor, prerequisite_id, attempt_id=fail_attempt)
            failed = resolve_world_action(
                actor,
                fail_attempt,
                "FAILURE",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            after_fail_state = _plain_dict(getattr(site.db, "world_state", {}))
            after_fail_gate = inspect_exit_state(exit_obj)
            fail_traverse = exit_obj.at_traverse(actor, destination)
            check(
                "failed-prerequisite-does-not-open-route",
                pending_fail.get("status") == "PENDING_RESOLUTION"
                and failed.get("status") == "RESOLVED"
                and failed.get("outcome") == "FAILURE"
                and flag not in after_fail_state
                and after_fail_gate.get("eligible") is False
                and fail_traverse is False
                and actor.location == site,
                f"resolved={failed.get('status')}/{failed.get('outcome')} eligible={after_fail_gate.get('eligible')}",
            )

            pending_success = begin_world_action(actor, prerequisite_id, attempt_id=success_attempt)
            succeeded = resolve_world_action(
                actor,
                success_attempt,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            state_after_success = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "successful-prerequisite-mutates-route-world-state",
                pending_success.get("status") == "PENDING_RESOLUTION"
                and succeeded.get("status") == "RESOLVED"
                and succeeded.get("outcome") == "SUCCESS"
                and state_after_success.get(flag) == 1,
                f"resolved={succeeded.get('status')}/{succeeded.get('outcome')} {flag}={state_after_success.get(flag)}",
            )

            open_gate = inspect_exit_state(exit_obj)
            exit_obj.at_traverse(actor, destination)
            check(
                "matching-world-state-opens-real-route-and-traverses",
                open_gate.get("eligible") is True and actor.location == destination,
                f"eligible={open_gate.get('eligible')} location={actor.location.key if actor.location else None}",
            )

            actor.move_to(site, quiet=True)
            exit_obj.db.is_locked = True
            locked_result = exit_obj.at_traverse(actor, destination)
            check(
                "physical-lock-remains-authoritative-after-state-gate-passes",
                inspect_exit_state(exit_obj).get("eligible") is True
                and locked_result is False
                and actor.location == site,
                f"state_gate={inspect_exit_state(exit_obj).get('eligible')} locked={exit_obj.db.is_locked} location={actor.location.key if actor.location else None}",
            )

            exit_obj.db.is_locked = False
            site.db.world_state = {}
            relocked_gate = inspect_exit_state(exit_obj)
            relocked_result = exit_obj.at_traverse(actor, destination)
            check(
                "exit-gate-is-live-and-relocks-when-world-state-no-longer-matches",
                relocked_gate.get("eligible") is False
                and relocked_result is False
                and actor.location == site,
                f"eligible={relocked_gate.get('eligible')} location={actor.location.key if actor.location else None}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            _restore_attribute(actor, "siza_narration", had_narration, original_narration)
            actor.db.adventure_stats = original_stats
            actor.db.action_resolution_history = original_resolution_history
            actor.db.world_action_history = original_world_action_history
            site.db.world_actions = original_actions
            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    site.db.world_state = None
            _restore_attribute(
                exit_obj,
                "state_requirements",
                had_exit_requirements,
                original_exit_requirements,
            )
            _restore_attribute(
                exit_obj,
                "state_block_message",
                had_exit_message,
                original_exit_message,
            )
            exit_obj.db.door_state = original_door_state
            exit_obj.db.is_locked = original_is_locked
            registry.db.rules = original_rules
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "TEMP STATE RESTORED: actor location/narration, exit gate/door state, stats, action histories, room state/actions and consequence registry restored"
        )
        self.caller.msg("========================================================")
