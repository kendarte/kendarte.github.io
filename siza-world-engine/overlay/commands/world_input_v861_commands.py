from evennia.utils import logger

from commands.world_combat_bridge_commands import _decode_result_token
from commands.world_input_v82_commands import present_conversation_result_v82
from commands.world_input_v83_commands import classify_v83_input
from commands.world_input_v84_commands import _current_interaction_capability
from commands.world_input_v85_commands import CmdSizaNoMatchV85, handle_action_proposal_result_v85
from services.active_perception_proposal_runtime import dispatch_active_perception_proposal_async
from services.action_resolution_engine import adventure_stats
from services.interaction_engine import parse_interaction_intent
from services.player_language_contract import get_actor_turn_language, localize, resolve_turn_language
from services.ranked_fact_conversation_engine import (
    RANKED_FACT_CONVERSATION_BUILD,
    resolve_ranked_talk_with_disclosure_and_acquisition,
)
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent
from services.world_combat_handoff_engine import (
    WORLD_COMBAT_HANDOFF_BUILD,
    accept_world_combat_result,
    build_world_combat_encounter,
    clear_pending_world_combat,
    emit_world_combat_encounter,
)


NATURAL_RANKED_FACT_TALK_BUILD = "0.86.1-ranked-single-fact-talk-authority"
COMBAT_RESULT_PREFIX = "siza-combat-result "
COMBAT_TEST_PREFIX = "siza-combat-test "
COMBAT_CLEAR_COMMAND = "siza-combat-clear"
UI_STATS_COMMAND = "siza-ui-stats"


def _is_admin(actor):
    if not actor:
        return False
    if bool(getattr(actor, "is_superuser", False)):
        return True
    try:
        return bool(actor.permissions.check("Admin"))
    except Exception:
        return False


def _handle_reserved_combat_input(actor, raw):
    """Handle browser/QA bridge messages before any natural-language or AI routing."""
    value = str(raw or "").strip()
    lowered = value.lower()

    if lowered == UI_STATS_COMMAND:
        stats = adventure_stats(actor)
        actor.msg(
            siza_character_stats=(
                ({
                    "stats": {key: stats.get(key) for key in ("FUE", "AGI", "COO", "INT", "PER", "PSI")},
                    "authored_count": sum(1 for value in stats.values() if value is not None),
                },),
                {},
            )
        )
        return True

    if lowered.startswith(COMBAT_RESULT_PREFIX):
        token = value[len(COMBAT_RESULT_PREFIX):].strip()
        decoded = _decode_result_token(token)
        if not decoded.get("accepted"):
            actor.msg(f"Combat result rechazado: {decoded.get('status')}")
            return True
        accepted = accept_world_combat_result(actor, decoded.get("result"))
        if not accepted.get("accepted"):
            actor.msg(f"Combat result rechazado: {accepted.get('status')}")
            return True
        actor.msg(
            siza_combat_result_accepted=(
                ({
                    "encounter_id": accepted.get("encounter_id"),
                    "outcome": accepted.get("outcome"),
                    "world_consequences_applied": False,
                    "bridge_build": WORLD_COMBAT_HANDOFF_BUILD,
                },),
                {},
            )
        )
        return True

    if lowered == COMBAT_CLEAR_COMMAND:
        if not _is_admin(actor):
            actor.msg("No tienes permiso para limpiar el bridge de combate.")
            return True
        clear_pending_world_combat(actor)
        actor.msg("TCG bridge: pending encounter eliminado.")
        return True

    if lowered.startswith(COMBAT_TEST_PREFIX):
        if not _is_admin(actor):
            actor.msg("No tienes permiso para lanzar el handoff de prueba.")
            return True
        target_name = value[len(COMBAT_TEST_PREFIX):].strip()
        if not target_name:
            actor.msg("Uso: siza-combat-test <NPC local>")
            return True
        target = actor.search(target_name, location=actor.location)
        if not target:
            return True
        if target is actor or getattr(target, "destination", None):
            actor.msg("El objetivo debe ser un personaje local.")
            return True
        if not bool(getattr(target.db, "is_npc", False)):
            actor.msg("El objetivo de esta prueba debe tener is_npc=True.")
            return True
        packet = build_world_combat_encounter(
            actor,
            target,
            source_action_id=f"QA:{WORLD_COMBAT_HANDOFF_BUILD}",
        )
        if not packet.get("accepted"):
            actor.msg(f"Combat handoff rechazado: {packet.get('status')}")
            return True
        emitted = emit_world_combat_encounter(actor, packet.get("encounter"))
        if not emitted.get("accepted"):
            actor.msg(f"Combat handoff no emitido: {emitted.get('status')}")
            return True
        actor.msg(f"Combat handoff enviado al cliente: {emitted.get('encounter_id')}")
        return True

    return False


def handle_action_proposal_result_v861(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    emit_messages=True,
    render_async_callable=None,
    provider_options=None,
):
    """For ordinary TALK, bind disclosure and transfer to one ranked fact_id. All other routes stay on v0.85."""
    if parse_semantic_fact_inform_intent(raw_player_input):
        return handle_action_proposal_result_v85(
            actor,
            proposal_result,
            raw_player_input=raw_player_input,
            emit_messages=emit_messages,
            render_async_callable=render_async_callable,
            provider_options=provider_options,
        )

    current = _current_interaction_capability(actor, proposal_result)
    if current:
        packet = resolve_ranked_talk_with_disclosure_and_acquisition(
            actor,
            raw_player_input,
            expected_target_dbref=current.get("target_dbref"),
        )
        packet = {**dict(packet or {}), "build": NATURAL_RANKED_FACT_TALK_BUILD}
        return present_conversation_result_v82(
            actor,
            packet,
            emit_messages=emit_messages,
            render_async_callable=render_async_callable,
            provider_options=provider_options,
        )

    return handle_action_proposal_result_v85(
        actor,
        proposal_result,
        raw_player_input=raw_player_input,
        emit_messages=emit_messages,
        render_async_callable=render_async_callable,
        provider_options=provider_options,
    )


def _proposal_failure(actor, failure):
    logger.log_err(f"SIZA v0.86.1 action proposal runtime failure: {failure}")
    actor.msg("\n" + localize("unsupported", get_actor_turn_language(actor)))
    return failure


def dispatch_unknown_action_v861(actor, raw, **provider_options):
    def _handle(current_actor, proposal_result):
        return handle_action_proposal_result_v861(
            current_actor,
            proposal_result,
            raw_player_input=raw,
            emit_messages=True,
            provider_options=provider_options,
        )

    return dispatch_active_perception_proposal_async(
        actor,
        raw,
        on_result=_handle,
        on_failure=_proposal_failure,
        **provider_options,
    )


class CmdSizaNoMatchV861(CmdSizaNoMatchV85):
    key = "__nomatch_command"
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        if _handle_reserved_combat_input(self.caller, raw):
            return None

        # One language decision per natural-language player turn. Downstream renderers read this contract.
        resolve_turn_language(self.caller, raw)

        classification = classify_v83_input(self.caller, raw)
        if classification.get("route") == "INTERACTION" and classification.get("explicit_talk_precedence"):
            packet = resolve_ranked_talk_with_disclosure_and_acquisition(
                self.caller,
                raw,
            )
            present_conversation_result_v82(self.caller, packet, emit_messages=True)
            return None
        if classification.get("route") == "AI_ACTION_PROPOSAL":
            dispatch_unknown_action_v861(self.caller, raw)
            return None
        return super().func()
