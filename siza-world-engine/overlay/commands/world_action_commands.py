import uuid

from evennia import Command

from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry
from services.npc_simulation import find_npc, find_room
from services.world_action_engine import (
    WORLD_ACTION_BUILD,
    available_world_actions,
    begin_world_action,
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


class CmdSizaActions(Command):
    """Inspect authored world actions available at an actor's current location."""

    key = "siza-actions"
    locks = "cmd:perm(Admin)"

    def func(self):
        query = (self.args or "").strip()
        actor = find_npc(query)
        if not actor:
            self.caller.msg("Uso: siza-actions <NPC>")
            return
        rows = available_world_actions(actor)
        self.caller.msg(f"=== SIZA WORLD ACTIONS | {WORLD_ACTION_BUILD} ===")
        self.caller.msg(f"Actor: {actor.key} | location={actor.location.key if actor.location else None}")
        if not rows:
            self.caller.msg("  actions=NONE")
        for row in rows:
            check = row.get("check") or {}
            self.caller.msg(
                f"  {row.get('id')} | name={row.get('name')} | "
                f"requires_check={bool(check)} | mode={check.get('mode')} | stat={check.get('stat')}"
            )
        self.caller.msg("===============================================")


class CmdSizaAction(Command):
    """Admin/debug: start one authored local world action for an NPC."""

    key = "siza-action"
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|")]
        if len(parts) != 2 or not all(parts):
            self.caller.msg("Uso: siza-action <NPC> | <ACTION_ID>")
            return
        actor = find_npc(parts[0])
        if not actor:
            self.caller.msg("No identifico ese NPC.")
            return
        packet = begin_world_action(actor, parts[1])
        self.caller.msg(
            f"[WORLD ACTION] actor={actor.key} | action={parts[1]} | "
            f"attempt={packet.get('attempt_id')} | status={packet.get('status')} | "
            f"resolution={packet.get('resolution_id')}"
        )


class CmdSizaActionResolve(Command):
    """Admin/debug: submit an explicit provider outcome for a pending world action."""

    key = "siza-action-resolve"
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|")]
        if len(parts) != 4 or not all(parts):
            self.caller.msg(
                "Uso: siza-action-resolve <NPC> | <ATTEMPT_ID> | <OUTCOME> | <PROVIDER>"
            )
            return
        actor = find_npc(parts[0])
        if not actor:
            self.caller.msg("No identifico ese NPC.")
            return
        packet = resolve_world_action(actor, parts[1], parts[2], parts[3])
        self.caller.msg(
            f"[WORLD ACTION RESOLVE] actor={actor.key} | attempt={parts[1]} | "
            f"status={packet.get('status')} | outcome={packet.get('outcome')} | "
            f"provider={packet.get('provider')}"
        )


class CmdSizaValidateV41(Command):
    """Run the complete non-destructive v0.41 generic action pipeline validation."""

    key = "siza-validate-v41"
    aliases = ["validate-v41"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.41 VALIDATION] FAIL | Informante C/location missing")
            return

        local_site = actor.location
        plaza = find_room("Plaza de Recepcion", "CAR-KAL-DAR-003")
        pescaderia = find_room("Pescaderia de Darsena", "CAR-KAL-DAR-007")
        remote_site = pescaderia if local_site != pescaderia else plaza
        if not remote_site or remote_site == local_site:
            self.caller.msg("[V0.41 VALIDATION] FAIL | no distinct remote room")
            return

        registry = get_consequence_registry(create=False)
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_world_action_history = _clone(getattr(actor.db, "world_action_history", []))
        original_local_actions = _clone(getattr(local_site.db, "world_actions", []))
        original_remote_actions = _clone(getattr(remote_site.db, "world_actions", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", [])) if registry else None
        original_log = _clone(getattr(registry.db, "action_log", [])) if registry else None

        suffix = uuid.uuid4().hex[:10]
        immediate_id = f"V041-IMMEDIATE-{suffix}"
        checked_id = f"V041-CHECKED-{suffix}"
        remote_id = f"V041-REMOTE-{suffix}"
        immediate_attempt = f"V041-ATTEMPT-IMMEDIATE-{suffix}"
        checked_attempt = f"V041-ATTEMPT-CHECKED-{suffix}"
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            suffix_text = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{suffix_text}")

        self.caller.msg(f"=== SIZA VALIDATION v0.41 | {WORLD_ACTION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | local={local_site.key} | remote={remote_site.key}")

        try:
            actor.db.adventure_stats = {}
            actor.db.action_resolution_history = []
            actor.db.world_action_history = []
            set_adventure_stat(actor, "PER", 4)

            local_site.db.world_actions = [
                {
                    "id": immediate_id,
                    "name": "Accion inmediata de prueba",
                    "enabled": True,
                    "activity": "ejecutando una accion cotidiana de prueba",
                    "canon_status": "prototype",
                },
                {
                    "id": checked_id,
                    "name": "Inspeccion con obstaculo de prueba",
                    "enabled": True,
                    "activity": "inspeccionando un obstaculo de prueba",
                    "check": {
                        "id": f"CHECK-{checked_id}",
                        "trigger": "OBSTACLE",
                        "mode": "DIRECT",
                        "stat": "PER",
                        "difficulty": 7,
                    },
                    "canon_status": "prototype",
                },
            ]
            remote_site.db.world_actions = [
                {
                    "id": remote_id,
                    "name": "Accion remota que no debe estar disponible",
                    "enabled": True,
                    "canon_status": "prototype",
                }
            ]

            available_ids = {str(row.get("id") or "") for row in available_world_actions(actor)}
            check(
                "actions-are-authored-and-location-scoped",
                immediate_id in available_ids and checked_id in available_ids and remote_id not in available_ids,
                f"available={sorted(available_ids)}",
            )

            immediate = begin_world_action(
                actor,
                immediate_id,
                attempt_id=immediate_attempt,
            )
            immediate_consequence = immediate.get("action_consequence") or {}
            check(
                "no-check-action-completes-immediately",
                immediate.get("status") == "COMPLETED"
                and immediate.get("resolved") is True
                and immediate.get("outcome") == "COMPLETED"
                and immediate.get("resolution_id") is None,
                f"status={immediate.get('status')} outcome={immediate.get('outcome')}",
            )
            check(
                "immediate-action-emits-world-consequence-action",
                immediate_consequence.get("status") == "PROCESSED",
                f"consequence={immediate_consequence.get('status')}",
            )

            pending = begin_world_action(
                actor,
                checked_id,
                attempt_id=checked_attempt,
            )
            check(
                "checked-action-enters-pending-resolution",
                pending.get("status") == "PENDING_RESOLUTION"
                and pending.get("resolved") is False
                and pending.get("actor_stat") == "PER"
                and pending.get("actor_stat_value") == 4
                and pending.get("difficulty") == 7
                and bool(pending.get("resolution_id")),
                f"status={pending.get('status')} stat={pending.get('actor_stat_value')} difficulty={pending.get('difficulty')}",
            )

            invalid = resolve_world_action(
                actor,
                checked_attempt,
                "ACTOR_WIN",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            pending_after_invalid = next(
                (row for row in world_action_history(actor) if row.get("attempt_id") == checked_attempt),
                {},
            )
            check(
                "invalid-outcome-does-not-complete-world-action",
                invalid.get("status") == "INVALID_OUTCOME"
                and pending_after_invalid.get("status") == "PENDING_RESOLUTION"
                and pending_after_invalid.get("resolved") is False,
                f"result={invalid.get('status')} stored={pending_after_invalid.get('status')}",
            )

            resolved = resolve_world_action(
                actor,
                checked_attempt,
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
                resolution_data={"validator": True},
            )
            resolved_consequence = resolved.get("action_consequence") or {}
            check(
                "external-provider-resolves-world-action",
                resolved.get("status") == "RESOLVED"
                and resolved.get("resolved") is True
                and resolved.get("outcome") == "SUCCESS"
                and resolved.get("provider") == "VALIDATOR_EXTERNAL_PROVIDER",
                f"status={resolved.get('status')} outcome={resolved.get('outcome')} provider={resolved.get('provider')}",
            )
            check(
                "resolved-action-emits-world-consequence-action",
                resolved_consequence.get("status") == "PROCESSED",
                f"consequence={resolved_consequence.get('status')}",
            )

            duplicate = resolve_world_action(
                actor,
                checked_attempt,
                "FAILURE",
                "SECOND_PROVIDER",
            )
            check(
                "resolved-world-action-cannot-be-overwritten",
                duplicate.get("status") == "ALREADY_RESOLVED"
                and duplicate.get("outcome") == "SUCCESS",
                f"status={duplicate.get('status')} outcome={duplicate.get('outcome')}",
            )

            history = world_action_history(actor)
            immediate_stored = next(
                (row for row in history if row.get("attempt_id") == immediate_attempt),
                {},
            )
            checked_stored = next(
                (row for row in history if row.get("attempt_id") == checked_attempt),
                {},
            )
            check(
                "world-action-history-persists-both-paths",
                immediate_stored.get("status") == "COMPLETED"
                and checked_stored.get("status") == "RESOLVED"
                and checked_stored.get("outcome") == "SUCCESS",
                f"immediate={immediate_stored.get('status')} checked={checked_stored.get('status')}/{checked_stored.get('outcome')}",
            )
        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            actor.db.adventure_stats = original_stats
            actor.db.action_resolution_history = original_resolution_history
            actor.db.world_action_history = original_world_action_history
            local_site.db.world_actions = original_local_actions
            remote_site.db.world_actions = original_remote_actions
            if registry is not None:
                registry.db.processed_action_ids = original_processed
                registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "TEMP STATE RESTORED: stats, action histories, room actions and consequence log restored"
        )
        self.caller.msg("========================================================")
