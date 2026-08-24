import uuid

from evennia import Command

from services.npc_simulation import find_npc
from services.room_presentation_engine import (
    ROOM_PRESENTATION_BUILD,
    inspect_state_presentations,
)


def _clone(value):
    if hasattr(value, "items"):
        try:
            return {str(key): _clone(item) for key, item in value.items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_clone(item) for item in value]
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        try:
            return [_clone(item) for item in value]
        except Exception:
            pass
    return value


class CmdSizaValidateV45(Command):
    """Validate state-driven room presentation without leaving persistent test state."""

    key = "siza-validate-v45"
    aliases = ["validate-v45"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = find_npc("Informante C")
        if not actor or not actor.location:
            self.caller.msg("[V0.45 VALIDATION] FAIL | Informante C/location missing")
            return

        site = actor.location
        had_world_state = bool(site.attributes.has("world_state"))
        had_presentations = bool(site.attributes.has("state_presentations"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_presentations = _clone(getattr(site.db, "state_presentations", None))

        suffix = uuid.uuid4().hex[:10]
        flag = f"v045_visible_{suffix}"
        second_flag = f"v045_secondary_{suffix}"
        active_text = f"[V045-{suffix}] La compuerta de prueba esta abierta."
        multi_text = f"[V045-MULTI-{suffix}] Ambos estados coinciden."
        disabled_text = f"[V045-DISABLED-{suffix}] NO DEBE VERSE."
        invalid_text = f"[V045-INVALID-{suffix}] NO DEBE VERSE."
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            tail = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{tail}")

        self.caller.msg(f"=== SIZA VALIDATION v0.45 | {ROOM_PRESENTATION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {actor.key} | site={site.key} | dbref=#{site.id}")

        try:
            site.db.world_state = {}
            site.db.state_presentations = [
                {
                    "id": f"V045-ACTIVE-{suffix}",
                    "enabled": True,
                    "text": active_text,
                    "state_requirements": [
                        {"field": flag, "op": "EQ", "value": 1, "name": "Compuerta abierta"}
                    ],
                    "canon_status": "prototype",
                },
                {
                    "id": f"V045-MULTI-{suffix}",
                    "enabled": True,
                    "text": multi_text,
                    "state_requirements": [
                        {"field": flag, "op": "EQ", "value": 1},
                        {"field": second_flag, "op": "GTE", "value": 2},
                    ],
                    "canon_status": "prototype",
                },
                {
                    "id": f"V045-DISABLED-{suffix}",
                    "enabled": False,
                    "text": disabled_text,
                    "state_requirements": [],
                    "canon_status": "prototype",
                },
                {
                    "id": f"V045-INVALID-{suffix}",
                    "enabled": True,
                    "text": invalid_text,
                    "state_requirements": [
                        {"field": flag, "op": "EXECUTE", "value": 1}
                    ],
                    "canon_status": "prototype",
                },
            ]

            base_without_state = str(site.return_appearance(actor) or "")
            rows_without_state = inspect_state_presentations(site)
            active_row = next((row for row in rows_without_state if row.get("text") == active_text), None)
            check(
                "unmet-state-fragment-is-not-rendered",
                active_text not in base_without_state and active_row is not None and active_row.get("active") is False,
                f"active={None if active_row is None else active_row.get('active')}",
            )

            check(
                "normal-room-appearance-remains-present-without-active-fragments",
                str(site.key) in base_without_state and active_text not in base_without_state,
                f"room_name_present={str(site.key) in base_without_state}",
            )

            site.db.world_state = {flag: 1}
            appearance_open = str(site.return_appearance(actor) or "")
            rows_open = inspect_state_presentations(site)
            active_row = next((row for row in rows_open if row.get("text") == active_text), None)
            check(
                "matching-world-state-appends-authored-room-text",
                active_text in appearance_open and active_row is not None and active_row.get("active") is True,
                f"active={None if active_row is None else active_row.get('active')}",
            )

            multi_row = next((row for row in rows_open if row.get("text") == multi_text), None)
            check(
                "multiple-state-requirements-use-all-semantics",
                multi_text not in appearance_open and multi_row is not None and multi_row.get("active") is False,
                f"active={None if multi_row is None else multi_row.get('active')}",
            )

            site.db.world_state = {flag: 1, second_flag: 2}
            appearance_multi = str(site.return_appearance(actor) or "")
            check(
                "all-matching-state-requirements-render-fragment",
                active_text in appearance_multi and multi_text in appearance_multi,
                f"active_text={active_text in appearance_multi} multi_text={multi_text in appearance_multi}",
            )

            check(
                "disabled-and-malformed-presentations-fail-closed",
                disabled_text not in appearance_multi and invalid_text not in appearance_multi,
                f"disabled_visible={disabled_text in appearance_multi} malformed_visible={invalid_text in appearance_multi}",
            )

            site.db.world_state = {}
            appearance_relocked = str(site.return_appearance(actor) or "")
            check(
                "presentation-is-live-and-disappears-when-state-no-longer-matches",
                active_text not in appearance_relocked and multi_text not in appearance_relocked,
                f"active_visible={active_text in appearance_relocked} multi_visible={multi_text in appearance_relocked}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    site.db.world_state = None
            if had_presentations:
                site.db.state_presentations = original_presentations
            else:
                try:
                    site.attributes.remove("state_presentations")
                except Exception:
                    site.db.state_presentations = None

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("TEMP STATE RESTORED: room world_state and state_presentations restored")
        self.caller.msg("========================================================")
