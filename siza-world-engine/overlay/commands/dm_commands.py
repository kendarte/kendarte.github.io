from copy import deepcopy

from evennia import Command

from services.dm_campaign_director import (
    DM_DIRECTOR_BUILD,
    build_dm_turn_plan,
    complete_active_beat,
    get_campaign_state,
    set_campaign_signal,
    start_campaign,
    validate_campaign_definition,
)
from services.dm_world_context import build_dm_world_snapshot
from world.faro_ahogado_vertical_slice import FARO_AHOGADO_CAMPAIGN


DM_COMMAND_BUILD = "dm-0.1-faro-ahogado-debug-harness"


def _is_admin(actor):
    if bool(getattr(actor, "is_superuser", False)):
        return True
    try:
        return bool(actor.permissions.check("Admin"))
    except Exception:
        return False


def _show_status(actor):
    state = get_campaign_state(actor)
    if not state:
        actor.msg("DM: no hay campaña activa.")
        return
    actor.msg(f"DM | campaign={state.get('campaign_id')} | status={state.get('status')}")
    actor.msg(f"Beat activo: {state.get('active_beat_id')}")
    actor.msg(f"Beats completos: {', '.join(state.get('completed_beats') or []) or '-'}")
    actor.msg(f"Signals: {state.get('signals') or {}}")
    actor.msg(f"Director turn: {state.get('director_turn', 0)}")


class CmdSizaDMStart(Command):
    key = "siza-dm-start"
    locks = "cmd:all()"

    def func(self):
        result = start_campaign(self.caller, FARO_AHOGADO_CAMPAIGN, force=False)
        self.caller.msg(f"DM Faro Ahogado: {result.get('status')}")
        _show_status(self.caller)


class CmdSizaDMStatus(Command):
    key = "siza-dm-status"
    locks = "cmd:all()"

    def func(self):
        _show_status(self.caller)


class CmdSizaDMPlan(Command):
    key = "siza-dm-plan"
    locks = "cmd:all()"

    def func(self):
        raw = str(self.args or "").strip()
        if not raw:
            self.caller.msg("Uso: siza-dm-plan <acción libre del jugador>")
            return
        if not get_campaign_state(self.caller):
            start_campaign(self.caller, FARO_AHOGADO_CAMPAIGN)
        snapshot = build_dm_world_snapshot(self.caller, raw_player_input=raw)
        plan = build_dm_turn_plan(
            self.caller,
            FARO_AHOGADO_CAMPAIGN,
            raw,
            world_snapshot=snapshot,
        )
        self.caller.msg(f"DM PLAN | {plan.get('status')} | build={plan.get('build')}")
        beat = plan.get("active_beat") or {}
        self.caller.msg(f"Objetivo de estado: {beat.get('state_goal') or '-'}")
        location = plan.get("location") or {}
        self.caller.msg(f"Contexto local: {location.get('name') or '-'} [{location.get('room_id') or '-'}]")
        self.caller.msg("Master Deck:")
        for card in list(plan.get("selected_cards") or []):
            self.caller.msg(
                f"  {card.get('id')} | {card.get('type')} | score={card.get('director_score')} | intent={card.get('director_intent')}"
            )
        requests = plan.get("retrieval_requests") or {}
        self.caller.msg("World Engine queries: " + (", ".join(requests.get("world_engine") or []) or "-"))
        self.caller.msg("World Book topics: " + (" | ".join(requests.get("world_book") or []) or "-"))
        authority = plan.get("authority") or {}
        self.caller.msg(
            "DM authority: interpret/rank/request=yes | mutate-world="
            + str(bool(authority.get("dm_may_mutate_world"))).lower()
            + " | resolve="
            + str(bool(authority.get("dm_may_resolve_actions"))).lower()
        )


class CmdSizaDMSignal(Command):
    key = "siza-dm-signal"
    locks = "cmd:perm(Admin)"

    def func(self):
        raw = str(self.args or "").strip()
        if "=" not in raw:
            self.caller.msg("Uso: siza-dm-signal <key>=<value>")
            return
        key, value = raw.split("=", 1)
        value = value.strip()
        if value.lower() in {"true", "false"}:
            parsed = value.lower() == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        result = set_campaign_signal(self.caller, key.strip(), parsed)
        self.caller.msg(f"DM signal: {result.get('status')} | {result.get('signal')}={result.get('value')}")


class CmdSizaDMAdvance(Command):
    key = "siza-dm-advance"
    locks = "cmd:perm(Admin)"

    def func(self):
        result = complete_active_beat(
            self.caller,
            FARO_AHOGADO_CAMPAIGN,
            evidence={"source": "ADMIN_DEBUG", "note": str(self.args or "").strip()},
        )
        self.caller.msg(
            f"DM advance: {result.get('status')} | completed={result.get('completed_beat_id')} | active={result.get('active_beat_id')}"
        )


class CmdSizaValidateDMV01(Command):
    key = "siza-validate-dm-v01"
    locks = "cmd:perm(Admin)"

    def func(self):
        original = deepcopy(getattr(self.caller.db, "dm_campaign_state", None))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA DM VALIDATION v0.1 | {DM_COMMAND_BUILD} ===")
        try:
            definition = validate_campaign_definition(FARO_AHOGADO_CAMPAIGN)
            check("faro-ahogado-definition-valid", bool(definition.get("valid")), str(definition.get("errors")))

            started = start_campaign(self.caller, FARO_AHOGADO_CAMPAIGN, force=True)
            state = get_campaign_state(self.caller)
            check(
                "campaign-starts-on-lead-beat",
                started.get("started") is True and state.get("active_beat_id") == "FA-BEAT-LEAD",
                str(state.get("active_beat_id")),
            )

            raw = "pregunto por rumores de la expedición y busco una pista sobre el faro"
            snapshot = build_dm_world_snapshot(self.caller, raw_player_input=raw)
            plan = build_dm_turn_plan(self.caller, FARO_AHOGADO_CAMPAIGN, raw, world_snapshot=snapshot)
            ids = [str(card.get("id") or "") for card in list(plan.get("selected_cards") or [])]
            check(
                "lead-input-ranks-information-source-card",
                bool(ids) and ids[0] == "FA-CARD-LEAD-SOURCE",
                str(ids),
            )
            authority = plan.get("authority") or {}
            check(
                "dm-remains-non-authoritative",
                authority.get("dm_may_mutate_world") is False
                and authority.get("dm_may_resolve_actions") is False
                and authority.get("dm_may_invent_facts") is False,
                str(authority),
            )

            set_campaign_signal(self.caller, "attention", 1)
            attention_plan = build_dm_turn_plan(
                self.caller,
                FARO_AHOGADO_CAMPAIGN,
                "robo un documento y fuerzo la cerradura",
                world_snapshot=build_dm_world_snapshot(self.caller, raw_player_input="robo un documento y fuerzo la cerradura"),
            )
            attention_ids = [str(card.get("id") or "") for card in list(attention_plan.get("selected_cards") or [])]
            check(
                "authoritative-signal-makes-consequence-card-eligible",
                "FA-CARD-CONSEQUENCE-ATTENTION" in attention_ids,
                str(attention_ids),
            )

            advanced = complete_active_beat(
                self.caller,
                FARO_AHOGADO_CAMPAIGN,
                evidence={"source": "QA", "fact_id": "FA-QA-LEAD"},
            )
            route_plan = build_dm_turn_plan(
                self.caller,
                FARO_AHOGADO_CAMPAIGN,
                "quiero encontrar una ruta viable",
                world_snapshot=build_dm_world_snapshot(self.caller, raw_player_input="quiero encontrar una ruta viable"),
            )
            route_ids = [str(card.get("id") or "") for card in list(route_plan.get("selected_cards") or [])]
            check(
                "authoritative-beat-evidence-advances-to-route-deck",
                advanced.get("active_beat_id") == "FA-BEAT-ROUTE" and "FA-CARD-ROUTE-EVIDENCE" in route_ids,
                f"active={advanced.get('active_beat_id')} cards={route_ids}",
            )
        finally:
            self.caller.db.dm_campaign_state = original

        passed = sum(1 for value in results if value)
        self.caller.msg(f"RESULT: {passed}/{len(results)} PASS")
        self.caller.msg("STATE RESTORED: dm_campaign_state restored to its previous value")
        self.caller.msg(f"CORE UNCHANGED: DM layer only | director={DM_DIRECTOR_BUILD}")
        self.caller.msg("========================================================")
