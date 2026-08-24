import uuid

from evennia import Command, create_object

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.npc_simulation import find_npc
from services.object_action_engine import (
    OBJECT_ACTION_BUILD,
    begin_object_action,
    inspect_object_actions,
    object_action_history,
    resolve_object_action,
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


def _restore_attribute(obj, key, had_value, value):
    if had_value:
        setattr(obj.db, key, value)
        return
    try:
        obj.attributes.remove(key)
    except Exception:
        setattr(obj.db, key, None)


class CmdSizaValidateV48(Command):
    """Validate authored persistent object actions without leaving test state."""

    key = "siza-validate-v48"
    aliases = ["validate-v48"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.48 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        registry = get_consequence_registry(create=True)

        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        had_object_history = bool(actor.attributes.has("object_action_history"))
        original_object_history = _clone(getattr(actor.db, "object_action_history", None))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_rules = _clone(getattr(registry.db, "rules", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        suffix = uuid.uuid4().hex[:10]
        object_id = f"V048-OBJECT-{suffix}"
        object_name = f"Contenedor de Prueba v0.48 {suffix}"
        action_id = f"V048-OBJECT-ACTION-{suffix}"
        attempt_id = f"V048-ATTEMPT-{suffix}"
        hidden_flag = f"v048_object_visible_{suffix}"
        consequence_flag = f"v048_interaction_resolved_{suffix}"
        rule_id = f"V048-CONSEQUENCE-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []
        temp_obj = None

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.48 | {OBJECT_ACTION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | site={site.key} | dbref=#{site.id}")

        try:
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            site.db.world_state = {}
            set_adventure_stat(actor, "PER", 4)

            temp_obj = create_object(
                "typeclasses.siza_objects.WorldObject",
                key=object_name,
                location=site,
            )
            temp_obj.db.object_id = object_id
            temp_obj.db.state = {"sealed": True}
            temp_obj.db.state_visibility_requirements = []
            temp_obj.db.object_actions = [
                {
                    "id": action_id,
                    "name": "Registrar contenedor de prueba v0.48",
                    "enabled": True,
                    "object_state_requirements": [
                        {
                            "field": "sealed",
                            "op": "EQ",
                            "value": False,
                            "name": "Contenedor sin sello",
                        }
                    ],
                    "check": {
                        "id": f"CHECK-{action_id}",
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
                        "action_type": "OBJECT_ACTION_RESOLVED",
                        "object_action_id": action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_SITE",
                            "namespace": "world_state",
                            "field": consequence_flag,
                            "op": "SET",
                            "value": 1,
                        }
                    ],
                }
            )

            initial_rows = inspect_object_actions(actor, temp_obj)
            initial = next((row for row in initial_rows if row.get("id") == action_id), None)
            object_blocker = next(
                (row for row in ((initial or {}).get("blockers") or []) if row.get("kind") == "OBJECT_STATE"),
                None,
            )
            check(
                "object-state-gated-action-remains-visible-for-debug",
                initial is not None
                and initial.get("eligible") is False
                and object_blocker is not None
                and object_blocker.get("id") == "sealed"
                and object_blocker.get("current") is True
                and object_blocker.get("required") is False,
                f"eligible={None if initial is None else initial.get('eligible')} blocker={object_blocker}",
            )

            blocked = begin_object_action(actor, temp_obj, action_id, attempt_id=f"V048-BLOCKED-{suffix}")
            check(
                "unmet-object-state-blocks-before-attempt",
                blocked.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={blocked.get('status')} object_history={len(object_action_history(actor))} resolution_history={len(action_resolution_history(actor))}",
            )

            temp_obj.db.state = {"sealed": False}
            temp_obj.db.state_visibility_requirements = [
                {"field": hidden_flag, "op": "EQ", "value": 1, "name": "Objeto visible"}
            ]
            hidden_attempt = begin_object_action(
                actor,
                temp_obj,
                action_id,
                attempt_id=f"V048-HIDDEN-{suffix}",
            )
            check(
                "hidden-object-cannot-be-interacted-with",
                hidden_attempt.get("status") == "OBJECT_NOT_VISIBLE"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={hidden_attempt.get('status')} object_history={len(object_action_history(actor))}",
            )

            temp_obj.db.state_visibility_requirements = []
            unlocked = next(
                (row for row in inspect_object_actions(actor, temp_obj) if row.get("id") == action_id),
                None,
            )
            check(
                "matching-object-state-unlocks-authored-object-action",
                unlocked is not None
                and unlocked.get("eligible") is True
                and unlocked.get("local") is True
                and unlocked.get("visible") is True,
                f"eligible={None if unlocked is None else unlocked.get('eligible')} local={None if unlocked is None else unlocked.get('local')} visible={None if unlocked is None else unlocked.get('visible')}",
            )

            pending = begin_object_action(actor, temp_obj, action_id, attempt_id=attempt_id)
            check(
                "object-action-enters-normal-stat-resolution-with-object-identity",
                pending.get("status") == "PENDING_RESOLUTION"
                and pending.get("actor_stat") == "PER"
                and pending.get("object_id") == object_id
                and pending.get("object_dbref") == int(temp_obj.id)
                and len(object_action_history(actor)) == 1
                and len(action_resolution_history(actor)) == 1,
                f"status={pending.get('status')} stat={pending.get('actor_stat')} object_id={pending.get('object_id')} dbref={pending.get('object_dbref')}",
            )

            resolved = resolve_object_action(
                actor,
                attempt_id,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            world_state = _plain_dict(getattr(site.db, "world_state", {}))
            consequence = _plain_dict(resolved.get("action_consequence"))
            check(
                "resolved-object-action-flows-through-existing-consequence-engine",
                resolved.get("status") == "RESOLVED"
                and resolved.get("outcome") == "SUCCESS"
                and resolved.get("object_id") == object_id
                and world_state.get(consequence_flag) == 1
                and consequence.get("status") == "PROCESSED",
                f"resolved={resolved.get('status')}/{resolved.get('outcome')} consequence={consequence.get('status')} {consequence_flag}={world_state.get(consequence_flag)}",
            )

            duplicate = resolve_object_action(
                actor,
                attempt_id,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            final_state = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "duplicate-object-resolution-cannot-repeat-consequence",
                duplicate.get("status") == "ALREADY_RESOLVED"
                and final_state.get(consequence_flag) == 1
                and len(object_action_history(actor)) == 1,
                f"status={duplicate.get('status')} final={final_state.get(consequence_flag)} object_history={len(object_action_history(actor))}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            actor.db.adventure_stats = original_stats
            actor.db.action_resolution_history = original_resolution_history
            _restore_attribute(actor, "object_action_history", had_object_history, original_object_history)
            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    site.db.world_state = None
            registry.db.rules = original_rules
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log
            if temp_obj:
                try:
                    temp_obj.delete()
                except Exception:
                    pass

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "TEMP STATE RESTORED: stats, resolution/object-action histories, room state and consequence registry restored; temporary world object deleted"
        )
        self.caller.msg("========================================================")
