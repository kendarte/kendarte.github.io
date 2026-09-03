def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_string_list(value):
    try:
        rows = list(value or [])
    except Exception:
        rows = []
    output = []
    for raw in rows:
        item = str(raw or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def read_npc_combat_profile(npc):
    """Return the authored, persistent combat profile without resolving TCG cards."""
    raw = _plain_dict(getattr(getattr(npc, "db", None), "combat_profile", {}))
    deck_id = str(raw.get("deck_id") or "").strip() or None
    return {
        "enabled": bool(raw.get("enabled", False)),
        "deck_id": deck_id,
        "tcg_profile": _plain_dict(raw.get("tcg_profile")),
        "loadout": _plain_dict(raw.get("loadout")),
        "world_status": _plain_dict(raw.get("world_status")),
        "encounter_tags": _plain_string_list(raw.get("encounter_tags")),
    }


def build_npc_combat_opponent(npc):
    """Build the World Engine -> TCG opponent participant packet for one NPC."""
    if not npc:
        return {"ok": False, "status": "NPC_MISSING"}

    profile = read_npc_combat_profile(npc)
    if not profile["enabled"]:
        return {"ok": False, "status": "NPC_COMBAT_DISABLED"}
    if not profile["deck_id"]:
        return {"ok": False, "status": "NPC_DECK_MISSING"}

    npc_id = str(getattr(npc.db, "npc_id", "") or "").strip()
    if not npc_id:
        npc_id = f"NPC-DBREF-{int(npc.id)}"

    return {
        "ok": True,
        "status": "NPC_COMBAT_OPPONENT_READY",
        "opponent": {
            "npc_id": npc_id,
            "name": str(getattr(npc, "key", "") or npc_id),
            "deck_id": profile["deck_id"],
            "tcg_profile": profile["tcg_profile"],
            "loadout": profile["loadout"],
            "world_status": profile["world_status"],
        },
        "world_context_tags": profile["encounter_tags"],
    }
