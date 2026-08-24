from evennia import create_script, search_script


FACTION_BUILD = "0.24.0-faction-membership-loyalty"
FACTION_REGISTRY_KEY = "SIZA_FACTION_REGISTRY"
MIN_LOYALTY_BIAS = -100
MAX_LOYALTY_BIAS = 100


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clamp(value, low, high):
    return max(low, min(high, int(value)))


def get_faction_registry(create=False):
    matches = list(search_script(FACTION_REGISTRY_KEY))
    registry = matches[0] if matches else None
    if registry is None and create:
        registry = create_script(
            "typeclasses.faction_registry.SizaFactionRegistry",
            key=FACTION_REGISTRY_KEY,
            persistent=True,
            autostart=True,
        )
    if registry is not None:
        if registry.db.factions is None:
            registry.db.factions = {}
        registry.db.build = FACTION_BUILD
    return registry


def faction_definitions():
    registry = get_faction_registry(create=False)
    if registry is None:
        return {}
    output = {}
    for faction_id, raw in _plain_dict(registry.db.factions).items():
        item = _record(raw)
        if item is not None:
            item.setdefault("id", str(faction_id))
            output[str(faction_id)] = item
    return output


def upsert_faction(faction):
    item = _record(faction)
    faction_id = str((item or {}).get("id") or "").strip()
    if not faction_id:
        return None
    registry = get_faction_registry(create=True)
    factions = faction_definitions()
    item["id"] = faction_id
    item.setdefault("name", faction_id)
    item.setdefault("active", True)
    item.setdefault("canon_status", "prototype")
    factions[faction_id] = item
    registry.db.factions = factions
    registry.db.build = FACTION_BUILD
    return dict(item)


def _membership_rows(npc):
    if not npc:
        return []
    raw = getattr(npc.db, "faction_memberships", None)
    output = []
    if isinstance(raw, dict):
        iterable = []
        for faction_id, value in raw.items():
            item = _record(value) or {}
            item.setdefault("faction_id", str(faction_id))
            iterable.append(item)
    else:
        iterable = _plain_list(raw)

    for value in iterable:
        item = _record(value)
        if item is None:
            continue
        faction_id = str(item.get("faction_id") or item.get("id") or "").strip()
        if not faction_id:
            continue
        item["faction_id"] = faction_id
        item["active"] = bool(item.get("active", True))
        item["loyalty_bias"] = _clamp(
            _safe_int(item.get("loyalty_bias"), 0),
            MIN_LOYALTY_BIAS,
            MAX_LOYALTY_BIAS,
        )
        item.setdefault("role", None)
        item.setdefault("rank", None)
        item.setdefault("canon_status", "prototype")
        output.append(item)
    return output


def npc_memberships(npc, active_only=False):
    rows = _membership_rows(npc)
    if active_only:
        rows = [row for row in rows if bool(row.get("active"))]
    return rows


def membership_for(npc, faction_id, active_only=False):
    wanted = str(faction_id or "").strip()
    for row in npc_memberships(npc, active_only=active_only):
        if str(row.get("faction_id") or "") == wanted:
            return row
    return None


def upsert_membership(npc, membership):
    if not npc:
        return None
    item = _record(membership)
    faction_id = str((item or {}).get("faction_id") or (item or {}).get("id") or "").strip()
    if not faction_id:
        return None
    item["faction_id"] = faction_id
    item["active"] = bool(item.get("active", True))
    item["loyalty_bias"] = _clamp(
        _safe_int(item.get("loyalty_bias"), 0),
        MIN_LOYALTY_BIAS,
        MAX_LOYALTY_BIAS,
    )
    item.setdefault("role", None)
    item.setdefault("rank", None)
    item.setdefault("canon_status", "prototype")

    output = []
    replaced = False
    for existing in npc_memberships(npc):
        if str(existing.get("faction_id") or "") == faction_id:
            output.append(dict(item))
            replaced = True
        else:
            output.append(dict(existing))
    if not replaced:
        output.append(dict(item))
    npc.db.faction_memberships = output
    return dict(item)


def set_membership_active(npc, faction_id, active):
    current = membership_for(npc, faction_id)
    if not current:
        return None
    current = dict(current)
    current["active"] = bool(active)
    return upsert_membership(npc, current)


def set_loyalty_bias(npc, faction_id, value):
    current = membership_for(npc, faction_id)
    if not current:
        return None
    current = dict(current)
    current["loyalty_bias"] = _clamp(
        _safe_int(value, 0),
        MIN_LOYALTY_BIAS,
        MAX_LOYALTY_BIAS,
    )
    return upsert_membership(npc, current)


def has_active_membership(npc, faction_id):
    return membership_for(npc, faction_id, active_only=True) is not None


def faction_context_modifiers(npc, goal):
    """Return per-membership decision modifiers for goals from one faction.

    Loyalty has no universal formula. Each membership stores its own signed
    loyalty_bias, which affects only ORDER goals carrying that same faction_id.
    """
    item = dict(goal or {})
    if str(item.get("type") or "").upper() != "ORDER":
        return []

    faction_id = str(
        item.get("faction_id")
        or item.get("authority_faction_id")
        or ""
    ).strip()
    if not faction_id:
        return []

    membership = membership_for(npc, faction_id, active_only=True)
    if not membership:
        return []

    value = int(membership.get("loyalty_bias", 0) or 0)
    if not value:
        return []
    return [
        {
            "id": f"FACTION_LOYALTY:{faction_id}",
            "value": value,
            "source": "faction_membership",
            "faction_id": faction_id,
            "role": membership.get("role"),
            "rank": membership.get("rank"),
        }
    ]


def inspect_factions():
    return {
        "build": FACTION_BUILD,
        "registry_exists": get_faction_registry(create=False) is not None,
        "factions": list(faction_definitions().values()),
    }


def inspect_memberships(npc):
    definitions = faction_definitions()
    rows = []
    for membership in npc_memberships(npc):
        faction_id = str(membership.get("faction_id") or "")
        faction = definitions.get(faction_id) or {}
        rows.append(
            {
                **membership,
                "faction_name": faction.get("name") or faction_id,
                "faction_active": bool(faction.get("active", True)) if faction else None,
            }
        )
    return rows
