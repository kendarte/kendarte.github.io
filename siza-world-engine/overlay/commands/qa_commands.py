from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v1011_commands import CmdSizaValidateV1011
from services.knowledge_context_engine import (
    FACT_STATUS_ACTIVE,
    FACT_STATUS_RETRACTED,
    set_knowledge_level,
)
from services.knowledge_fact_engine import (
    find_knowledge_fact,
    set_knowledge_fact_status,
    upsert_knowledge_fact,
)


QA_BUILD = "1.01.1-targeted-risk-based-one-command-qa"
MANUAL_BACKUP_ATTR = "v101_manual_acceptance_backup"
MANUAL_FACT_ID = "FACT-V101-MANUAL-FREEZE-001"
MANUAL_KNOWLEDGE_KEY = "V101_MANUAL_FREEZE"
MANUAL_TOPIC = "senal de cierre del motor v101"
MANUAL_TEXT = "La señal de cierre del motor v101 confirma que el Fact de aceptación manual está vigente."
MANUAL_QUERY = "¿Qué sé sobre la señal de cierre del motor v101?"


def _run_command(command_cls, caller, args=""):
    """Run one existing synchronous Evennia command against the real caller."""
    cmd = command_cls()
    cmd.caller = caller
    cmd.args = str(args or "")
    cmd.raw_string = f"{cmd.key} {cmd.args}".strip()
    cmd.cmdstring = cmd.key
    try:
        cmd.account = caller.account
    except Exception:
        pass
    try:
        sessions = list(caller.sessions.all())
        cmd.session = sessions[0] if sessions else None
    except Exception:
        cmd.session = None
    return cmd.func()


def _manual_backup(caller):
    return getattr(caller.db, MANUAL_BACKUP_ATTR, None)


def _save_manual_backup(caller):
    backup = _manual_backup(caller)
    if backup is not None:
        return backup, False
    backup = {
        "knowledge": _clone(getattr(caller.db, "knowledge", {})),
        "facts": _clone(getattr(caller.db, "knowledge_facts", [])),
    }
    setattr(caller.db, MANUAL_BACKUP_ATTR, backup)
    return backup, True


def _clear_manual_backup(caller):
    try:
        caller.attributes.remove(MANUAL_BACKUP_ATTR)
    except Exception:
        setattr(caller.db, MANUAL_BACKUP_ATTR, None)


def _manual_acceptance(caller, action):
    action = str(action or "").strip().lower()
    if action == "setup":
        _save_manual_backup(caller)
        upsert_knowledge_fact(
            caller,
            {
                "id": MANUAL_FACT_ID,
                "topic": MANUAL_TOPIC,
                "aliases": ["senal cierre motor v101", "cierre motor v101"],
                "text": MANUAL_TEXT,
                "knowledge_key": MANUAL_KNOWLEDGE_KEY,
                "required_level": 1,
                "canon_status": "prototype",
                "source": {"validator": "v1.01-manual-freeze-acceptance"},
                "learned_by": {"mode": "MANUAL_ACCEPTANCE"},
            },
        )
        set_knowledge_level(caller, MANUAL_KNOWLEDGE_KEY, 1)
        packet = set_knowledge_fact_status(
            caller,
            MANUAL_FACT_ID,
            FACT_STATUS_ACTIVE,
            reason="manual freeze acceptance setup",
        )
        caller.msg("=== V1.01 FINAL MANUAL ACCEPTANCE | SETUP ===")
        caller.msg(f"Fact status: {packet.get('status') or FACT_STATUS_ACTIVE}")
        caller.msg("Now type this as normal player input (no command prefix):")
        caller.msg(MANUAL_QUERY)
        caller.msg(f"EXPECTED: {MANUAL_TEXT}")
        return

    if action == "retract":
        if _manual_backup(caller) is None or not find_knowledge_fact(caller, MANUAL_FACT_ID):
            caller.msg("Manual acceptance is not set up. Run: siza-qa-latest acceptance setup")
            return
        packet = set_knowledge_fact_status(
            caller,
            MANUAL_FACT_ID,
            FACT_STATUS_RETRACTED,
            reason="manual freeze acceptance retraction",
        )
        caller.msg("=== V1.01 FINAL MANUAL ACCEPTANCE | RETRACTED ===")
        caller.msg(f"Mutation: success={packet.get('success')} status={packet.get('status')}")
        caller.msg("Type the SAME normal player input again:")
        caller.msg(MANUAL_QUERY)
        caller.msg("EXPECTED: No tienes información conocida sobre la señal de cierre del motor v101.")
        return

    if action == "reactivate":
        if _manual_backup(caller) is None or not find_knowledge_fact(caller, MANUAL_FACT_ID):
            caller.msg("Manual acceptance is not set up. Run: siza-qa-latest acceptance setup")
            return
        packet = set_knowledge_fact_status(
            caller,
            MANUAL_FACT_ID,
            FACT_STATUS_ACTIVE,
            reason="manual freeze acceptance reactivation",
        )
        caller.msg("=== V1.01 FINAL MANUAL ACCEPTANCE | REACTIVATED ===")
        caller.msg(f"Mutation: success={packet.get('success')} status={packet.get('status')}")
        caller.msg("Type the SAME normal player input one final time:")
        caller.msg(MANUAL_QUERY)
        caller.msg(f"EXPECTED: {MANUAL_TEXT}")
        caller.msg("If it matches, run: siza-qa-latest acceptance cleanup")
        return

    if action == "cleanup":
        backup = _manual_backup(caller)
        if backup is None:
            caller.msg("No manual acceptance backup is active; nothing to restore.")
            return
        caller.db.knowledge = _clone((backup or {}).get("knowledge", {}))
        caller.db.knowledge_facts = _clone((backup or {}).get("facts", []))
        _clear_manual_backup(caller)
        caller.msg("=== V1.01 FINAL MANUAL ACCEPTANCE | CLEANUP ===")
        caller.msg("Original player Knowledge/Facts restored exactly from the pre-acceptance snapshot.")
        return

    fact = find_knowledge_fact(caller, MANUAL_FACT_ID)
    caller.msg("Usage: siza-qa-latest acceptance setup|retract|reactivate|cleanup")
    caller.msg(f"Manual Fact present: {bool(fact)} | backup active: {_manual_backup(caller) is not None}")


class CmdSizaQALatest(Command):
    """Run the newest risk-based validator or the final v1.01 manual acceptance harness."""

    key = "siza-qa-latest"
    aliases = ["qa-latest"]
    locks = "cmd:perm(Admin)"

    def func(self):
        raw = str(self.args or "").strip()
        lowered = raw.lower()
        if lowered.startswith("acceptance"):
            parts = raw.split(None, 1)
            action = parts[1] if len(parts) > 1 else ""
            return _manual_acceptance(self.caller, action)

        self.caller.msg(f"=== SIZA QA LATEST | {QA_BUILD} ===")
        self.caller.msg(
            "RISK PROFILE: v1.01 production passed 9/10. RETRACTED/SUPERSEDED lifecycle authority, retrieval/disclosure/decision-effect exclusion, Fact-goal cancellation, SHARE_FACT cancellation, transfer blocking, same-identity reactivation, holder-local copy isolation and replacement semantics all passed. The sole failure was validator setup: its baseline required a relationship candidate but did not control npc.db.decision_enabled, while collect_relationship_candidates intentionally returns [] for a decision-disabled NPC. The goal and SHARE_FACT obligation were visibly active in the failed assertion. v1.01.1 changes no production code and reruns only the active-Fact baseline with decision_enabled explicitly enabled and restored."
        )
        _run_command(CmdSizaValidateV1011, self.caller)
        self.caller.msg(
            "QA POLICY: targeted validator-only follow-up. If all three assertions pass, the automated v1.01 lifecycle suite is closed. Because v1.01 changed shared/core fact_knowledge_state authority, one minimal player-facing retract/reactivate acceptance remains before freezing the engine."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
