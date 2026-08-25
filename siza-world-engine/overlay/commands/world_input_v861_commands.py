from evennia.utils import logger

from commands.world_input_v82_commands import present_conversation_result_v82
from commands.world_input_v83_commands import classify_v83_input
from commands.world_input_v84_commands import _current_interaction_capability
from commands.world_input_v85_commands import CmdSizaNoMatchV85, handle_action_proposal_result_v85
from services.action_proposal_async_runtime import DEFAULT_ACTION_FAILURE_TEXT
from services.active_perception_proposal_runtime import dispatch_active_perception_proposal_async
from services.interaction_engine import parse_interaction_intent
from services.ranked_fact_conversation_engine import (
    RANKED_FACT_CONVERSATION_BUILD,
    resolve_ranked_talk_with_disclosure_and_acquisition,
)
from services.semantic_fact_inform_engine import parse_semantic_fact_inform_intent


NATURAL_RANKED_FACT_TALK_BUILD = "0.86.1-ranked-single-fact-talk-authority"


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
    actor.msg("\n" + DEFAULT_ACTION_FAILURE_TEXT)
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
