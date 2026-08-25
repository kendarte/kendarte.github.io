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
    CmdSizaSelfStatClear,
    CmdSizaSelfStatSet,
)
from commands.player_roll_v53_commands import (
    CmdSizaResetV53,
    CmdSizaSelfStatRestore,
    CmdSizaSelfStatTemp,
)
from commands.player_roll_v54_commands import CmdSizaResetV54
from commands.player_roll_v55_commands import CmdSizaResetV55, CmdSizaRollV55
from commands.qa_commands import CmdSizaQALatest
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
from commands.world_input_v83_commands import CmdSizaNoMatchV83
from commands.world_object_v47_commands import CmdSizaValidateV47
from commands.world_object_v48_commands import CmdSizaValidateV48
from commands.world_object_v49_commands import CmdSizaValidateV49
from commands.world_object_v50_commands import CmdSizaValidateV50
from commands.world_object_v511_commands import CmdSizaResetV51, CmdSizaValidateV51Fixed
from commands.world_object_v52_commands import CmdSizaValidateV52
from commands.world_object_v53_commands import CmdSizaValidateV53
from commands.world_object_v531_commands import CmdSizaValidateV531
from commands.world_object_v54_commands import CmdSizaValidateV54
from commands.world_object_v55_commands import CmdSizaValidateV55
from commands.world_object_v56_commands import CmdSizaResetV56, CmdSizaValidateV56
from commands.world_object_v57_commands import (
    CmdSizaMyKnowledgeV57,
    CmdSizaResetV57,
    CmdSizaValidateV57,
)
from commands.world_object_v58_commands import (
    CmdSizaNPCFactsV58,
    CmdSizaResetV58,
    CmdSizaShareFactV58,
    CmdSizaSharePilotFactV58,
    CmdSizaValidateV58,
)
from commands.world_object_v59_commands import (
    CmdSizaFactGoalsV59,
    CmdSizaResetV59,
    CmdSizaValidateV59,
)
from commands.world_object_v60_commands import (
    CmdSizaFactCompletionsV60,
    CmdSizaResetV60,
    CmdSizaValidateV60,
)
from commands.world_object_v61_commands import CmdSizaResetV61, CmdSizaValidateV61
from commands.world_object_v62_commands import (
    CmdSizaResetV62,
    CmdSizaV62ManifestState,
    CmdSizaValidateV62,
)
from commands.world_object_v63_commands import (
    CmdSizaResetV63,
    CmdSizaV63Fact,
    CmdSizaValidateV63,
)
from commands.world_object_v64_commands import CmdSizaFactContextV64, CmdSizaValidateV64
from commands.world_object_v65_commands import CmdSizaNarrationContextV65, CmdSizaValidateV65
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
        self.add(CmdSizaSelfStatClear())
        self.add(CmdSizaSelfStatTemp())
        self.add(CmdSizaSelfStatRestore())
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
        self.add(CmdSizaValidateV53())
        self.add(CmdSizaValidateV531())
        self.add(CmdSizaResetV53())
        self.add(CmdSizaValidateV54())
        self.add(CmdSizaResetV54())
        self.add(CmdSizaValidateV55())
        self.add(CmdSizaResetV55())
        self.add(CmdSizaValidateV56())
        self.add(CmdSizaResetV56())
        self.add(CmdSizaValidateV57())
        self.add(CmdSizaResetV57())
        self.add(CmdSizaValidateV58())
        self.add(CmdSizaResetV58())
        self.add(CmdSizaValidateV59())
        self.add(CmdSizaResetV59())
        self.add(CmdSizaFactGoalsV59())
        self.add(CmdSizaValidateV60())
        self.add(CmdSizaResetV60())
        self.add(CmdSizaFactCompletionsV60())
        self.add(CmdSizaValidateV61())
        self.add(CmdSizaResetV61())
        self.add(CmdSizaValidateV62())
        self.add(CmdSizaResetV62())
        self.add(CmdSizaV62ManifestState())
        self.add(CmdSizaValidateV63())
        self.add(CmdSizaResetV63())
        self.add(CmdSizaV63Fact())
        self.add(CmdSizaValidateV64())
        self.add(CmdSizaFactContextV64())
        self.add(CmdSizaValidateV65())
        self.add(CmdSizaNarrationContextV65())
        self.add(CmdSizaQALatest())
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
        self.add(CmdSizaMyKnowledgeV57())
        self.add(CmdSizaNPCFactsV58())
        self.add(CmdSizaShareFactV58())
        self.add(CmdSizaSharePilotFactV58())
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
        self.add(CmdSizaRollV55())
        self.add(CmdSizaNoMatchV83())


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
