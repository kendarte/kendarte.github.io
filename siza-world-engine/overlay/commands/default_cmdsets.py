from evennia import default_cmds

from commands.decision_commands import (
    CmdSizaDecide,
    CmdSizaDecisionMode,
    CmdSizaDecisionStep,
    CmdSizaGoalToggle,
)
from commands.job_commands import CmdSizaJobs, CmdSizaJobToggle
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
        self.add(CmdSizaDecide())
        self.add(CmdSizaDecisionMode())
        self.add(CmdSizaGoalToggle())
        self.add(CmdSizaDecisionStep())
        self.add(CmdSizaJobs())
        self.add(CmdSizaJobToggle())
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
