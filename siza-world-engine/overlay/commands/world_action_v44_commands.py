import uuid

from evennia import Command

from services.action_requirement_engine import ACTION_REQUIREMENT_BUILD
from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.npc_simulation import find_npc
from services.world_action_engine import (
    begin_world_action,
    inspect_world_actions,
    resolve_world_action,
    world_action_history,
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


class CmdSizaValidateV44(Command):
    """Validate dynamic world_state eligibility gates without leaving persistent test state."""

    key = "siza-validate-v44"
    aliases = ["validate-v44"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.44 VALIDATION] FAIL | Informante C/location missing")
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
        flag = f"v044_access_{suffix}"
        prerequisite_id = f"V044-PREREQUISITE-{suffix}"
        dependent_id = f"V044-DEPENDENT-{suffix}"
        rule_id = f"V044-UNLOCK-RULE-{suffix}"
        fail_attempt = f"V044-FAIL-{suffix}"
        success_attempt = f"V044-SUCCESS-{suffix}"
        dependent_attempt = f"V044-DEPENDENT-ATTEMPT-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.44 | {ACTION_REQUIREMENT_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | site={site.key} | dbref=#{site.id}")

        try:
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.world_action_history = []
            site.db.world_state = {}
            set_adventure_stat(actor, "PER", 4)

            site.db.world_actions = [
                {
                    "id": prerequisite_id,
                    "name": "Abrir acceso de prueba v0.44",
                    "enabled": True,
                    "check": {
                        "id": f"CHECK-{prerequisite_id}",
                        "trigger": "OBSTACLE",
                        "mode": "DIRECT",
                        "stat": "PER",
                        "difficulty": 7,
                    },
                    "canon_status": "prototype",
                },
                {
                    "id": dependent_id,
                    "name": "Usar acceso abierto v0.44",
                    "enabled": True,
                    "state_requirements": [
                        {
                            "field": flag,
                            "op": "EQ",
                            "value": 1,
                            "name": "Acceso abierto",
                        }
                    ],
                    "canon_status": "prototype",
                },
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

            initial_rows = inspect_world_actions(actor)
            initial_dep = next(
                (row for row in initial_rows if str(row.get("id") or "") == dependent_id),
                None,
            )
            blockers = ((initial_dep or {}).get("requirement_check") or {}).get("blockers") or []
            state_blocker = next(
                (row for row in blockers if str(row.get("kind") or "") == "STATE"),
                None,
            )
            check(
                "state-gated-action-remains-visible-while-blocked",
                initial_dep is not None
                and initial_dep.get("eligible") is False
                and state_blocker is not None
                and state_blocker.get("id") == flag
                and state_blocker.get("required") == 1,
                f"eligible={None if initial_dep is None else initial_dep.get('eligible')} blocker={state_blocker}",
            )

            blocked = begin_world_action(actor, dependent_id, attempt_id=f"V044-BLOCKED-{suffix}")
            check(
                "unmet-world-state-blocks-before-attempt",
                blocked.get("status") == "ACTION_REQUIREMENTS_UNMET"
                and len(world_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={blocked.get('status')} world_history={len(world_action_history(actor))} resolution_history={len(action_resolution_history(actor))}",
            )

            pending_fail = begin_world_action(actor, prerequisite_id, attempt_id=fail_attempt)
            failed = resolve_world_action(
                actor,
                fail_attempt,
                "FAILURE",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            after_fail = next(
                (
                    row
                    for row in inspect_world_actions(actor)
                    if str(row.get("id") or "") == dependent_id
                ),
                None,
            )
            check(
                "failed-prerequisite-does-not-unlock-dependent-action",
                pending_fail.get("status") == "PENDING_RESOLUTION"
                and failed.get("status") == "RESOLVED"
                and failed.get("outcome") == "FAILURE"
                and flag not in _plain_dict(getattr(site.db, "world_state", {}))
                and after_fail is not None
                and after_fail.get("eligible") is False,
                f"resolved={failed.get('status')}/{failed.get('outcome')} eligible={None if after_fail is None else after_fail.get('eligible')}",
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
                "successful-prerequisite-mutates-required-world-state",
                pending_success.get("status") == "PENDING_RESOLUTION"
                and succeeded.get("status") == "RESOLVED"
                and succeeded.get("outcome") == "SUCCESS"
                and state_after_success.get(flag) == 1,
                f"resolved={succeeded.get('status')}/{succeeded.get('outcome')} {flag}={state_after_success.get(flag)}",
            )

            unlocked_rows = inspect_world_actions(actor)
            unlocked_dep = next(
                (row for row in unlocked_rows if str(row.get("id") or "") == dependent_id),
                None,
            )
            state_checks = ((unlocked_dep or {}).get("requirement_check") or {}).get("state_checks") or []
            check(
                "world-state-change-dynamically-unlocks-dependent-action",
                unlocked_dep is not None
                and unlocked_dep.get("eligible") is True
                and len(state_checks) == 1
                and state_checks[0].get("met") is True
                and state_checks[0].get("current") == 1,
                f"eligible={None if unlocked_dep is None else unlocked_dep.get('eligible')} state={None if not state_checks else state_checks[0].get('current')}",
            )

            dependent = begin_world_action(actor, dependent_id, attempt_id=dependent_attempt)
            check(
                "newly-unlocked-action-executes-through-normal-world-action-path",
                dependent.get("status") == "COMPLETED"
                and dependent.get("resolved") is True
                and dependent.get("outcome") == "COMPLETED",
                f"status={dependent.get('status')} outcome={dependent.get('outcome')}",
            )

            site.db.world_state = {}
            relocked = next(
                (
                    row
                    for row in inspect_world_actions(actor)
                    if str(row.get("id") or "") == dependent_id
                ),
                None,
            )
            check(
                "eligibility-is-live-and-relocks-when-world-state-no-longer-matches",
                relocked is not None and relocked.get("eligible") is False,
                f"eligible={None if relocked is None else relocked.get('eligible')}",
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
