"""Campaign-neutral discovery for persistent Siza actors."""


def _objects():
    try:
        from evennia.objects.models import ObjectDB
        return list(ObjectDB.objects.all())
    except Exception:
        return []


def is_siza_npc(obj):
    return bool(obj and getattr(getattr(obj, "db", None), "is_npc", False))


def is_siza_character(obj):
    db = getattr(obj, "db", None)
    return bool(obj and db and (is_siza_npc(obj) or getattr(db, "siza_narration", False)))


def siza_actors(*, include_npcs=True, include_players=True):
    rows = [obj for obj in _objects() if (include_npcs and is_siza_npc(obj)) or (include_players and not is_siza_npc(obj) and is_siza_character(obj))]
    return sorted(rows, key=lambda obj: int(getattr(obj, "id", 0) or 0))


def siza_npcs(*, simulated_only=False):
    rows = [obj for obj in siza_actors(include_players=False) if str(getattr(obj.db, "npc_id", "") or "").strip()]
    return [obj for obj in rows if not simulated_only or bool(getattr(obj.db, "simulation_enabled", False))]


def find_npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    return next((obj for obj in siza_npcs() if str(getattr(obj.db, "npc_id", "") or "") == wanted), None)


def find_social_actor(identity):
    from services.social_graph_engine import resolve_social_entity
    return resolve_social_entity(identity)
