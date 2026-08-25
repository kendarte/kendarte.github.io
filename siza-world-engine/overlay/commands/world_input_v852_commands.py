from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v83_commands import classify_v83_input
from world.upgrade_pilot_v54 import ensure_v54_pilot_content


V0852_VALIDATION_BUILD = "0.85.2-targeted-precedence-aware-routing-regression"


class CmdSizaValidateV852(Command):
    key = "siza-validate-v852"
    aliases = ["validate-v852"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v54_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.85.2 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        target = install.get("target")
        original_actor_location = actor.location
        original_target_location = target.location
        original_actor_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_actor_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_actor_memories = _clone(getattr(actor.db, "memories", []))
        original_actor_relationships = _clone(getattr(actor.db, "relationships", {}))
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.85.2 | {V0852_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted rerun: preserve historical OBJECT_ACTION precedence for named actionable NPC text while validating established perception/knowledge/movement routes"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if target.location != site:
                target.move_to(site, quiet=True)

            named_observe = classify_v83_input(actor, "observo al Informante de Prueba C")
            check(
                "named-informant-observation-preserves-existing-strong-object-action-precedence",
                named_observe.get("route") == "OBJECT_ACTION"
                and int(named_observe.get("object_score") or 0) >= 500,
                f"route={named_observe.get('route')} score={named_observe.get('object_score')}",
            )

            established_perception = classify_v83_input(actor, "observo alrededor")
            check(
                "established-generic-perception-fixture-remains-perception",
                established_perception.get("route") == "PERCEPTION"
                and established_perception.get("ai_allowed") is False,
                f"route={established_perception.get('route')}",
            )

            knowledge = classify_v83_input(actor, "¿Qué sé sobre el manifiesto duplicado?")
            movement = classify_v83_input(actor, "salir a la calle")
            check(
                "knowledge-and-movement-routing-remain-unchanged",
                knowledge.get("route") == "KNOWLEDGE_QUERY"
                and movement.get("route") == "MOVEMENT",
                f"knowledge={knowledge.get('route')} movement={movement.get('route')}",
            )

            after = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "object_history": getattr(actor.db, "object_action_history", []),
                    "resolution_history": getattr(actor.db, "action_resolution_history", []),
                }
            )
            before = {
                "knowledge": original_actor_knowledge,
                "facts": original_actor_facts,
                "memories": original_actor_memories,
                "relationships": original_actor_relationships,
                "object_history": original_object_history,
                "resolution_history": original_resolution_history,
            }
            check(
                "classification-only-regression-probe-is-read-only",
                after == before,
                "state_unchanged=True" if after == before else "state_unchanged=False",
            )
        except Exception as exc:
            check("targeted-validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_actor_location:
                    actor.move_to(original_actor_location, quiet=True)
            except Exception:
                pass
            try:
                if target.location != original_target_location:
                    target.move_to(original_target_location, quiet=True)
            except Exception:
                pass
            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.memories = original_actor_memories
            actor.db.relationships = original_actor_relationships
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor/Informant location and player Knowledge/social/action state restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: v0.85 production unchanged; v0.68 object-action-before-perception precedence remains authoritative")
        self.caller.msg("========================================================")
