"""One combat profile contract for Players and NPCs."""
from copy import deepcopy

FIELDS = ("deck_id", "tcg_profile", "loadout", "world_status", "encounter_tags", "enabled")
def _dict(value):
    try: return dict(value or {})
    except Exception: return {}
def combat_profile(actor, *, migrate_legacy=True):
    profile = _dict(getattr(actor.db, "combat_profile", {})) if actor else {}
    legacy = {"deck_id": str(getattr(actor.db, "tcg_deck_id", "") or ""), "tcg_profile": _dict(getattr(actor.db, "tcg_profile", {})), "loadout": _dict(getattr(actor.db, "tcg_loadout", {})), "world_status": _dict(getattr(actor.db, "state", {}))} if actor else {}
    for key, value in legacy.items():
        if not profile.get(key): profile[key] = value
    profile.setdefault("encounter_tags", []); profile.setdefault("enabled", bool(profile.get("deck_id")))
    return {key: deepcopy(profile.get(key)) for key in FIELDS}
def set_combat_profile(actor, profile):
    current = combat_profile(actor); current.update({key: deepcopy(value) for key, value in _dict(profile).items() if key in FIELDS}); actor.db.combat_profile = current; return combat_profile(actor, migrate_legacy=False)
def combat_participant(actor, entity_id):
    profile = combat_profile(actor)
    return {"entity_id": str(entity_id or ""), "name": str(getattr(actor, "key", "") or ""), "deck_id": str(profile.get("deck_id") or ""), "loadout": profile.get("loadout") or {}, "world_status": profile.get("world_status") or {}, "tcg_profile": profile.get("tcg_profile") or {}, "encounter_tags": list(profile.get("encounter_tags") or [])}
