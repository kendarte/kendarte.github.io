import uuid

from evennia import Command

from services.action_resolution_engine import set_adventure_stat
from services.consequence_engine import get_consequence_registry
from services.knowledge_context_engine import set_knowledge_level
from services.npc_simulation import find_npc
from services.skill_engine import set_skill_level
from services.world_action_engine import (
    WORLD_ACTION_BUILD,
    available_world_actions,
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


class CmdSizaActionsV42(Command):
    """Inspect all enabled local actions and explain hard requirement blockers."""

    key = "siza-actions"
    locks = "cmd:perm(Admin)"

    def func(self):
        query = (self.args or "").strip()
        actor = find_npc(query)
        if not actor:
            self.caller.msg("Uso: siza-actions <NPC>")
            return

        rows = inspect_world_actions(actor)
        self.caller.msg(f"=== SIZA WORLD ACTIONS | {WORLD_ACTION_BUILD} ===")
        self.caller.msg(f"Actor: {actor.key} | location={actor.location.key if actor.location else None}")
        if not rows:
            self.caller.msg("  actions=NONE")

        for row in rows:
            check = row.get("check") or {}
            requirement = row.get("requirement_check") or {}
            blockers = requirement.get("blockers") or []
            blocker_text = ", ".join(
                f"{item.get('kind')}:{item.get('id')} {item.get('level')}/{item.get('required')}"
                for item in blockers
            ) or "NONE"
            self.caller.msg(
                f"  {row.get('id')} | name={row.get('name')} | eligible={row.get('eligible')} | "
                f"blockers={blocker_text} | requires_check={bool(check)} | "
                f"mode={check.get('mode')} | stat={check.get('stat')}"
            )
        self.caller.msg("===============================================")


class CmdSizaValidateV42(Command):
    """Run non-destructive v0.42 Skill/Knowledge hard requirement validation."""

    key = "siza-validate-v42"
    aliases = ["validate-v42"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.42 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        registry = get_consequence_registry(create=False)
        original_stats = _clone(getattr(actor.db, "adventure_stats", {}))
        original_skills = _clone(getattr(actor.db, "skills", {}))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_world_action_history = _clone(getattr(actor.db, "world_action_history", []))
        original_actions = _clone(getattr(site.db, "world_actions", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", [])) if registry else None
        original_log = _clone(getattr(registry.db, "action_log", [])) if registry else None

        suffix = uuid.uuid4().hex[:10]
        action_id = f"V042-REQUIRED-{suffix}"
        attempt_id = f"V042-ATTEMPT-{suffix}"
        skill_id = f"V042_SKILL_{suffix}"
        knowledge_key = f"V042_KNOWLEDGE_{suffix}"
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.42 | {WORLD_ACTION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | location={site.key}")

        try:
            actor.db.adventure_stats = {}
            actor.db.skills = {}
            actor.db.knowledge = {}
            actor.db.action_resolution_history = []
            actor.db.world_action_history = []
            set_adventure_stat(actor, "PER", 4)

            site.db.world_actions = [
                {
                    "id": action_id,
                    "name": "Accion con requisitos de prueba",
                    "enabled": True,
                    "skill_requirements": [
                        {"skill_id": skill_id, "min_level": 2, "name": "Skill de prueba v0.42"}
                    ],
                    "knowledge_requirements": [
                        {"knowledge_key": knowledge_key, "min_level": 1, "name": "Knowledge de prueba v0.42"}
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

            inspected = inspect_world_actions(actor)
            row = next((item for item in inspected if item.get("id") == action_id), {})
            blockers = row.get("requirement_check", {}).get("blockers", [])
            kinds = {item.get("kind") for item in blockers}
            check(
                "blocked-action-remains-visible-for-debug",
                row.get("eligible") is False and kinds == {"SKILL", "KNOWLEDGE"},
                f"eligible={row.get('eligible')} blockers={kinds}",
            )

            before_world_history = len(world_action_history(actor))
            before_resolution_history = len(getattr(actor.db, "action_resolution_history", []) or [])
            blocked_both = begin_world_action(actor, action_id, attempt_id=attempt_id)
            check(
                "missing-requirements-block-before-attempt",
                blocked_both.get("status") == "ACTION_REQUIREMENTS_UNMET"
                and len(world_action_history(actor)) == before_world_history
                and len(getattr(actor.db, "action_resolution_history", []) or []) == before_resolution_history,
                f"status={blocked_both.get('status')} world_history={len(world_action_history(actor))} resolution_history={len(getattr(actor.db, 'action_resolution_history', []) or [])}",
            )

            set_skill_level(actor, skill_id, 2)
            blocked_knowledge = begin_world_action(actor, action_id, attempt_id=attempt_id)
            blockers_knowledge = blocked_knowledge.get("blockers") or []
            check(
                "skill-alone-does-not-bypass-knowledge",
                blocked_knowledge.get("status") == "ACTION_REQUIREMENTS_UNMET"
                and len(blockers_knowledge) == 1
                and blockers_knowledge[0].get("kind") == "KNOWLEDGE",
                f"status={blocked_knowledge.get('status')} blockers={[(b.get('kind'), b.get('id')) for b in blockers_knowledge]}",
            )

            set_knowledge_level(actor, knowledge_key, 1)
            available_ids = {str(item.get("id") or "") for item in available_world_actions(actor)}
            check(
                "skill-plus-knowledge-makes-action-eligible",
                action_id in available_ids,
                f"available={sorted(available_ids)}",
            )

            pending = begin_world_action(actor, action_id, attempt_id=attempt_id)
            check(
                "eligible-action-then-enters-stat-check",
                pending.get("status") == "PENDING_RESOLUTION"
                and pending.get("actor_stat") == "PER"
                and pending.get("actor_stat_value") == 4
                and pending.get("difficulty") == 7,
                f"status={pending.get('status')} stat={pending.get('actor_stat_value')} difficulty={pending.get('difficulty')}",
            )

            # Prove the Skill gate is independent from the stat check after eligibility was authored.
            actor.db.world_action_history = []
            actor.db.action_resolution_history = []
            set_skill_level(actor, skill_id, 1)
            skill_low = begin_world_action(actor, action_id, attempt_id=f"{attempt_id}-LOW")
            check(
                "skill-below-minimum-blocks-even-with-stat-and-knowledge",
                skill_low.get("status") == "ACTION_REQUIREMENTS_UNMET"
                and any(item.get("kind") == "SKILL" for item in (skill_low.get("blockers") or [])),
                f"status={skill_low.get('status')} blockers={[(b.get('kind'), b.get('level'), b.get('required')) for b in (skill_low.get('blockers') or [])]}",
            )

            set_skill_level(actor, skill_id, 2)
            pending2 = begin_world_action(actor, action_id, attempt_id=f"{attempt_id}-FINAL")
            resolved = resolve_world_action(
                actor,
                f"{attempt_id}-FINAL",
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
            )
            check(
                "requirements-do-not-replace-resolution-outcome",
                pending2.get("status") == "PENDING_RESOLUTION"
                and resolved.get("status") == "RESOLVED"
                and resolved.get("outcome") == "SUCCESS",
                f"pending={pending2.get('status')} resolved={resolved.get('status')}/{resolved.get('outcome')}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            actor.db.adventure_stats = original_stats
            actor.db.skills = original_skills
            actor.db.knowledge = original_knowledge
            actor.db.action_resolution_history = original_resolution_history
            actor.db.world_action_history = original_world_action_history
            site.db.world_actions = original_actions
            if registry is not None:
                registry.db.processed_action_ids = original_processed
                registry.db.action_log = original_log

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "TEMP STATE RESTORED: stats, skills, Knowledge, action histories, room actions and consequence log restored"
        )
        self.caller.msg("========================================================")
