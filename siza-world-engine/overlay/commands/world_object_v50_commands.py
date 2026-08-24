import uuid

from evennia import Command, create_object

from services.action_resolution_engine import action_resolution_history, set_adventure_stat
from services.consequence_engine import get_consequence_registry, upsert_consequence_rule
from services.interaction_engine import parse_interaction_intent
from services.npc_simulation import find_npc
from services.object_action_engine import object_action_history, resolve_object_action
from services.object_action_input_engine import (
    OBJECT_ACTION_INPUT_BUILD,
    match_object_action_input,
    route_object_action_input,
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


class CmdSizaValidateV50(Command):
    """Validate real text routing into authored object actions while preserving legacy fallback behavior."""

    key = "siza-validate-v50"
    aliases = ["validate-v50"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.50 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        registry = get_consequence_registry(create=True)

        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_object_action_history = _clone(getattr(actor.db, "object_action_history", []))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_rules = _clone(getattr(registry.db, "rules", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))

        suffix = uuid.uuid4().hex[:10]
        object_id = f"V050-OBJECT-{suffix}"
        object_name = f"Contenedor v050 {suffix}"
        open_action_id = f"V050-OPEN-{suffix}"
        inspect_action_id = f"V050-INSPECT-{suffix}"
        open_rule_id = f"V050-OPEN-RULE-{suffix}"
        inspect_rule_id = f"V050-INSPECT-RULE-{suffix}"
        hidden_flag = f"v050_visible_{suffix}"
        inspect_attempt = f"V050-INSPECT-ATTEMPT-{suffix}"
        actor_id = str(actor.db.npc_id or "")
        results = []
        temp_obj = None

        open_text = f"abrir contenedor v050 {suffix}"
        inspect_text = f"registrar contenedor v050 {suffix}"

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.50 | {OBJECT_ACTION_INPUT_BUILD} ===")
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
            temp_obj.db.state = {"sealed": True, "opens": 0, "inspected": False}
            temp_obj.db.state_visibility_requirements = []
            temp_obj.db.object_actions = [
                {
                    "id": open_action_id,
                    "name": "Abrir contenedor",
                    "input_phrases": ["abrir", "desellar"],
                    "enabled": True,
                    "object_state_requirements": [
                        {
                            "field": "sealed",
                            "op": "EQ",
                            "value": True,
                            "name": "Contenedor sellado",
                        }
                    ],
                    "canon_status": "prototype",
                },
                {
                    "id": inspect_action_id,
                    "name": "Registrar contenedor",
                    "input_phrases": ["registrar", "inspeccionar"],
                    "enabled": True,
                    "object_state_requirements": [
                        {
                            "field": "sealed",
                            "op": "EQ",
                            "value": False,
                            "name": "Contenedor abierto",
                        }
                    ],
                    "check": {
                        "id": f"CHECK-{inspect_action_id}",
                        "trigger": "OBSTACLE",
                        "mode": "DIRECT",
                        "stat": "PER",
                        "difficulty": 7,
                    },
                    "canon_status": "prototype",
                },
            ]

            upsert_consequence_rule(
                {
                    "id": open_rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "EXPLICIT",
                    "recipient_ids": [actor_id],
                    "when": {
                        "action_type": "OBJECT_ACTION_COMPLETED",
                        "object_action_id": open_action_id,
                        "outcome": "COMPLETED",
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
                            "field": "opens",
                            "op": "ADD",
                            "value": 1,
                        },
                    ],
                }
            )
            upsert_consequence_rule(
                {
                    "id": inspect_rule_id,
                    "enabled": True,
                    "canon_status": "prototype",
                    "recipient_mode": "EXPLICIT",
                    "recipient_ids": [actor_id],
                    "when": {
                        "action_type": "OBJECT_ACTION_RESOLVED",
                        "object_action_id": inspect_action_id,
                        "outcome": "SUCCESS",
                    },
                    "state_effects": [
                        {
                            "scope": "ACTION_OBJECT",
                            "namespace": "state",
                            "field": "inspected",
                            "op": "SET",
                            "value": True,
                        }
                    ],
                }
            )

            matched = match_object_action_input(actor, open_text)
            generic = parse_interaction_intent(open_text) or {}
            check(
                "authored-object-input-wins-before-generic-door-intent",
                matched.get("matched") is True
                and matched.get("status") == "MATCHED"
                and matched.get("object_id") == object_id
                and matched.get("object_action_id") == open_action_id
                and generic.get("intent") == "DOOR",
                f"object_match={matched.get('status')} action={matched.get('object_action_id')} generic={generic.get('intent')}",
            )

            temp_obj.db.state_visibility_requirements = [
                {"field": hidden_flag, "op": "EQ", "value": 1, "name": "Objeto visible"}
            ]
            hidden = route_object_action_input(actor, open_text, attempt_id=f"V050-HIDDEN-{suffix}")
            check(
                "hidden-object-input-is-caught-but-not-executed",
                hidden.get("matched") is True
                and hidden.get("status") == "OBJECT_NOT_VISIBLE"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={hidden.get('status')} object_history={len(object_action_history(actor))}",
            )

            temp_obj.db.state_visibility_requirements = []
            temp_obj.db.state = {"sealed": False, "opens": 0, "inspected": False}
            blocked = route_object_action_input(actor, open_text, attempt_id=f"V050-BLOCKED-{suffix}")
            check(
                "object-state-blocked-real-input-does-not-create-history",
                blocked.get("matched") is True
                and blocked.get("status") == "OBJECT_ACTION_REQUIREMENTS_UNMET"
                and len(object_action_history(actor)) == 0
                and len(action_resolution_history(actor)) == 0,
                f"status={blocked.get('status')} object_history={len(object_action_history(actor))}",
            )

            temp_obj.db.state = {"sealed": True, "opens": 0, "inspected": False}
            opened = route_object_action_input(actor, open_text, attempt_id=f"V050-OPEN-ATTEMPT-{suffix}")
            opened_state = _plain_dict(getattr(temp_obj.db, "state", {}))
            open_result = opened.get("action_result") or {}
            open_consequence = open_result.get("action_consequence") or {}
            check(
                "routine-real-input-completes-and-mutates-action-object",
                opened.get("matched") is True
                and opened.get("status") == "COMPLETED"
                and open_result.get("outcome") == "COMPLETED"
                and open_consequence.get("status") == "PROCESSED"
                and opened_state.get("sealed") is False
                and opened_state.get("opens") == 1
                and len(object_action_history(actor)) == 1,
                f"status={opened.get('status')} consequence={open_consequence.get('status')} sealed={opened_state.get('sealed')} opens={opened_state.get('opens')}",
            )

            pending = route_object_action_input(actor, inspect_text, attempt_id=inspect_attempt)
            pending_result = pending.get("action_result") or {}
            check(
                "state-change-unlocks-followup-real-input-into-pending-resolution",
                pending.get("matched") is True
                and pending.get("status") == "PENDING_RESOLUTION"
                and pending_result.get("object_id") == object_id
                and pending_result.get("object_dbref") == int(temp_obj.id)
                and pending_result.get("actor_stat") == "PER"
                and len(object_action_history(actor)) == 2
                and len(action_resolution_history(actor)) == 1,
                f"status={pending.get('status')} stat={pending_result.get('actor_stat')} object_id={pending_result.get('object_id')}",
            )

            resolved = resolve_object_action(
                actor,
                inspect_attempt,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            resolved_state = _plain_dict(getattr(temp_obj.db, "state", {}))
            resolved_consequence = resolved.get("action_consequence") or {}
            check(
                "resolved-input-action-flows-through-consequence-engine",
                resolved.get("status") == "RESOLVED"
                and resolved.get("outcome") == "SUCCESS"
                and resolved_consequence.get("status") == "PROCESSED"
                and resolved_state.get("inspected") is True,
                f"resolved={resolved.get('status')}/{resolved.get('outcome')} consequence={resolved_consequence.get('status')} inspected={resolved_state.get('inspected')}",
            )

            fallback_match = match_object_action_input(actor, "abrir puerta de la trastienda")
            fallback_intent = parse_interaction_intent("abrir puerta de la trastienda") or {}
            check(
                "unmatched-object-input-preserves-existing-door-fallback",
                fallback_match.get("matched") is False
                and fallback_intent.get("intent") == "DOOR"
                and fallback_intent.get("action") == "open",
                f"object_matched={fallback_match.get('matched')} fallback={fallback_intent.get('intent')}/{fallback_intent.get('action')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            actor.db.adventure_stats = original_stats
            actor.db.action_resolution_history = original_resolution_history
            actor.db.object_action_history = original_object_action_history
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
