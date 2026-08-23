from evennia import Command

from services.job_claims import get_job_claim, release_job_claim
from services.job_engine import (
    inspect_job_tasks,
    inspect_worksites,
    refresh_world_job_rules,
    set_job_task_active,
    set_work_state,
)
from services.npc_simulation import find_npc


def _find_worksite(query):
    query = str(query or "").strip().lower()
    rows = inspect_worksites()
    if not query:
        return rows[0].get("site") if len(rows) == 1 else None

    exact = []
    partial = []
    for row in rows:
        site = row.get("site")
        name = str(row.get("name") or "").lower()
        room_id = str(row.get("room_id") or "").lower()
        if query in {name, room_id}:
            exact.append(site)
        elif query in name or query in room_id:
            partial.append(site)
    if len(exact) == 1:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


class CmdSizaJobs(Command):
    """Inspect persistent world job tasks, claims, progress and NPC eligibility."""

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
                claim = get_job_claim(row.get("id"))
                claim_text = claim.get("npc_name") if claim else "NONE"
                self.caller.msg(
                    f"{row.get('id')} | site={row.get('site')} | job_id={row.get('job_id')} | "
                    f"active={row.get('active')} | status={row.get('status')} | "
                    f"priority={row.get('priority')} | eligible={row.get('eligible')} | "
                    f"rule={row.get('rule_id') or 'NONE'} | claim={claim_text} | "
                    f"work={row.get('work_done')}/{row.get('work_required')} "
                    f"(+{row.get('work_per_action')}/WORK)"
                )
                if row.get("activity"):
                    self.caller.msg(f"  activity={row.get('activity')}")
                if claim:
                    self.caller.msg(
                        f"  claim_owner={claim.get('npc_name')} | npc_id={claim.get('npc_id')} | "
                        f"claimed_at={claim.get('claimed_at')}"
                    )
                    self.caller.msg(
                        f"  claim_source={claim.get('claim_source') or 'LEGACY'} | "
                        f"policy={claim.get('claim_policy') or 'FIRST_SELECTED'} | "
                        f"distance={claim.get('claim_distance')}"
                    )
                if row.get("work_last_npc_name"):
                    self.caller.msg(f"  last_worker={row.get('work_last_npc_name')}")
                if row.get("completion_effects_applied"):
                    self.caller.msg(f"  completion_effects={row.get('completion_effects_applied')}")
        self.caller.msg("=======================")


class CmdSizaJobToggle(Command):
    """Admin/debug: activate/deactivate an authored task manually."""

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

        if state_word == "off":
            release_job_claim(task_id, force=True)

        self.caller.msg(
            f"World JOB {task_id}: {'ACTIVE' if state_word == 'on' else 'INACTIVE'} | site={site.key}."
        )
        self.caller.msg("Si la task tiene rule_id, el productor puede sobrescribir este estado en el próximo refresh.")


class CmdSizaJobRelease(Command):
    """Admin/debug: force-release the owner of one active JOB without changing progress."""

    key = "siza-job-release"
    aliases = ["job-release"]
    locks = "cmd:perm(Admin)"

    def func(self):
        task_id = (self.args or "").strip()
        if not task_id:
            self.caller.msg("Uso: siza-job-release <TASK_ID>")
            return
        released = release_job_claim(task_id, force=True)
        if not released:
            self.caller.msg(f"No hay claim activo para {task_id}.")
            return
        self.caller.msg(
            f"Claim liberado: {task_id} | owner={released.get('npc_name')} | "
            f"progress conservado."
        )


class CmdSizaWorksite(Command):
    """Inspect persistent worksite state and automatic job-production rules."""

    key = "siza-worksite"
    aliases = ["worksite", "site-state"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip().lower()
        rows = inspect_worksites()
        if query:
            rows = [
                row for row in rows
                if query in str(row.get("name") or "").lower()
                or query in str(row.get("room_id") or "").lower()
            ]

        if not rows:
            self.caller.msg("No identifico un worksite de Siza con esa consulta.")
            return

        self.caller.msg("=== SIZA WORKSITES ===")
        for row in rows:
            self.caller.msg(f"{row.get('name')} | room_id={row.get('room_id')}")
            self.caller.msg(f"  state={row.get('work_state')}")
            rules = row.get("job_rules") or []
            if not rules:
                self.caller.msg("  rules=NONE")
            for rule in rules:
                self.caller.msg(
                    f"  rule={rule.get('id')} | enabled={rule.get('enabled', True)} | "
                    f"if {rule.get('field')} {rule.get('op')} {rule.get('value')} -> task={rule.get('task_id')}"
                )
                if rule.get("completion_effects"):
                    self.caller.msg(f"    completion_effects={rule.get('completion_effects')}")
        self.caller.msg("======================")


class CmdSizaWorkSet(Command):
    """Admin/debug: mutate one persistent worksite field and refresh producers immediately."""

    key = "siza-workset"
    aliases = ["workset"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 3:
            self.caller.msg("Uso: siza-workset <ROOM_ID> <field> <value>")
            return

        site_query, field, value = parts
        site = _find_worksite(site_query)
        if not site:
            self.caller.msg("No identifico un único worksite con ese ROOM_ID/nombre.")
            return

        state = set_work_state(site, field, value)
        refresh = refresh_world_job_rules()
        self.caller.msg(f"{site.key}: {field}={state.get(field)}")
        relevant = [row for row in refresh if row.get("room_id") == site.db.room_id]
        for row in relevant:
            self.caller.msg(
                f"[PRODUCER] {row.get('rule_id')}: condition={row.get('condition_met')} | "
                f"task={row.get('task_id')} active={row.get('task_active')} "
                f"status={row.get('task_status')} | work={row.get('work_done')}/{row.get('work_required')}"
            )


class CmdSizaJobRefresh(Command):
    """Admin/debug: evaluate all worksite producers without advancing NPCs."""

    key = "siza-job-refresh"
    aliases = ["job-refresh"]
    locks = "cmd:perm(Admin)"

    def func(self):
        rows = refresh_world_job_rules()
        self.caller.msg("=== SIZA JOB PRODUCERS ===")
        if not rows:
            self.caller.msg("No hay reglas productoras para evaluar.")
        for row in rows:
            self.caller.msg(
                f"{row.get('site')} | {row.get('rule_id')} | "
                f"{row.get('field')}={row.get('actual')} {row.get('op')} {row.get('expected')} | "
                f"condition={row.get('condition_met')} | task={row.get('task_id')} "
                f"active={row.get('task_active')} status={row.get('task_status')} | "
                f"work={row.get('work_done')}/{row.get('work_required')}"
            )
        self.caller.msg("==========================")
