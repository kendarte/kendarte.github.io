import json

from evennia import Command

from commands.world_input_v71_commands import classify_v71_input
from commands.world_input_v72_commands import handle_action_proposal_result_v72
from services.action_intent_proposal_engine import build_action_proposal_request
from services.action_proposal_async_runtime import call_prebuilt_action_proposal
from services.action_resolution_engine import action_resolution_history
from services.object_action_engine import object_action_history
from world.upgrade_pilot_v63 import ensure_v63_pilot_content


V721_QA_BUILD = "0.72.1-targeted-semantic-movement-qa"
SEMANTIC_MOVEMENT_PHRASE = "me largo de este local hacia el exterior"
TARGET_EXIT_KEY = "salir a la calle"


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


class CmdSizaValidateV721(Command):
    key = "siza-validate-v721"
    aliases = ["validate-v721"]
    locks = "cmd:perm(Admin)"

    def func(self):
        context = ensure_v63_pilot_content()
        if not bool(context.get("success")):
            self.caller.msg(f"[V0.72.1 VALIDATION] FAIL | context={context}")
            return

        actor = self.caller
        site = context.get("destination")
        original_location = actor.location
        original_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.72.1 | {V721_QA_BUILD} ===")
        self.caller.msg("targeted rerun: semantic movement not covered by deterministic matcher -> structured proposal -> real Exit")

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)

            route = classify_v71_input(actor, SEMANTIC_MOVEMENT_PHRASE)
            check(
                "semantic-movement-fixture-really-reaches-action-proposal-route",
                route.get("route") == "AI_ACTION_PROPOSAL" and route.get("ai_allowed") is True,
                f"route={route.get('route')} phrase={SEMANTIC_MOVEMENT_PHRASE!r}",
            )

            request = build_action_proposal_request(actor, SEMANTIC_MOVEMENT_PHRASE)
            catalog = list(request.get("catalog") or [])
            movement_cap = next(
                (
                    row
                    for row in catalog
                    if row.get("kind") == "MOVEMENT" and str(row.get("label") or "") == TARGET_EXIT_KEY
                ),
                None,
            )
            destination = next(
                (
                    getattr(exit_obj, "destination", None)
                    for exit_obj in list(getattr(site, "exits", []) or [])
                    if str(exit_obj.key) == TARGET_EXIT_KEY
                ),
                None,
            )
            check(
                "target-real-exit-is-present-in-reactor-snapshot",
                movement_cap is not None and destination is not None,
                f"capability={(movement_cap or {}).get('capability_id')} destination={getattr(destination, 'key', None)}",
            )
            if not movement_cap or not destination:
                raise RuntimeError("target movement capability missing")

            self.caller.msg(
                f"LIVE V0721 TARGETED MOVEMENT PROBE: action={SEMANTIC_MOVEMENT_PHRASE!r} target={TARGET_EXIT_KEY!r}"
            )
            live = call_prebuilt_action_proposal(request, timeout=60)
            proposal = dict(live.get("proposal") or {})
            check(
                "live-qwen-maps-true-fallback-phrase-to-real-movement-capability",
                live.get("status") == "ACCEPTED"
                and live.get("accepted") is True
                and proposal.get("kind") == "MOVEMENT"
                and proposal.get("capability_id") == movement_cap.get("capability_id")
                and float(proposal.get("confidence") or 0) >= 0.90,
                f"status={live.get('status')} proposal={proposal}",
            )

            before_obj = len(object_action_history(actor))
            before_res = len(action_resolution_history(actor))
            handled = handle_action_proposal_result_v72(actor, live, emit_messages=False)
            check(
                "true-fallback-proposal-traverses-real-exit-without-action-history-or-model-prose",
                handled.get("status") == "MOVEMENT_EXECUTED"
                and handled.get("executed") is True
                and actor.location == destination
                and len(object_action_history(actor)) == before_obj
                and len(action_resolution_history(actor)) == before_res
                and _clone(getattr(actor.db, "knowledge", {})) == original_knowledge
                and _clone(getattr(actor.db, "knowledge_facts", [])) == original_facts
                and str(proposal.get("reason") or "") not in json.dumps(handled, ensure_ascii=False),
                f"handler={handled.get('status')} location={actor.location.key if actor.location else None}",
            )

            self.caller.msg("--- LIVE V0721 TARGETED RESULT ---")
            self.caller.msg(
                json.dumps(
                    {
                        "proposal": proposal,
                        "handler_status": handled.get("status"),
                        "bridge_status": (handled.get("bridge") or {}).get("status"),
                        "exit_key": (handled.get("bridge") or {}).get("exit_key"),
                        "destination": (handled.get("bridge") or {}).get("destination_name"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            self.caller.msg("--- END LIVE V0721 TARGETED RESULT ---")

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_location:
                    actor.move_to(original_location, quiet=True)
            except Exception:
                pass
            actor.db.object_action_history = original_object_history
            actor.db.action_resolution_history = original_resolution_history
            actor.db.knowledge = original_knowledge
            actor.db.knowledge_facts = original_facts

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("STATE RESTORED: actor location/action histories/Knowledge/Facts restored exactly")
        self.caller.msg("PERSISTENT SYSTEM RETAINED: v0.72 production movement bridge unchanged; only the failed semantic-fallback assumption is retested")
        self.caller.msg("========================================================")
