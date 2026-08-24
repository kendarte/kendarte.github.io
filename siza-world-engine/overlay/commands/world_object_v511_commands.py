from evennia import Command, search_object

from commands.world_object_v51_commands import CmdSizaValidateV51
from world.upgrade_pilot_v51 import (
    CONTAINER_ID,
    MANIFEST_VISIBLE_FIELD,
    PESCADERIA_ID,
    ensure_v51_pilot_content,
)


HOTFIX_BUILD = "0.51.1-pescaderia-playtest-reset"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _find_pescaderia():
    for obj in search_object("Pescaderia de Darsena"):
        if str(getattr(obj.db, "room_id", "") or "") == PESCADERIA_ID:
            return obj
    return None


def reset_v51_playtest_state():
    """Reset only the v0.51 prototype loop to its authored initial state."""
    install = ensure_v51_pilot_content()
    if not bool(install.get("success")):
        return {
            "success": False,
            "reason": install.get("reason") or "INSTALL_FAILED",
            "build": HOTFIX_BUILD,
        }

    site = install.get("site") or _find_pescaderia()
    container = install.get("container")
    manifest = install.get("manifest")
    if not site or not container or not manifest:
        return {
            "success": False,
            "reason": "PERSISTENT_CONTENT_MISSING",
            "build": HOTFIX_BUILD,
        }

    if str(getattr(container.db, "object_id", "") or "") != CONTAINER_ID:
        return {
            "success": False,
            "reason": "CONTAINER_ID_MISMATCH",
            "build": HOTFIX_BUILD,
        }

    state = _plain_dict(getattr(container.db, "state", {}))
    state["sealed"] = True
    state["opened_count"] = 0
    state["inspected"] = False
    container.db.state = state

    world_state = _plain_dict(getattr(site.db, "world_state", {}))
    world_state.pop(MANIFEST_VISIBLE_FIELD, None)
    site.db.world_state = world_state

    return {
        "success": True,
        "reason": "PLAYTEST_RESET",
        "build": HOTFIX_BUILD,
        "site": site,
        "container": container,
        "manifest": manifest,
        "sealed": True,
        "opened_count": 0,
        "inspected": False,
        "manifest_visible": False,
    }


class CmdSizaResetV51(Command):
    """Reset only the persistent v0.51 Pescaderia prototype loop."""

    key = "siza-reset-v51"
    aliases = ["reset-v51"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v51_playtest_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.51.1 RESET] FAIL | reason={result.get('reason')} | build={HOTFIX_BUILD}"
            )
            return

        site = result.get("site")
        container = result.get("container")
        manifest = result.get("manifest")
        self.caller.msg(f"=== SIZA v0.51.1 RESET | {HOTFIX_BUILD} ===")
        self.caller.msg(
            f"PASS Pescaderia playtest reset | site={site.key}#{site.id} | container=#{container.id} | manifest=#{manifest.id}"
        )
        self.caller.msg("Cajon: sealed=True | opened_count=0 | inspected=False")
        self.caller.msg("Manifiesto: persistent=True | visible=False")
        self.caller.msg("No se tocaron jobs, NPCs, exits, skills, Knowledge ni otros world_state fields.")
        self.caller.msg("========================================================")


class CmdSizaValidateV51Fixed(CmdSizaValidateV51):
    """Run v0.51 validation, then force the prototype loop back to clean playtest state."""

    key = "siza-validate-v51"
    aliases = ["validate-v51"]
    locks = "cmd:perm(Admin)"

    def func(self):
        super().func()
        result = reset_v51_playtest_state()
        if result.get("success"):
            self.caller.msg(
                f"V0.51.1 HOTFIX: playtest state reset after validation | sealed=True inspected=False manifest_visible=False"
            )
        else:
            self.caller.msg(
                f"V0.51.1 HOTFIX FAIL: could not reset playtest state | reason={result.get('reason')}"
            )
