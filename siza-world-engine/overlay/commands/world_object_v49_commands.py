import uuid

from evennia import Command, create_object

from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.npc_simulation import find_npc
from services.object_action_engine import (
    begin_object_action,
    inspect_object_actions,
    object_action_history,
    resolve_object_action,
)
from services.state_effect_engine import STATE_EFFECT_BUILD


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


class CmdSizaValidateV49(Command):
    """Validate safe consequence-driven mutation of the exact action object's persistent state."""

    key = "siza-validate-v49"
    aliases = ["validate-v49"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.49 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        registry = get_consequence_registry(create=True)

        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_action_history = _clone(getattr(actor.db, "object_action_history", []))
        original_rules = _clone(getattr(registry.db, "rules", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        suffix = uuid.uuid4().hex[:10]
        object_id = f"V049-OBJECT-{suffix}"
        decoy_id = f"V049-DECOY-{suffix}"
        open_action_id = f"V049-OPEN-{suffix}"
        followup_action_id = f"V049-SEARCH-{suffix}"
        success_rule_id = f"V049-OBJECT-STATE-{suffix}"
        denied_rule_id = f"V049-DENIED-NAMESPACE-{suffix}"
        redirect_rule_id = f"V049-DENIED-REDIRECT-{suffix}"
        failure_attempt = f"V049-FAIL-{suffix}"
        success_attempt = f"V049-SUCCESS-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []
        temp_obj = None
        decoy = None

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.49 | {STATE_EFFECT_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | site={site.key} | dbref=#{site.id}")

        try:
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.object_action_history = []
            set_adventure_stat(actor, "PER", 4)

            temp_obj = create_object(
                "typeclasses.siza_objects.WorldObject",
                key=f"Contenedor de Prueba v0.49 {suffix}",
                location=site,
            )
            temp_obj.db.object_id = object_id
            temp_obj.db.state = {"sealed": True, "transitions": 0}
            temp_obj.db.object_actions = [
                {
                    "id": open_action_id,
                    "name": "Romper sello de prueba v0.49",
                    "enabled": True,
                    "object_state_requirements": [
                        {
                            "field": "sealed",
                            "op": "EQ",
                            "value": True,
                            "name": "Contenedor sellado",
                        }
                    ],
                    "check": {
                        "id": f"CHECK-{open_action_id}",
                        "trigger": "OBSTACLE",
                        "mode": "DIRECT",
                        "stat": "PER",
                        "difficulty": 7,
                    },
                    "canon_status": "prototype",
                },
                {
                    "id": followup_action_id,
                    "name": "Registrar interior de prueba v0.49",
                    "enabled": True,
                    "object_state_requirements": [
                        {
                            "field": "sealed",
                            "op": "EQ",
                            "value": False,
                            "name": "Contenedor sin sello",
                        }
                    ],
                    "canon_status": "prototype",
                },
            ]

            decoy = create_object(
                "typeclasses.siza_objects.WorldObject",
                key=f"Objeto Senuelo v0.49 {suffix}",
                location=site,
            )
            decoy.db.object_id = decoy_id
            decoy.db.state = {"sealed": True, "compromised": False}

            upsert_consequence_rule(
                {
                    "id": success_rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "EXPLICIT",
                    "recipient_ids": [actor_id],
                    "when": {
                        "action_type": "OBJECT_ACTION_RESOLVED",
                        "object_action_id": open_action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_OBJECT",
                            "namespace": "state",
                            "field": "sealed",
                            "op": "SET",
                            "value": False,
                        },
                        {
                            "scope": "ACTION_OBJECT",
                            "namespace": "state",
                            "field": "transitions",
                            "op": "ADD",
                            "value": 1,
                        },
                    ],
                }
            )
            upsert_consequence_rule(
                {
                    "id": denied_rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "ACTION_RECIPIENTS",
                    "when": {
                        "action_type": "OBJECT_ACTION_RESOLVED",
                        "object_action_id": open_action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_OBJECT",
                            "namespace": "world_state",
                            "field": "must_not_exist",
                            "op": "SET",
                            "value": 999,
                        }
                    ],
                }
            )
            upsert_consequence_rule(
                {
                    "id": redirect_rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "ACTION_RECIPIENTS",
                    "when": {
                        "action_type": "OBJECT_ACTION_RESOLVED",
                        "object_action_id": open_action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_OBJECT",
                            "namespace": "state",
                            "object_dbref": int(decoy.id),
                            "field": "compromised",
                            "op": "SET",
                            "value": True,
                        }
                    ],
                }
            )

            pending_fail = begin_object_action(
                actor,
                temp_obj,
                open_action_id,
                attempt_id=failure_attempt,
            )
            failed = resolve_object_action(
                actor,
                failure_attempt,
                "FAILURE",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            state_after_failure = _plain_dict(getattr(temp_obj.db, "state", {}))
            check(
                "failure-does-not-mutate-action-object-state",
                pending_fail.get("status") == "PENDING_RESOLUTION"
                and failed.get("status") == "RESOLVED"
                and failed.get("outcome") == "FAILURE"
                and state_after_failure.get("sealed") is True
                and state_after_failure.get("transitions") == 0,
                f"resolved={failed.get('status')}/{failed.get('outcome')} sealed={state_after_failure.get('sealed')} transitions={state_after_failure.get('transitions')}",
            )

            pending_success = begin_object_action(
                actor,
                temp_obj,
                open_action_id,
                attempt_id=success_attempt,
            )
            succeeded = resolve_object_action(
                actor,
                success_attempt,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            state_after_success = _plain_dict(getattr(temp_obj.db, "state", {}))
            consequence = succeeded.get("action_consequence") or {}
            rule_rows = {
                str(row.get("rule_id") or ""): row
                for row in (consequence.get("results") or [])
            }
            success_row = rule_rows.get(success_rule_id) or {}
            denied_row = rule_rows.get(denied_rule_id) or {}
            redirect_row = rule_rows.get(redirect_rule_id) or {}
            success_effects = success_row.get("state_effects") or []
            denied_effects = denied_row.get("state_effects") or []
            redirect_effects = redirect_row.get("state_effects") or []

            check(
                "success-mutates-exact-action-object-state",
                pending_success.get("status") == "PENDING_RESOLUTION"
                and succeeded.get("status") == "RESOLVED"
                and succeeded.get("outcome") == "SUCCESS"
                and success_row.get("status") == "APPLIED"
                and state_after_success.get("sealed") is False
                and state_after_success.get("transitions") == 1,
                f"resolved={succeeded.get('status')}/{succeeded.get('outcome')} sealed={state_after_success.get('sealed')} transitions={state_after_success.get('transitions')}",
            )

            exact_effect = next(
                (row for row in success_effects if str(row.get("field") or "") == "sealed"),
                None,
            )
            check(
                "object-state-effect-targets-exact-action-object-identity",
                exact_effect is not None
                and exact_effect.get("success") is True
                and int(exact_effect.get("object_dbref") or 0) == int(temp_obj.id)
                and str(exact_effect.get("object_id") or "") == object_id,
                f"effect_dbref={None if exact_effect is None else exact_effect.get('object_dbref')} expected={temp_obj.id} object_id={None if exact_effect is None else exact_effect.get('object_id')}",
            )

            followup = next(
                (
                    row
                    for row in inspect_object_actions(actor, temp_obj)
                    if str(row.get("id") or "") == followup_action_id
                ),
                None,
            )
            check(
                "object-state-mutation-dynamically-unlocks-followup-action",
                followup is not None and followup.get("eligible") is True,
                f"eligible={None if followup is None else followup.get('eligible')} sealed={state_after_success.get('sealed')}",
            )

            check(
                "action-object-rejects-unauthorized-namespace",
                denied_row.get("status") == "STATE_EFFECT_FAILED"
                and len(denied_effects) == 1
                and denied_effects[0].get("success") is False
                and denied_effects[0].get("reason") == "NAMESPACE_NOT_ALLOWED"
                and getattr(temp_obj.db, "world_state", None) is None,
                f"rule={denied_row.get('status')} reason={None if not denied_effects else denied_effects[0].get('reason')}",
            )

            decoy_state = _plain_dict(getattr(decoy.db, "state", {}))
            check(
                "action-object-effect-cannot-redirect-to-another-dbref",
                redirect_row.get("status") == "STATE_EFFECT_FAILED"
                and len(redirect_effects) == 1
                and redirect_effects[0].get("success") is False
                and redirect_effects[0].get("reason") == "OBJECT_DBREF_MISMATCH"
                and decoy_state.get("compromised") is False,
                f"rule={redirect_row.get('status')} reason={None if not redirect_effects else redirect_effects[0].get('reason')} decoy={decoy_state.get('compromised')}",
            )

            duplicate = resolve_object_action(
                actor,
                success_attempt,
                "FAILURE",
                "SECOND_PROVIDER",
            )
            state_after_duplicate = _plain_dict(getattr(temp_obj.db, "state", {}))
            check(
                "duplicate-resolution-cannot-repeat-object-state-effect",
                duplicate.get("status") == "ALREADY_RESOLVED"
                and state_after_duplicate.get("sealed") is False
                and state_after_duplicate.get("transitions") == 1
                and len(object_action_history(actor)) == 2,
                f"status={duplicate.get('status')} sealed={state_after_duplicate.get('sealed')} transitions={state_after_duplicate.get('transitions')} history={len(object_action_history(actor))}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            actor.db.adventure_stats = original_stats
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_action_history
            registry.db.rules = original_rules
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log
            if temp_obj:
                try:
                    temp_obj.delete()
                except Exception:
                    pass
            if decoy:
                try:
                    decoy.delete()
                except Exception:
                    pass

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "TEMP STATE RESTORED: stats, resolution/object-action histories and consequence registry restored; temporary world objects deleted"
        )
        self.caller.msg("========================================================")
