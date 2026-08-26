from evennia.utils import logger

from services.dm_campaign_director import build_dm_turn_plan, get_campaign_state, start_campaign
from services.dm_free_action_adjudicator import adjudicate_dm_free_action
from services.dm_free_action_execution_bridge import execute_adjudicated_dm_free_action
from services.dm_free_action_judge_runtime import dispatch_dm_judge_async
from services.dm_free_action_judgment_bridge import apply_dm_judgment
from services.dm_free_action_runtime import dispatch_dm_free_action_async
from services.dm_world_context import build_dm_world_snapshot
from services.player_language_contract import get_actor_turn_language, localize
from world.faro_ahogado_vertical_slice import FARO_AHOGADO_CAMPAIGN


DM_FREE_ACTION_PIPELINE_BUILD = "dm-0.1.1-single-bounded-context-retry"
MAX_CONTEXT_RETRIES = 1


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _unique_strings(values):
    output = []
    for value in list(values or []):
        text = str(value or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def _schedule_next_reactor_tick(callback):
    """Schedule a context retry outside the completed serialized provider callback."""
    from twisted.internet import reactor

    return reactor.callLater(0, callback)


def is_valid_unsupported_proposal(proposal_result):
    """Escalate only a schema-valid capability-parser UNSUPPORTED decision."""
    packet = _plain_dict(proposal_result)
    proposal = _plain_dict(packet.get("proposal"))
    return bool(
        packet.get("status") == "UNSUPPORTED"
        and packet.get("accepted") is True
        and str(proposal.get("kind") or "") == "UNSUPPORTED"
        and not str(proposal.get("capability_id") or "").strip()
    )


def _campaign_ready(actor):
    state = get_campaign_state(actor)
    wanted = str(FARO_AHOGADO_CAMPAIGN.get("id") or "")
    if not state:
        started = start_campaign(actor, FARO_AHOGADO_CAMPAIGN, force=False)
        state = _plain_dict(started.get("state")) or get_campaign_state(actor)
    if str(state.get("campaign_id") or "") != wanted:
        return {
            "status": "OTHER_CAMPAIGN_ACTIVE",
            "ready": False,
            "campaign_id": state.get("campaign_id"),
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }
    if str(state.get("status") or "") == "COMPLETED":
        return {
            "status": "CAMPAIGN_COMPLETED",
            "ready": False,
            "campaign_id": wanted,
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }
    return {
        "status": "READY",
        "ready": True,
        "campaign_id": wanted,
        "state": state,
        "build": DM_FREE_ACTION_PIPELINE_BUILD,
    }


def prepare_dm_unsupported_turn(actor, raw_player_input):
    """Snapshot authoritative context and build the non-authoritative Director plan on the reactor."""
    ready = _campaign_ready(actor)
    if not ready.get("ready"):
        return {
            "status": ready.get("status"),
            "prepared": False,
            "campaign": ready,
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }
    snapshot = build_dm_world_snapshot(actor, raw_player_input=raw_player_input)
    plan = build_dm_turn_plan(
        actor,
        FARO_AHOGADO_CAMPAIGN,
        raw_player_input,
        world_snapshot=snapshot,
    )
    if str(plan.get("status") or "") != "PLANNED":
        return {
            "status": "DIRECTOR_NOT_READY",
            "prepared": False,
            "campaign": ready,
            "snapshot": snapshot,
            "plan": plan,
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }
    return {
        "status": "PREPARED",
        "prepared": True,
        "campaign": ready,
        "snapshot": snapshot,
        "plan": plan,
        "build": DM_FREE_ACTION_PIPELINE_BUILD,
    }


def _resolution_text(outcome, language):
    value = str(outcome or "").upper().strip()
    if language == "en":
        if value in {"SUCCESS", "ACTOR_WIN"}:
            return "Your attempt succeeds."
        if value in {"FAILURE", "TARGET_WIN"}:
            return "Your attempt fails."
        if value in {"TIE", "DRAW"}:
            return "The contest ends without a clear winner."
        return "The attempt is resolved."
    if value in {"SUCCESS", "ACTOR_WIN"}:
        return "Tu intento tiene éxito."
    if value in {"FAILURE", "TARGET_WIN"}:
        return "Tu intento falla."
    if value in {"TIE", "DRAW"}:
        return "La confrontación termina sin un vencedor claro."
    return "El intento queda resuelto."


def _safe_pipeline_failure_text(actor, status):
    language = get_actor_turn_language(actor)
    value = str(status or "").upper().strip()
    if value in {"NEEDS_CONTEXT", "NOT_ADMISSIBLE", "JUDGMENT_NOT_ACCEPTED", "INVALID_JUDGMENT_MERGE"}:
        if language == "en":
            return "The world does not currently provide enough support to resolve that action."
        return "El mundo no ofrece suficiente soporte ahora mismo para resolver esa acción."
    return localize("unsupported", language)


def present_dm_execution_result(actor, execution):
    """Present only authoritative execution results and never echo model-authored outcome text."""
    packet = _plain_dict(execution)
    language = get_actor_turn_language(actor)
    if not packet.get("executed"):
        text = _safe_pipeline_failure_text(actor, packet.get("status"))
        if text:
            actor.msg("\n" + text)
        return {"presented": bool(text), "text": text, "build": DM_FREE_ACTION_PIPELINE_BUILD}

    rendered = str(packet.get("rendered_text") or "").strip()
    if rendered:
        actor.msg("\n" + rendered)
        return {"presented": True, "text": rendered, "build": DM_FREE_ACTION_PIPELINE_BUILD}

    results = [_plain_dict(row) for row in _plain_list(packet.get("results"))]
    # MOVEMENT executes the actual current Exit command and COMBAT emits its client handoff; both own presentation.
    if results and all(str(row.get("status") or "").startswith(("MOVEMENT_", "COMBAT_")) or row.get("encounter_id") for row in results):
        return {"presented": False, "text": "", "delegated": True, "build": DM_FREE_ACTION_PIPELINE_BUILD}

    outcomes = [str(row.get("outcome") or "").strip() for row in results if str(row.get("outcome") or "").strip()]
    if outcomes:
        text = _resolution_text(outcomes[-1], language)
    else:
        text = "The action is carried out." if language == "en" else "La acción se lleva a cabo."
    actor.msg("\n" + text)
    return {"presented": True, "text": text, "build": DM_FREE_ACTION_PIPELINE_BUILD}


def _execute_and_present(actor, admissible_plan, raw_player_input):
    execution = execute_adjudicated_dm_free_action(
        actor,
        admissible_plan,
        raw_player_input=raw_player_input,
    )
    presentation = present_dm_execution_result(actor, execution)
    return {
        "status": "DM_ACTION_EXECUTED" if execution.get("executed") else "DM_ACTION_EXECUTION_REJECTED",
        "handled": True,
        "execution": execution,
        "presentation": presentation,
        "build": DM_FREE_ACTION_PIPELINE_BUILD,
    }


def handle_dm_interpretation_result(
    actor,
    interpreted,
    *,
    raw_player_input,
    dm_plan,
    retry_count=0,
    context_retry_callable=None,
    judge_dispatch_callable=None,
    judge_provider_callable=None,
    judge_provider_options=None,
):
    """Deterministic middle. Context may be retrieved once; only NEEDS_JUDGMENT can invoke the bounded Judge."""
    packet = _plain_dict(interpreted)
    if packet.get("status") != "INTERPRETED" or packet.get("accepted") is not True:
        text = _safe_pipeline_failure_text(actor, packet.get("status"))
        actor.msg("\n" + text)
        return {
            "status": "DM_INTERPRETATION_REJECTED",
            "handled": True,
            "retry_count": int(retry_count or 0),
            "presentation": {"presented": True, "text": text},
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }

    adjudication = adjudicate_dm_free_action(actor, packet)
    status = str(adjudication.get("status") or "")
    if status == "ADMISSIBLE" and adjudication.get("admissible") is True:
        return _execute_and_present(actor, adjudication, raw_player_input)

    if status == "NEEDS_CONTEXT":
        needs = _unique_strings(adjudication.get("context_needs"))
        can_retry = int(retry_count or 0) < MAX_CONTEXT_RETRIES and bool(needs) and callable(context_retry_callable)
        if can_retry:
            retry = context_retry_callable(actor, needs)
            return {
                "status": "DM_CONTEXT_RETRY_QUEUED",
                "handled": True,
                "retry_count": int(retry_count or 0),
                "context_needs": needs,
                "adjudication": adjudication,
                "retry": retry,
                "build": DM_FREE_ACTION_PIPELINE_BUILD,
            }
        text = _safe_pipeline_failure_text(actor, status)
        actor.msg("\n" + text)
        return {
            "status": "NEEDS_CONTEXT",
            "handled": True,
            "retry_count": int(retry_count or 0),
            "context_needs": needs,
            "adjudication": adjudication,
            "presentation": {"presented": True, "text": text},
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }

    if status != "NEEDS_JUDGMENT":
        text = _safe_pipeline_failure_text(actor, status)
        actor.msg("\n" + text)
        return {
            "status": status or "DM_ACTION_NOT_ADMISSIBLE",
            "handled": True,
            "adjudication": adjudication,
            "presentation": {"presented": True, "text": text},
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }

    dispatch_judge = judge_dispatch_callable or dispatch_dm_judge_async

    def _judge_ok(current_actor, judge_result):
        merged = apply_dm_judgment(adjudication, judge_result)
        if merged.get("status") == "ADMISSIBLE" and merged.get("admissible") is True:
            result = _execute_and_present(current_actor, merged, raw_player_input)
            result["adjudication"] = adjudication
            result["judgment"] = _plain_dict(judge_result)
            result["execution_plan"] = merged
            return result
        text = _safe_pipeline_failure_text(current_actor, merged.get("status"))
        current_actor.msg("\n" + text)
        return {
            "status": "DM_JUDGMENT_REJECTED",
            "handled": True,
            "adjudication": adjudication,
            "judgment": _plain_dict(judge_result),
            "execution_plan": merged,
            "presentation": {"presented": True, "text": text},
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }

    def _judge_failed(current_actor, failure):
        logger.log_err(f"SIZA DM judgment pipeline failure: {failure}")
        text = _safe_pipeline_failure_text(current_actor, "JUDGE_FAILURE")
        current_actor.msg("\n" + text)
        return failure

    options = dict(judge_provider_options or {})
    return dispatch_judge(
        actor,
        raw_player_input,
        adjudication,
        dm_plan,
        on_result=_judge_ok,
        on_failure=_judge_failed,
        provider_callable=judge_provider_callable,
        **options,
    )


def dispatch_dm_unsupported_action_async(
    actor,
    raw_player_input,
    *,
    interpreter_dispatch_callable=None,
    interpreter_provider_callable=None,
    interpreter_provider_options=None,
    judge_dispatch_callable=None,
    judge_provider_callable=None,
    judge_provider_options=None,
    retry_scheduler_callable=None,
):
    """Escalate unsupported input through Director -> Interpreter -> one context retry -> Adjudicator -> Judge -> Engine."""
    prepared = prepare_dm_unsupported_turn(actor, raw_player_input)
    if not prepared.get("prepared"):
        text = _safe_pipeline_failure_text(actor, prepared.get("status"))
        actor.msg("\n" + text)
        return {
            "status": prepared.get("status") or "DM_PREPARATION_FAILED",
            "handled": True,
            "prepared": prepared,
            "presentation": {"presented": True, "text": text},
            "build": DM_FREE_ACTION_PIPELINE_BUILD,
        }

    initial_snapshot = _plain_dict(prepared.get("snapshot"))
    plan = _plain_dict(prepared.get("plan"))
    dispatch_interpreter = interpreter_dispatch_callable or dispatch_dm_free_action_async
    schedule_retry = retry_scheduler_callable or _schedule_next_reactor_tick
    interpreter_options = dict(interpreter_provider_options or {})

    def _interpreter_failed(current_actor, failure):
        logger.log_err(f"SIZA DM interpretation pipeline failure: {failure}")
        text = _safe_pipeline_failure_text(current_actor, "INTERPRETER_FAILURE")
        current_actor.msg("\n" + text)
        return failure

    def _dispatch(current_actor, snapshot, retry_count=0, context_needs=None):
        requested_needs = _unique_strings(context_needs)

        def _context_retry(retry_actor, needs):
            next_needs = _unique_strings(needs)

            def _run_retry():
                fresh_snapshot = build_dm_world_snapshot(retry_actor, raw_player_input=raw_player_input)
                return _dispatch(
                    retry_actor,
                    fresh_snapshot,
                    retry_count=int(retry_count or 0) + 1,
                    context_needs=next_needs,
                )

            scheduled = schedule_retry(_run_retry)
            return {
                "status": "SCHEDULED",
                "context_needs": next_needs,
                "retry_count": int(retry_count or 0) + 1,
                "scheduled": scheduled,
                "build": DM_FREE_ACTION_PIPELINE_BUILD,
            }

        def _interpreted(current_result_actor, result):
            return handle_dm_interpretation_result(
                current_result_actor,
                result,
                raw_player_input=raw_player_input,
                dm_plan=plan,
                retry_count=retry_count,
                context_retry_callable=_context_retry,
                judge_dispatch_callable=judge_dispatch_callable,
                judge_provider_callable=judge_provider_callable,
                judge_provider_options=judge_provider_options,
            )

        return dispatch_interpreter(
            current_actor,
            raw_player_input,
            plan,
            snapshot,
            on_result=_interpreted,
            on_failure=_interpreter_failed,
            provider_callable=interpreter_provider_callable,
            context_needs=requested_needs,
            **interpreter_options,
        )

    dispatched = _dispatch(actor, initial_snapshot, retry_count=0, context_needs=None)
    return {
        "status": "DM_PIPELINE_QUEUED",
        "handled": True,
        "prepared": prepared,
        "dispatch": dispatched,
        "max_context_retries": MAX_CONTEXT_RETRIES,
        "build": DM_FREE_ACTION_PIPELINE_BUILD,
    }
