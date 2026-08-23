from evennia import default_cmds

from commands.decision_commands import (
    CmdSizaDecide,
    CmdSizaDecisionMode,
    CmdSizaDecisionStep,
    CmdSizaGoalToggle,
)
from commands.job_commands import (
    CmdSizaJobRefresh,
    CmdSizaJobRelease,
    CmdSizaJobs,
    CmdSizaJobToggle,
    CmdSizaWorkSet,
    CmdSizaWorksite,
)
from commands.need_commands import CmdSizaNeeds, CmdSizaNeedSet
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
        self.add(CmdSizaJobs())
        self.add(CmdSizaJobToggle())
        self.add(CmdSizaJobRelease())
        self.add(CmdSizaWorksite())
        self.add(CmdSizaWorkSet())
        self.add(CmdSizaJobRefresh())
        self.add(CmdSizaNeeds())
        self.add(CmdSizaNeedSet())
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
