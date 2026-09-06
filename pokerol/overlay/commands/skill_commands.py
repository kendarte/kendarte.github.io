from evennia import Command

from services.npc_simulation import find_npc
from services.skill_engine import SKILL_BUILD, inspect_skills, set_skill_level


class CmdSizaSkills(Command):
    """Inspect persistent practical competencies for one NPC."""

    key = "siza-skills"
    aliases = ["npc-skills", "skills-state"]
    locks = "cmd:all()"

    def func(self):
        npc = find_npc((self.args or "").strip())
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        state = inspect_skills(npc)
        self.caller.msg(f"=== SIZA SKILLS | {SKILL_BUILD} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={state.get('npc_id')}")
        skills = state.get("skills") or {}
        if not skills:
            self.caller.msg("Skills: NONE")
        else:
            for skill_id, item in sorted(skills.items()):
                self.caller.msg(
                    f"  {skill_id} | name={item.get('name') or skill_id} | "
                    f"level={item.get('level', 0)} | status={item.get('canon_status') or 'prototype'}"
                )
        self.caller.msg("===============================================")


class CmdSizaSkillSet(Command):
    """Admin/debug: set one practical skill level on an NPC."""

    key = "siza-skill-set"
    aliases = ["skill-set"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            self.caller.msg("Uso: siza-skill-set <NPC> <SKILL_ID> <LEVEL>")
            return

        try:
            level = int(parts[-1])
        except ValueError:
            self.caller.msg("LEVEL debe ser un entero >= 0.")
            return

        skill_id = parts[-2]
        npc_query = " ".join(parts[:-2])
        npc = find_npc(npc_query)
        if not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        packet = set_skill_level(npc, skill_id, level)
        if not packet:
            self.caller.msg("No pude modificar ese skill.")
            return

        self.caller.msg(
            f"{npc.key}: skill {packet.get('skill_id')} "
            f"{packet.get('before')} -> {packet.get('after')}"
        )
