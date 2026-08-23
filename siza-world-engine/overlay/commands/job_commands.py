from evennia import Command

from services.job_engine import inspect_job_tasks, set_job_task_active
from services.npc_simulation import find_npc


class CmdSizaJobs(Command):
    """Inspect persistent world job tasks and NPC eligibility."""

    key = "siza-jobs"
    aliases = ["jobs-state"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        npc = find_npc(query) if query else None
        if query and not npc:
            self.caller.msg("No identifico un NPC de Siza con ese nombre.")
            return

        rows = inspect_job_tasks(npc=npc)
        self.caller.msg("=== SIZA WORLD JOBS ===")
        if npc:
            job = dict(npc.db.job or {})
            self.caller.msg(
                f"NPC: {npc.key} | job_id={job.get('id') or 'NONE'} | job={job.get('name') or 'NONE'}"
            )
        if not rows:
            self.caller.msg("No hay tareas de trabajo persistentes registradas.")
        else:
            for row in rows:
                self.caller.msg(
                    f"{row.get('id')} | site={row.get('site')} | job_id={row.get('job_id')} | "
                    f"active={row.get('active')} | status={row.get('status')} | "
                    f"priority={row.get('priority')} | eligible={row.get('eligible')}"
                )
                if row.get("activity"):
                    self.caller.msg(f"  activity={row.get('activity')}")
        self.caller.msg("=======================")


class CmdSizaJobToggle(Command):
    """Admin/debug: activate or deactivate one authored world job task."""

    key = "siza-job-toggle"
    aliases = ["job-toggle"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 2:
            self.caller.msg("Uso: siza-job-toggle <TASK_ID> <on|off>")
            return

        task_id, state_word = parts
        state_word = state_word.lower()
        if state_word not in {"on", "off"}:
            self.caller.msg("El estado debe ser on u off.")
            return

        site = set_job_task_active(task_id, state_word == "on")
        if not site:
            self.caller.msg(f"Task de trabajo no encontrado: {task_id}")
            return

        self.caller.msg(
            f"World JOB {task_id}: {'ACTIVE' if state_word == 'on' else 'INACTIVE'} | site={site.key}."
        )
