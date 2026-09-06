"""POKEROL anime-world physics.

Deterministic, game-facing physical logic for move/world interactions.  This is
not a real-world simulator: it uses readable material/state rules so the DM can
reason consistently about anime-style consequences such as ignition, conductive
water, freezing, melting and thermal shock.

The module never writes to Evennia. It returns state changes and propagated
impacts for the execution/consequence layer to apply authoritatively.
"""

from copy import deepcopy


DEFAULT_PHYSICAL = {
    "flammability": 0.0,
    "conductivity": 0.0,
    "thermal_shock_sensitivity": 0.0,
    "ignition_point_c": 260.0,
    "melting_point_c": None,
    "freezing_point_c": 0.0,
    "heat_resistance": 0.0,
    "water_absorption": 0.0,
}

DEFAULT_STATE = {
    "temperature_c": 20.0,
    "wetness": 0.0,
    "burning": False,
    "frozen": False,
    "brittle": False,
    "cracked": False,
    "broken": False,
    "integrity": 1.0,
}

WATERLIKE = {"WATER", "PUDDLE", "POND", "STREAM", "RIVER", "LAKE"}
THERMAL_SHOCK_MATERIALS = {"GLASS", "STONE", "CERAMIC", "ICE", "BRITTLE_STRUCTURE", "FRAGILE_STRUCTURE"}
CONDUCTIVE_MATERIALS = {"WATER", "METAL", "ELECTRICAL_DEVICE"}
FLAMMABLE_MATERIALS = {"VEGETATION", "WOOD", "ROPE", "FABRIC", "PAPER", "DRY_GRASS", "LEAF_LITTER"}


def _dict(value):
    return dict(value or {}) if hasattr(value or {}, "items") else {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _tags(value):
    return {str(item).strip().upper() for item in _list(value) if str(item).strip()}


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def _target_packet(target):
    target = deepcopy(_dict(target))
    target.setdefault("materials", [])
    physical = dict(DEFAULT_PHYSICAL)
    physical.update(_dict(target.get("physical_properties")))
    state = dict(DEFAULT_STATE)
    state.update(_dict(target.get("environmental_state")))
    target["physical_properties"] = physical
    target["environmental_state"] = state
    return target


def _material_defaults(target):
    materials = _tags(target.get("materials")) | _tags(target.get("tags"))
    p = target["physical_properties"]
    if materials & FLAMMABLE_MATERIALS:
        p["flammability"] = max(float(p.get("flammability") or 0), 0.65)
    if materials & CONDUCTIVE_MATERIALS:
        p["conductivity"] = max(float(p.get("conductivity") or 0), 0.75)
    if materials & THERMAL_SHOCK_MATERIALS:
        p["thermal_shock_sensitivity"] = max(float(p.get("thermal_shock_sensitivity") or 0), 0.7)
    if "ICE" in materials and p.get("melting_point_c") is None:
        p["melting_point_c"] = 0.0
    return materials


def _event(events, kind, **payload):
    events.append({"type": kind, **payload})


def _apply_thermal_shock(target, before_temp, after_temp, events):
    state = target["environmental_state"]
    physical = target["physical_properties"]
    materials = _tags(target.get("materials")) | _tags(target.get("tags"))
    delta = abs(float(after_temp) - float(before_temp))
    sensitivity = float(physical.get("thermal_shock_sensitivity") or 0)
    if not sensitivity and not (materials & THERMAL_SHOCK_MATERIALS):
        return
    effective = delta * max(0.25, sensitivity)
    if effective >= 95:
        state["cracked"] = True
        state["broken"] = True
        state["integrity"] = _clamp(float(state.get("integrity", 1)) - 0.65)
        _event(events, "THERMAL_SHOCK_BREAK", delta_c=round(delta, 1), integrity=state["integrity"])
    elif effective >= 55:
        state["cracked"] = True
        state["brittle"] = True
        state["integrity"] = _clamp(float(state.get("integrity", 1)) - 0.3)
        _event(events, "THERMAL_SHOCK_CRACK", delta_c=round(delta, 1), integrity=state["integrity"])


def _apply_heat(target, intensity, events):
    state = target["environmental_state"]
    physical = target["physical_properties"]
    before = float(state.get("temperature_c") or 20)
    resistance = _clamp(physical.get("heat_resistance") or 0)
    rise = 70.0 * float(intensity) * (1.0 - resistance * 0.65)
    state["temperature_c"] = before + rise
    state["frozen"] = False
    if state.get("wetness", 0) > 0:
        state["wetness"] = _clamp(float(state.get("wetness") or 0) - 0.25 * intensity)
    _event(events, "HEATED", from_c=round(before, 1), to_c=round(state["temperature_c"], 1))

    melting = physical.get("melting_point_c")
    if melting is not None and state["temperature_c"] >= float(melting):
        _event(events, "MELTED", temperature_c=round(state["temperature_c"], 1))


def _apply_cooling(target, intensity, events, source_temperature_c=-25.0):
    state = target["environmental_state"]
    before = float(state.get("temperature_c") or 20)
    drop = max(35.0, abs(before - float(source_temperature_c)) * 0.75) * float(intensity)
    state["temperature_c"] = before - drop
    _event(events, "COOLED", from_c=round(before, 1), to_c=round(state["temperature_c"], 1))
    _apply_thermal_shock(target, before, state["temperature_c"], events)


def _apply_water(target, intensity, events, water_temperature_c=18.0):
    state = target["environmental_state"]
    physical = target["physical_properties"]
    before_temp = float(state.get("temperature_c") or 20)
    absorption = max(0.35, float(physical.get("water_absorption") or 0))
    state["wetness"] = _clamp(float(state.get("wetness") or 0) + 0.65 * intensity * absorption)
    if state.get("burning"):
        state["burning"] = False
        _event(events, "EXTINGUISHED")
    # Strong water attacks pull temperature toward the water temperature.
    state["temperature_c"] = before_temp + (float(water_temperature_c) - before_temp) * min(0.85, 0.55 * intensity)
    _event(events, "SOAKED", wetness=round(state["wetness"], 3))
    _apply_thermal_shock(target, before_temp, state["temperature_c"], events)


def _apply_ignite(target, intensity, events):
    state = target["environmental_state"]
    physical = target["physical_properties"]
    flammability = float(physical.get("flammability") or 0)
    hot_enough = float(state.get("temperature_c") or 20) >= float(physical.get("ignition_point_c") or 260)
    dry_enough = float(state.get("wetness") or 0) < 0.55
    if flammability * float(intensity) >= 0.45 and (hot_enough or intensity >= 0.75) and dry_enough:
        state["burning"] = True
        _event(events, "IGNITED", flammability=round(flammability, 3))
    elif not dry_enough:
        _event(events, "IGNITION_RESISTED_WET")
    else:
        _event(events, "SCORCHED")


def _apply_freeze(target, intensity, events):
    state = target["environmental_state"]
    materials = _tags(target.get("materials")) | _tags(target.get("tags"))
    _apply_cooling(target, intensity, events)
    if materials & WATERLIKE or float(state.get("wetness") or 0) >= 0.55:
        state["frozen"] = True
        state["wetness"] = max(0.0, float(state.get("wetness") or 0) - 0.35)
        _event(events, "FROZEN_SURFACE_CREATED")


def _electric_conduction(target, environment, intensity, events):
    state = target["environmental_state"]
    physical = target["physical_properties"]
    materials = _tags(target.get("materials")) | _tags(target.get("tags"))
    env = _dict(environment)
    wet = float(state.get("wetness") or 0) >= 0.35
    water_body_id = str(target.get("water_body_id") or env.get("water_body_id") or "").strip()
    shared_water = bool(water_body_id or materials & WATERLIKE or env.get("shared_water_body"))
    conductivity = max(float(physical.get("conductivity") or 0), 0.85 if wet else 0.0, 1.0 if shared_water else 0.0)

    _event(events, "ELECTRIFIED", conductivity=round(conductivity, 3))
    impacts = []
    members = _list(env.get("medium_members")) if shared_water else _list(env.get("touching_conductive_members"))
    if conductivity >= 0.55:
        for member in members:
            row = _dict(member)
            member_id = str(row.get("id") or row.get("dbref") or row.get("name") or "").strip()
            if not member_id:
                continue
            distance = float(row.get("distance_m") or 0)
            attenuation = 1.0 if shared_water else max(0.25, 1.0 - distance / 12.0)
            impacts.append({
                "target_id": member_id,
                "effect": "ELECTRIC_SHOCK",
                "element": "ELECTRIC",
                "intensity": round(float(intensity) * conductivity * attenuation, 3),
                "shared_medium": water_body_id or ("WATER" if shared_water else "CONDUCTOR"),
            })
        if impacts:
            _event(events, "CONDUCTIVE_AREA_DISCHARGE", count=len(impacts), medium=water_body_id or "WATER")
    return impacts


def resolve_anime_physics(move, target, environment=None, intensity=1.0):
    """Resolve the physical consequences of one already-authorized move use.

    Returns a copied target packet, discrete events and area impacts. Callers may
    pass dynamic `medium_members` in environment to represent every creature or
    object currently standing/swimming in the same water body.
    """
    move = _dict(move)
    target = _target_packet(target)
    environment = _dict(environment)
    intensity = max(0.1, min(3.0, float(intensity or 1.0)))
    materials = _material_defaults(target)
    effects = _tags(move.get("world_effects"))
    events = []
    area_impacts = []

    if effects & {"HEAT", "BURN", "IGNITE", "MELT"}:
        _apply_heat(target, intensity, events)
    if effects & {"IGNITE", "BURN"}:
        _apply_ignite(target, intensity, events)
    if effects & {"WATER", "SOAK"}:
        _apply_water(target, intensity, events, environment.get("water_temperature_c", 18.0))
    if effects & {"COOL"}:
        _apply_cooling(target, intensity, events)
    if effects & {"FREEZE"}:
        _apply_freeze(target, intensity, events)
    if effects & {"ELECTRIFY", "SHORT_CIRCUIT", "POWER_DEVICE"}:
        area_impacts.extend(_electric_conduction(target, environment, intensity, events))

    state = target["environmental_state"]
    if "BREAK" in effects or "BLUNT" in effects:
        vulnerable = bool(materials & {"GLASS", "FRAGILE_STRUCTURE", "BRITTLE_STRUCTURE"}) or state.get("brittle") or state.get("cracked")
        if vulnerable:
            damage = 0.5 * intensity * (1.35 if state.get("cracked") else 1.0)
            state["integrity"] = _clamp(float(state.get("integrity", 1)) - damage)
            if state["integrity"] <= 0.25:
                state["broken"] = True
                _event(events, "STRUCTURAL_BREAK", integrity=state["integrity"])
            else:
                _event(events, "STRUCTURAL_DAMAGE", integrity=state["integrity"])

    if "CUT" in effects or "CUT_VEGETATION" in effects:
        if materials & {"VEGETATION", "ROPE", "FABRIC"}:
            _event(events, "CUT_SUCCEEDED")

    if "CLEAR_SMOKE" in effects or "CREATE_WIND" in effects:
        if environment.get("smoke_density") is not None:
            before = float(environment.get("smoke_density") or 0)
            environment["smoke_density"] = _clamp(before - 0.45 * intensity)
            _event(events, "SMOKE_DISPERSED", from_density=before, to_density=environment["smoke_density"])
        if state.get("burning") and "CREATE_WIND" in effects:
            _event(events, "FIRE_SPREAD_RISK_INCREASED")

    return {
        "status": "ANIME_PHYSICS_RESOLVED",
        "move_id": str(move.get("move_id") or ""),
        "effects": sorted(effects),
        "target": target,
        "environment": environment,
        "events": events,
        "area_impacts": area_impacts,
    }
