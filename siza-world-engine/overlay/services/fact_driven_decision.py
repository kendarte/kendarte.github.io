from services.fact_goal_completion_engine import (
    FACT_GOAL_COMPLETION_BUILD,
    apply_goal_completion_effects,
)
from services.fact_goal_engine import FACT_GOAL_BUILD, refresh_fact_driven_goals
from services.npc_decision import (
    choose_goal as _choose_goal,
    decision_step as _decision_step,
    set_goal_active,
)


FACT_DRIVEN_DECISION_BUILD = "0.59.0-fact-driven-decision-wrapper"
FACT_DRIVEN_COMPLETION_BUILD = "0.60.0-fact-driven-completion-dispatch"


def choose_goal(npc):
    refresh = refresh_fact_driven_goals(npc)
    packet = dict(_choose_goal(npc) or {})
    packet["fact_goal_refresh"] = refresh
    packet["fact_driven_build"] = FACT_DRIVEN_DECISION_BUILD
    packet["fact_driven_completion_build"] = FACT_DRIVEN_COMPLETION_BUILD
    return packet


def decision_step(npc, prepare_world_state=True):
    refresh = refresh_fact_driven_goals(npc)
    packet = dict(_decision_step(npc, prepare_world_state=prepare_world_state) or {})
    completion = apply_goal_completion_effects(npc, packet)
    packet["fact_goal_refresh"] = refresh
    packet["fact_goal_build"] = FACT_GOAL_BUILD
    packet["fact_goal_completion"] = completion
    packet["fact_goal_completion_build"] = FACT_GOAL_COMPLETION_BUILD
    packet["fact_driven_build"] = FACT_DRIVEN_DECISION_BUILD
    packet["fact_driven_completion_build"] = FACT_DRIVEN_COMPLETION_BUILD
    return packet
