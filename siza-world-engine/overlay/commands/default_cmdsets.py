from evennia import default_cmds

from commands.action_resolution_commands import (
    CmdSizaCheckContract,
    CmdSizaStats,
    CmdSizaStatSet,
)
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
from commands.relationship_commands import (
    CmdSizaRelationships,
    CmdSizaRelationshipToggle,
)
from commands.skill_commands import CmdSizaSkills, CmdSizaSkillSet
from commands.siza_commands import (
    CmdSizaNoMatch,
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
        self.add(CmdSizaCheckContract())
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
        self.add(CmdSizaNoMatch())


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
