from evennia import default_cmds

from commands.action_resolution_commands import CmdSizaCheckContract, CmdSizaStats, CmdSizaStatSet
from commands.consequence_commands import CmdSizaConsequences, CmdSizaConsequenceToggle
from commands.context_effect_commands import CmdSizaContextEffects, CmdSizaContextEffectToggle
from commands.decision_commands import CmdSizaDecide, CmdSizaDecisionMode, CmdSizaDecisionStep, CmdSizaGoalToggle
from commands.event_commands import CmdSizaEventRefresh, CmdSizaEvents, CmdSizaEventSet
from commands.faction_commands import CmdSizaFactionLoyalty, CmdSizaFactionMembershipToggle, CmdSizaFactionRank, CmdSizaFactions
from commands.information_commands import CmdSizaInform, CmdSizaInformGoal, CmdSizaInformation
from commands.job_commands import CmdSizaJobRefresh, CmdSizaJobRelease, CmdSizaJobs, CmdSizaJobToggle, CmdSizaWorkSet, CmdSizaWorksite
from commands.knowledge_commands import CmdSizaKnowledge, CmdSizaKnowledgeEffectToggle, CmdSizaKnowledgeSet
from commands.need_commands import CmdSizaNeeds, CmdSizaNeedSet
from commands.order_commands import CmdSizaOrderAuthority, CmdSizaOrderIssue, CmdSizaOrders, CmdSizaOrderToggle
from commands.personality_commands import CmdSizaPersonality, CmdSizaPersonalityToggle
from commands.relationship_commands import CmdSizaRelationships, CmdSizaRelationshipToggle
from commands.skill_commands import CmdSizaSkills, CmdSizaSkillSet
from commands.siza_ui_runtime_commands import CmdSizaRoomState, CmdSizaUiContext, CmdSizaUiStats
from commands.time_commands import CmdSizaTime, CmdSizaTimeAdvance, CmdSizaTimeRate, CmdSizaTimeSet
from commands.trace_commands import CmdSizaSimTrace
from commands.trait_commands import CmdSizaTraits, CmdSizaTraitToggle
from commands.travel_event_commands import CmdPokerolResolveTravelEvent, CmdPokerolTravelEvent
from commands.world_combat_bridge_commands import CmdSizaCombatBridgeClear, CmdSizaCombatBridgeStatus, CmdSizaCombatBridgeTest, CmdSizaCombatResult
from commands.pokemon_battle_commands import (
    CmdPokerolBattleAbandon,
    CmdPokerolBattleAction,
    CmdPokerolBattleCapture,
    CmdPokerolBattleMove,
    CmdPokerolBattleRun,
    CmdPokerolBattleState,
    CmdPokerolBattleTest,
    CmdPokerolPositionOptions,
)
from commands.pokemon_machine_commands import CmdPokerolEquipKnownMove, CmdPokerolMachines, CmdPokerolTeachMachine
from commands.pokemon_reaction_commands import CmdPokerolBattleReaction, CmdPokerolReactionOptions
from commands.pokemon_registry_commands import (
    CmdPokerolGivePokemon,
    CmdPokerolPokemonRegistry,
    CmdPokerolWildEncounter,
)
from commands.pokemon_trainer_commands import (
    CmdPokerolActivePokemon,
    CmdPokerolBag,
    CmdPokerolGiveItem,
    CmdPokerolParty,
    CmdPokerolTrainerTest,
)
from commands.pokerol_commands import (
    CmdPokerolNPCState,
    CmdPokerolNoMatch,
    CmdPokerolSimStart,
    CmdPokerolSimStatus,
    CmdPokerolSimStep,
    CmdPokerolSimStop,
    CmdPokerolStatus,
    CmdPokerolWorldCheck,
)
from commands.pokerol_dm_commands import CmdPokerolDMAdvance, CmdPokerolDMPlan, CmdPokerolDMSignal, CmdPokerolDMStart, CmdPokerolDMStatus
from commands.pokerol_local_login_commands import CmdPokerolLocalLogin
from commands.pokerol_roll_commands import CmdPokerolRoll


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        for command in (
            CmdPokerolStatus(), CmdPokerolWorldCheck(), CmdPokerolNPCState(),
            CmdPokerolSimStep(), CmdPokerolSimStart(), CmdPokerolSimStop(), CmdPokerolSimStatus(), CmdSizaSimTrace(),
            CmdSizaDecide(), CmdSizaDecisionMode(), CmdSizaGoalToggle(), CmdSizaDecisionStep(),
            CmdSizaPersonality(), CmdSizaPersonalityToggle(), CmdSizaTraits(), CmdSizaTraitToggle(),
            CmdSizaSkills(), CmdSizaSkillSet(), CmdSizaStats(), CmdSizaStatSet(), CmdSizaCheckContract(),
            CmdSizaInformation(), CmdSizaInform(), CmdSizaInformGoal(),
            CmdSizaContextEffects(), CmdSizaContextEffectToggle(), CmdSizaConsequences(), CmdSizaConsequenceToggle(),
            CmdSizaKnowledge(), CmdSizaKnowledgeEffectToggle(), CmdSizaKnowledgeSet(),
            CmdSizaFactions(), CmdSizaFactionLoyalty(), CmdSizaFactionMembershipToggle(), CmdSizaFactionRank(),
            CmdSizaOrders(), CmdSizaOrderToggle(), CmdSizaOrderAuthority(), CmdSizaOrderIssue(),
            CmdSizaJobs(), CmdSizaJobToggle(), CmdSizaJobRelease(), CmdSizaWorksite(), CmdSizaWorkSet(), CmdSizaJobRefresh(),
            CmdSizaNeeds(), CmdSizaNeedSet(), CmdSizaEvents(), CmdSizaEventSet(), CmdSizaEventRefresh(),
            CmdSizaRelationships(), CmdSizaRelationshipToggle(),
            CmdSizaTime(), CmdSizaTimeSet(), CmdSizaTimeRate(), CmdSizaTimeAdvance(), CmdPokerolRoll(),
            CmdPokerolTravelEvent(), CmdPokerolResolveTravelEvent(),
            CmdPokerolParty(), CmdPokerolActivePokemon(), CmdPokerolBag(), CmdPokerolGiveItem(), CmdPokerolTrainerTest(),
            CmdPokerolMachines(), CmdPokerolTeachMachine(), CmdPokerolEquipKnownMove(),
            CmdPokerolPokemonRegistry(), CmdPokerolGivePokemon(), CmdPokerolWildEncounter(),
            CmdPokerolBattleState(), CmdPokerolBattleTest(), CmdPokerolBattleAction(), CmdPokerolPositionOptions(),
            CmdPokerolReactionOptions(), CmdPokerolBattleReaction(), CmdPokerolBattleMove(),
            CmdPokerolBattleCapture(), CmdPokerolBattleRun(), CmdPokerolBattleAbandon(),
            CmdPokerolDMStart(), CmdPokerolDMStatus(), CmdPokerolDMPlan(), CmdPokerolDMSignal(), CmdPokerolDMAdvance(),
            CmdSizaRoomState(), CmdSizaUiContext(), CmdSizaUiStats(),
            CmdSizaCombatResult(), CmdSizaCombatBridgeTest(), CmdSizaCombatBridgeStatus(), CmdSizaCombatBridgeClear(),
            CmdPokerolNoMatch(),
        ):
            self.add(command)


class AccountCmdSet(default_cmds.AccountCmdSet):
    key = "DefaultAccount"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(CmdPokerolLocalLogin())


class SessionCmdSet(default_cmds.SessionCmdSet):
    key = "DefaultSession"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
