from evennia import default_cmds

from commands.action_resolution_commands import (
    CmdSizaCheckContract,
    CmdSizaStats,
    CmdSizaStatSet,
    CmdSizaValidateV38,
)
from commands.action_resolution_v39_commands import CmdSizaValidateV39
from commands.consequence_commands import (
    CmdSizaConsequences,
    CmdSizaConsequenceToggle,
)
from commands.context_effect_commands import (
    CmdSizaContextEffects,
    CmdSizaContextEffectToggle,
)
from commands.decision_commands import (
    CmdSizaDecide,
    CmdSizaDecisionMode,
    CmdSizaDecisionStep,
    CmdSizaGoalToggle,
)
from commands.engine_validation_commands import CmdSizaValidateEngine
from commands.event_commands import (
    CmdSizaEventRefresh,
    CmdSizaEvents,
    CmdSizaEventSet,
)
from commands.faction_commands import (
    CmdSizaFactionLoyalty,
    CmdSizaFactionMembershipToggle,
    CmdSizaFactionRank,
    CmdSizaFactions,
)
from commands.information_commands import CmdSizaInform, CmdSizaInformGoal, CmdSizaInformation
from commands.job_commands import (
    CmdSizaJobRefresh,
    CmdSizaJobRelease,
    CmdSizaJobs,
    CmdSizaJobToggle,
    CmdSizaWorkSet,
    CmdSizaWorksite,
)
from commands.knowledge_commands import (
    CmdSizaKnowledge,
    CmdSizaKnowledgeEffectToggle,
    CmdSizaKnowledgeSet,
)
from commands.need_commands import CmdSizaNeeds, CmdSizaNeedSet
from commands.object_input_v50_commands import CmdSizaNoMatchV50
from commands.order_commands import (
    CmdSizaOrderAuthority,
    CmdSizaOrderIssue,
    CmdSizaOrders,
    CmdSizaOrderToggle,
)
from commands.personality_commands import (
    CmdSizaPersonality,
    CmdSizaPersonalityToggle,
)
from commands.player_roll_v52_commands import (
    CmdSizaResetV52,
    CmdSizaRoll,
    CmdSizaSelfStatSet,
)
from commands.relationship_commands import (
    CmdSizaRelationships,
    CmdSizaRelationshipToggle,
)
from commands.skill_commands import CmdSizaSkills, CmdSizaSkillSet
from commands.siza_commands import (
    CmdSizaNPCState,
    CmdSizaSimStart,
    CmdSizaSimStatus,
    CmdSizaSimStep,
    CmdSizaSimStop,
    CmdSizaStatus,
    CmdSizaWorldCheck,
)
from commands.time_commands import (
    CmdSizaTime,
    CmdSizaTimeAdvance,
    CmdSizaTimeRate,
    CmdSizaTimeSet,
)
from commands.trace_commands import CmdSizaSimTrace
from commands.trait_commands import CmdSizaTraits, CmdSizaTraitToggle
from commands.world_action_commands import (
    CmdSizaAction,
    CmdSizaActionResolve,
    CmdSizaValidateV41,
)
from commands.world_action_v42_commands import CmdSizaActionsV42, CmdSizaValidateV42
from commands.world_action_v43_commands import CmdSizaValidateV43
from commands.world_action_v44_commands import CmdSizaValidateV44
from commands.world_action_v46_commands import CmdSizaValidateV46
from commands.world_object_v47_commands import CmdSizaValidateV47
from commands.world_object_v48_commands import CmdSizaValidateV48
from commands.world_object_v49_commands import CmdSizaValidateV49
from commands.world_object_v50_commands import CmdSizaValidateV50
from commands.world_object_v511_commands import CmdSizaResetV51, CmdSizaValidateV51Fixed
from commands.world_object_v52_commands import CmdSizaValidateV52
from commands.world_presentation_v45_commands import CmdSizaValidateV45


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(CmdSizaStatus())
        self.add(CmdSizaWorldCheck())
        self.add(CmdSizaNPCState())
        self.add(CmdSizaSimStep())
        self.add(CmdSizaSimStart())
        self.add(CmdSizaSimStop())
        self.add(CmdSizaSimStatus())
        self.add(CmdSizaSimTrace())
        self.add(CmdSizaDecide())
        self.add(CmdSizaDecisionMode())
        self.add(CmdSizaGoalToggle())
        self.add(CmdSizaDecisionStep())
        self.add(CmdSizaPersonality())
        self.add(CmdSizaPersonalityToggle())
        self.add(CmdSizaTraits())
        self.add(CmdSizaTraitToggle())
        self.add(CmdSizaSkills())
        self.add(CmdSizaSkillSet())
        self.add(CmdSizaStats())
        self.add(CmdSizaStatSet())
        self.add(CmdSizaSelfStatSet())
        self.add(CmdSizaCheckContract())
        self.add(CmdSizaValidateV38())
        self.add(CmdSizaValidateV39())
        self.add(CmdSizaValidateEngine())
        self.add(CmdSizaActionsV42())
        self.add(CmdSizaAction())
        self.add(CmdSizaActionResolve())
        self.add(CmdSizaValidateV41())
        self.add(CmdSizaValidateV42())
        self.add(CmdSizaValidateV43())
        self.add(CmdSizaValidateV44())
        self.add(CmdSizaValidateV45())
        self.add(CmdSizaValidateV46())
        self.add(CmdSizaValidateV47())
        self.add(CmdSizaValidateV48())
        self.add(CmdSizaValidateV49())
        self.add(CmdSizaValidateV50())
        self.add(CmdSizaValidateV51Fixed())
        self.add(CmdSizaResetV51())
        self.add(CmdSizaValidateV52())
        self.add(CmdSizaResetV52())
        self.add(CmdSizaInformation())
        self.add(CmdSizaInform())
        self.add(CmdSizaInformGoal())
        self.add(CmdSizaContextEffects())
        self.add(CmdSizaContextEffectToggle())
        self.add(CmdSizaConsequences())
        self.add(CmdSizaConsequenceToggle())
        self.add(CmdSizaKnowledge())
        self.add(CmdSizaKnowledgeEffectToggle())
        self.add(CmdSizaKnowledgeSet())
        self.add(CmdSizaFactions())
        self.add(CmdSizaFactionLoyalty())
        self.add(CmdSizaFactionMembershipToggle())
        self.add(CmdSizaFactionRank())
        self.add(CmdSizaOrders())
        self.add(CmdSizaOrderToggle())
        self.add(CmdSizaOrderAuthority())
        self.add(CmdSizaOrderIssue())
        self.add(CmdSizaJobs())
        self.add(CmdSizaJobToggle())
        self.add(CmdSizaJobRelease())
        self.add(CmdSizaWorksite())
        self.add(CmdSizaWorkSet())
        self.add(CmdSizaJobRefresh())
        self.add(CmdSizaNeeds())
        self.add(CmdSizaNeedSet())
        self.add(CmdSizaEvents())
        self.add(CmdSizaEventSet())
        self.add(CmdSizaEventRefresh())
        self.add(CmdSizaRelationships())
        self.add(CmdSizaRelationshipToggle())
        self.add(CmdSizaTime())
        self.add(CmdSizaTimeSet())
        self.add(CmdSizaTimeRate())
        self.add(CmdSizaTimeAdvance())
        self.add(CmdSizaRoll())
        self.add(CmdSizaNoMatchV50())


class AccountCmdSet(default_cmds.AccountCmdSet):
    key = "DefaultAccount"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()


class SessionCmdSet(default_cmds.SessionCmdSet):
    key = "DefaultSession"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
