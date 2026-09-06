from evennia import Command

from services.dm_campaign_director import build_dm_turn_plan, complete_active_beat, get_campaign_state, set_campaign_signal
from services.dm_campaign_registry import get_active_campaign_definition, start_registered_campaign
from services.dm_world_context import build_dm_world_snapshot


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


class CmdPokerolDMStart(Command):
    key = "pokerol-dm-start"
    aliases = ["dm-start"]
    locks = "cmd:all()"

    def func(self):
        campaign_id = str(self.args or "").strip()
        if not campaign_id:
            self.caller.msg("Uso: pokerol-dm-start <campaign-id>")
            return
        result = start_registered_campaign(self.caller, campaign_id, force=False)
        self.caller.msg(f"DM campaign {campaign_id}: {result.get('status')}")
        _show_status(self.caller)


class CmdPokerolDMStatus(Command):
    key = "pokerol-dm-status"
    aliases = ["dm-status"]
    locks = "cmd:all()"

    def func(self):
        _show_status(self.caller)


class CmdPokerolDMPlan(Command):
    key = "pokerol-dm-plan"
    aliases = ["dm-plan"]
    locks = "cmd:all()"

    def func(self):
        raw = str(self.args or "").strip()
        if not raw:
            self.caller.msg("Uso: pokerol-dm-plan <acción libre del jugador>")
            return
        active = get_active_campaign_definition(self.caller)
        definition = active.get("definition")
        if not definition:
            self.caller.msg("DM PLAN | NO_ACTIVE_CAMPAIGN")
            return
        snapshot = build_dm_world_snapshot(self.caller, raw_player_input=raw)
        plan = build_dm_turn_plan(self.caller, definition, raw, world_snapshot=snapshot)
        self.caller.msg(f"DM PLAN | {plan.get('status')} | build={plan.get('build')}")
        beat = plan.get("active_beat") or {}
        self.caller.msg(f"Objetivo de estado: {beat.get('state_goal') or '-'}")
        location = plan.get("location") or {}
        self.caller.msg(f"Contexto local: {location.get('name') or '-'} [{location.get('room_id') or '-'}]")
        for card in list(plan.get("selected_cards") or []):
            self.caller.msg(f"  {card.get('id')} | {card.get('type')} | score={card.get('director_score')} | intent={card.get('director_intent')}")
        requests = plan.get("retrieval_requests") or {}
        self.caller.msg("World Engine queries: " + (", ".join(requests.get("world_engine") or []) or "-"))
        self.caller.msg("World Book topics: " + (" | ".join(requests.get("world_book") or []) or "-"))


class CmdPokerolDMSignal(Command):
    key = "pokerol-dm-signal"
    aliases = ["dm-signal"]
    locks = "cmd:perm(Admin)"

    def func(self):
        raw = str(self.args or "").strip()
        if "=" not in raw:
            self.caller.msg("Uso: pokerol-dm-signal <key>=<value>")
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


class CmdPokerolDMAdvance(Command):
    key = "pokerol-dm-advance"
    aliases = ["dm-advance"]
    locks = "cmd:perm(Admin)"

    def func(self):
        active = get_active_campaign_definition(self.caller)
        definition = active.get("definition")
        if not definition:
            self.caller.msg("DM advance: NO_ACTIVE_CAMPAIGN")
            return
        result = complete_active_beat(
            self.caller,
            definition,
            evidence={"source": "ADMIN_DEBUG", "note": str(self.args or "").strip()},
        )
        self.caller.msg(f"DM advance: {result.get('status')} | completed={result.get('completed_beat_id')} | active={result.get('active_beat_id')}")
