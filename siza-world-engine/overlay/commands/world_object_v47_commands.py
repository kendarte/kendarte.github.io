import uuid

from evennia import Command, create_object

from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.npc_simulation import find_npc
from services.object_visibility_engine import OBJECT_VISIBILITY_BUILD, inspect_object_visibility
from services.world_action_engine import begin_world_action, resolve_world_action


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


class CmdSizaValidateV47(Command):
    """Validate consequence-driven persistent world-object visibility without leaving test state."""

    key = "siza-validate-v47"
    aliases = ["validate-v47"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.47 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        registry = get_consequence_registry(create=True)

        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_world_action_history = _clone(getattr(actor.db, "world_action_history", []))
        original_actions = _clone(getattr(site.db, "world_actions", []))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_rules = _clone(getattr(registry.db, "rules", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        suffix = uuid.uuid4().hex[:10]
        flag = f"v047_object_revealed_{suffix}"
        object_id = f"V047-OBJECT-{suffix}"
        object_name = f"Objeto de Prueba v0.47 {suffix}"
        prerequisite_id = f"V047-PREREQUISITE-{suffix}"
        rule_id = f"V047-REVEAL-OBJECT-{suffix}"
        fail_attempt = f"V047-FAIL-{suffix}"
        success_attempt = f"V047-SUCCESS-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []
        temp_obj = None

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.47 | {OBJECT_VISIBILITY_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | site={site.key} | dbref=#{site.id}")

        try:
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.world_action_history = []
            site.db.world_state = {}
            set_adventure_stat(actor, "PER", 4)

            temp_obj = create_object(
                "typeclasses.siza_objects.WorldObject",
                key=object_name,
                location=site,
            )
            temp_obj.db.object_id = object_id
            temp_obj.db.canon_status = "prototype"
            temp_obj.db.state_visibility_requirements = [
                {
                    "field": flag,
                    "op": "EQ",
                    "value": 1,
                    "name": "Objeto revelado",
                }
            ]
            original_dbref = int(temp_obj.id)

            site.db.world_actions = [
                {
                    "id": prerequisite_id,
                    "name": "Revelar objeto de prueba v0.47",
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

            initial = inspect_object_visibility(temp_obj, site=site)
            initial_appearance = site.return_appearance(actor)
            check(
                "state-gated-object-remains-persistently-located-while-hidden",
                initial.get("visible") is False
                and temp_obj.location == site
                and int(temp_obj.id) == original_dbref,
                f"visible={initial.get('visible')} location={temp_obj.location.key if temp_obj.location else None} dbref={temp_obj.id}",
            )

            check(
                "unmet-world-state-hides-object-from-real-room-look",
                object_name not in initial_appearance,
                f"visible_in_look={object_name in initial_appearance}",
            )

            pending_fail = begin_world_action(actor, prerequisite_id, attempt_id=fail_attempt)
            failed = resolve_world_action(
                actor,
                fail_attempt,
                "FAILURE",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            after_fail = inspect_object_visibility(temp_obj, site=site)
            after_fail_appearance = site.return_appearance(actor)
            check(
                "failed-prerequisite-does-not-reveal-object",
                pending_fail.get("status") == "PENDING_RESOLUTION"
                and failed.get("status") == "RESOLVED"
                and failed.get("outcome") == "FAILURE"
                and flag not in _plain_dict(getattr(site.db, "world_state", {}))
                and after_fail.get("visible") is False
                and object_name not in after_fail_appearance,
                f"resolved={failed.get('status')}/{failed.get('outcome')} visible={after_fail.get('visible')}",
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
                "successful-prerequisite-mutates-object-visibility-world-state",
                pending_success.get("status") == "PENDING_RESOLUTION"
                and succeeded.get("status") == "RESOLVED"
                and succeeded.get("outcome") == "SUCCESS"
                and state_after_success.get(flag) == 1,
                f"resolved={succeeded.get('status')}/{succeeded.get('outcome')} {flag}={state_after_success.get(flag)}",
            )

            revealed = inspect_object_visibility(temp_obj, site=site)
            revealed_appearance = site.return_appearance(actor)
            check(
                "matching-world-state-reveals-object-in-real-room-look",
                revealed.get("visible") is True and object_name in revealed_appearance,
                f"visible={revealed.get('visible')} visible_in_look={object_name in revealed_appearance}",
            )

            check(
                "reveal-preserves-object-identity-and-location",
                int(temp_obj.id) == original_dbref
                and temp_obj.location == site
                and str(temp_obj.db.object_id or "") == object_id,
                f"dbref={temp_obj.id} location={temp_obj.location.key if temp_obj.location else None} object_id={temp_obj.db.object_id}",
            )

            site.db.world_state = {}
            relocked = inspect_object_visibility(temp_obj, site=site)
            relocked_appearance = site.return_appearance(actor)
            check(
                "object-visibility-is-live-and-rehides-without-deletion",
                relocked.get("visible") is False
                and object_name not in relocked_appearance
                and temp_obj.location == site
                and int(temp_obj.id) == original_dbref,
                f"visible={relocked.get('visible')} visible_in_look={object_name in relocked_appearance} location={temp_obj.location.key if temp_obj.location else None}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
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
            "TEMP STATE RESTORED: stats, action histories, room state/actions, consequence registry restored; temporary world object deleted"
        )
        self.caller.msg("========================================================")
