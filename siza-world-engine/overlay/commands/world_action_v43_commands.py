import uuid

from evennia import Command

from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.npc_simulation import find_npc
from services.world_action_engine import (
    WORLD_ACTION_BUILD,
    begin_world_action,
    resolve_world_action,
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


class CmdSizaValidateV43(Command):
    """Run non-destructive v0.43 consequence-driven world-state validation."""

    key = "siza-validate-v43"
    aliases = ["validate-v43"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.43 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        registry = get_consequence_registry(create=True)
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_world_action_history = _clone(getattr(actor.db, "world_action_history", []))
        original_actions = _clone(getattr(site.db, "world_actions", []))
        original_rules = _clone(getattr(registry.db, "rules", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        suffix = uuid.uuid4().hex[:10]
        action_id = f"V043-STATE-ACTION-{suffix}"
        failure_attempt = f"V043-FAIL-{suffix}"
        success_attempt = f"V043-SUCCESS-{suffix}"
        field = f"v043_counter_{suffix}"
        success_rule_id = f"V043-STATE-SUCCESS-{suffix}"
        denied_rule_id = f"V043-STATE-DENIED-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.43 | {WORLD_ACTION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | site={site.key} | dbref=#{site.id}")

        try:
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.world_action_history = []
            site.db.world_state = {}
            set_adventure_stat(actor, "PER", 4)

            site.db.world_actions = [
                {
                    "id": action_id,
                    "name": "Accion con efecto de estado v0.43",
                    "enabled": True,
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
                    "id": success_rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "EXPLICIT",
                    "recipient_ids": [actor_id, actor_id],
                    "when": {
                        "action_type": "WORLD_ACTION_RESOLVED",
                        "world_action_id": action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_SITE",
                            "namespace": "world_state",
                            "field": field,
                            "op": "ADD",
                            "value": 1,
                        }
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
                        "action_type": "WORLD_ACTION_RESOLVED",
                        "world_action_id": action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_SITE",
                            "namespace": "arbitrary_db_namespace",
                            "field": "must_not_exist",
                            "op": "SET",
                            "value": 999,
                        }
                    ],
                }
            )

            pending_fail = begin_world_action(actor, action_id, attempt_id=failure_attempt)
            failed = resolve_world_action(
                actor,
                failure_attempt,
                "FAILURE",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            state_after_failure = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "failure-does-not-run-success-state-rule",
                pending_fail.get("status") == "PENDING_RESOLUTION"
                and failed.get("status") == "RESOLVED"
                and failed.get("outcome") == "FAILURE"
                and field not in state_after_failure,
                f"resolved={failed.get('status')}/{failed.get('outcome')} state={state_after_failure.get(field)}",
            )

            pending_success = begin_world_action(actor, action_id, attempt_id=success_attempt)
            succeeded = resolve_world_action(
                actor,
                success_attempt,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            state_after_success = _plain_dict(getattr(site.db, "world_state", {}))
            consequence = succeeded.get("action_consequence") or {}
            rule_rows = {
                str(row.get("rule_id") or ""): row
                for row in (consequence.get("results") or [])
            }
            success_row = rule_rows.get(success_rule_id) or {}
            denied_row = rule_rows.get(denied_rule_id) or {}
            success_effects = success_row.get("state_effects") or []
            denied_effects = denied_row.get("state_effects") or []

            check(
                "success-mutates-action-site-state",
                pending_success.get("status") == "PENDING_RESOLUTION"
                and succeeded.get("status") == "RESOLVED"
                and succeeded.get("outcome") == "SUCCESS"
                and state_after_success.get(field) == 1,
                f"resolved={succeeded.get('status')}/{succeeded.get('outcome')} {field}={state_after_success.get(field)}",
            )
            check(
                "state-effect-runs-once-per-rule-not-per-recipient",
                state_after_success.get(field) == 1
                and success_row.get("status") == "APPLIED"
                and len(success_effects) == 1
                and bool(success_effects[0].get("success")),
                f"recipients=2 final={state_after_success.get(field)} rule={success_row.get('status')}",
            )
            check(
                "state-effect-targets-exact-action-site-dbref",
                bool(success_effects)
                and int(success_effects[0].get("site_dbref") or 0) == int(site.id),
                f"effect_dbref={None if not success_effects else success_effects[0].get('site_dbref')} expected={site.id}",
            )
            check(
                "unauthorized-state-namespace-is-rejected",
                denied_row.get("status") == "STATE_EFFECT_FAILED"
                and len(denied_effects) == 1
                and denied_effects[0].get("success") is False
                and denied_effects[0].get("reason") == "NAMESPACE_NOT_ALLOWED"
                and getattr(site.db, "arbitrary_db_namespace", None) is None,
                f"rule={denied_row.get('status')} reason={None if not denied_effects else denied_effects[0].get('reason')}",
            )
            check(
                "resolved-action-carries-site-identity-to-consequences",
                consequence.get("status") == "PROCESSED"
                and bool(success_effects)
                and success_effects[0].get("site_room_id")
                == str(getattr(site.db, "room_id", "") or ""),
                f"consequence={consequence.get('status')} room_id={None if not success_effects else success_effects[0].get('site_room_id')}",
            )

            duplicate = resolve_world_action(
                actor,
                success_attempt,
                "FAILURE",
                "SECOND_PROVIDER",
            )
            state_after_duplicate = _plain_dict(getattr(site.db, "world_state", {}))
            check(
                "duplicate-resolution-cannot-repeat-state-effect",
                duplicate.get("status") == "ALREADY_RESOLVED"
                and state_after_duplicate.get(field) == 1,
                f"status={duplicate.get('status')} final={state_after_duplicate.get(field)}",
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

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "TEMP STATE RESTORED: stats, action histories, room actions/state and consequence registry restored"
        )
        self.caller.msg("========================================================")
