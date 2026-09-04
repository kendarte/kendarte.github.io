"""Canonical directed social graph.  Mutators and read-only APIs are separate."""
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone

DIMENSIONS = {"familiarity": (0, 100), "trust": (-100, 100), "affection": (-100, 100), "respect": (-100, 100), "fear": (0, 100)}
HISTORY_LIMIT = 50


def _dict(value):
    try: return {str(k): v for k, v in (value or {}).items()}
    except Exception: return {}


def _list(value):
    try: return list(value or [])
    except Exception: return []


def _now(): return datetime.now(timezone.utc).isoformat()


def peek_social_entity_id(entity):
    """Identity read without attributes, scripts, registrations or migrations."""
    if isinstance(entity, str): return entity.strip() or None
    if not entity: return None
    existing = str(getattr(entity.db, "social_entity_id", "") or "").strip()
    if existing: return existing
    npc_id = str(getattr(entity.db, "npc_id", "") or "").strip()
    if bool(getattr(entity.db, "is_npc", False)) and npc_id: return "NPC:" + npc_id
    dbref = getattr(entity, "id", None)
    return "PLAYER:" + str(dbref) if dbref is not None else None


def social_entity_id(entity):
    """Writable identity assignment for authoritative code only."""
    identity = peek_social_entity_id(entity)
    if identity and not isinstance(entity, str) and not str(getattr(entity.db, "social_entity_id", "") or ""):
        entity.db.social_entity_id = identity
    return identity


def resolve_social_entity(identity):
    text = str(identity or "").strip()
    if not text: return None
    try:
        from services.actor_registry import siza_actors
        return next((obj for obj in siza_actors() if peek_social_entity_id(obj) == text), None)
    except Exception: return None


def _normalize(row, *, stamp=True):
    row = _dict(row)
    for name, (low, high) in DIMENSIONS.items():
        try: value = int(row.get(name, 0) or 0)
        except (TypeError, ValueError): value = 0
        row[name] = max(low, min(high, value))
    row["roles"] = sorted({str(x).upper() for x in _list(row.get("roles")) if str(x).strip()})
    for field in ("obligations", "history", "decision_effects"):
        row[field] = [_dict(x) for x in _list(row.get(field)) if _dict(x)]
    row["history"] = row["history"][-HISTORY_LIMIT:]
    if stamp:
        row.setdefault("created_at", _now()); row["updated_at"] = _now()
    return row


def _legacy_edges(source):
    edges = {}
    for key, raw in _dict(getattr(source.db, "relationships", {})).items():
        row = _dict(raw); target_npc = str(row.get("target_npc_id") or key)
        identity = str(row.get("target_social_entity_id") or "NPC:" + target_npc)
        row.setdefault("target_npc_id", target_npc); row["target_social_entity_id"] = identity
        edges[identity] = _normalize(row, stamp=False)
    return edges


def _merged_edges(source):
    """Read canonical + legacy, with legacy taking precedence while legacy writers remain."""
    result = {key: _normalize(value, stamp=False) for key, value in _dict(getattr(source.db, "social_relationships", {})).items()}
    result.update(_legacy_edges(source))
    return result


def read_relationship(source, target):
    identity = peek_social_entity_id(target)
    row = _merged_edges(source).get(identity) if identity else None
    return deepcopy(row) if row is not None else None


def read_related_entities(source, *, roles=None, active_obligations=None, limit=20):
    wanted = {str(x).upper() for x in _list(roles)}
    rows = []
    for identity, row in sorted(_merged_edges(source).items())[:max(0, int(limit))]:
        if wanted and not wanted.intersection(row.get("roles", [])): continue
        if active_obligations and not any(bool(x.get("active")) for x in row.get("obligations", [])): continue
        rows.append({"target_social_entity_id": identity, "relationship": deepcopy(row)})
    return rows


def read_social_path(source, target, *, max_depth=2, max_results=100):
    start, end = peek_social_entity_id(source), peek_social_entity_id(target)
    if not start or not end: return None
    queue, seen, scanned = deque([(start, [start])]), {start}, 0
    while queue and scanned < max_results:
        node, path = queue.popleft()
        if node == end: return path
        if len(path) - 1 >= max_depth: continue
        entity = resolve_social_entity(node)
        if not entity: continue
        for nxt in _merged_edges(entity):
            scanned += 1
            if nxt not in seen: seen.add(nxt); queue.append((nxt, path + [nxt]))
    return None


def _save(source, edges):
    source.db.social_relationships = deepcopy(edges)
    legacy = _dict(getattr(source.db, "relationships", {}))
    for identity, row in edges.items():
        if identity.startswith("NPC:"): legacy[identity[4:]] = deepcopy(row)
    source.db.relationships = legacy


def sync_legacy_relationships(source):
    """Explicit bridge for remaining legacy writers; refreshes canonical immediately."""
    if not source:
        return {}
    edges = _merged_edges(source)
    source.db.social_relationships = deepcopy(edges)
    return deepcopy(edges)


def ensure_relationship(source, target):
    source_id, target_id = social_entity_id(source), social_entity_id(target)
    if not source_id or not target_id: raise ValueError("Both social entities need an identity")
    edges = _merged_edges(source); row = _normalize(edges.get(target_id, {}))
    row.update({"source_social_entity_id": source_id, "target_social_entity_id": target_id, "target_type": target_id.split(":", 1)[0], "target_name": getattr(target, "key", row.get("target_name", ""))})
    if target_id.startswith("NPC:"): row["target_npc_id"] = target_id[4:]
    edges[target_id] = row; _save(source, edges); return deepcopy(row)


def _mutate(source, target, fn):
    target_id = social_entity_id(target)
    ensure_relationship(source, target)
    edges = _merged_edges(source); row = _normalize(edges[target_id]); fn(row); edges[target_id] = _normalize(row); _save(source, edges)
    return deepcopy(edges[target_id])


def set_relationship_dimension(source, target, dimension, value):
    if dimension not in DIMENSIONS: raise ValueError("Unknown relationship dimension")
    return _mutate(source, target, lambda row: row.__setitem__(dimension, value))
def adjust_relationship_dimension(source, target, dimension, delta):
    if dimension not in DIMENSIONS: raise ValueError("Unknown relationship dimension")
    return _mutate(source, target, lambda row: row.__setitem__(dimension, int(row.get(dimension, 0)) + int(delta)))
def add_relationship_role(source, target, role): return _mutate(source, target, lambda row: row.__setitem__("roles", _list(row.get("roles")) + [str(role).upper()]))
def remove_relationship_role(source, target, role): return _mutate(source, target, lambda row: row.__setitem__("roles", [x for x in _list(row.get("roles")) if str(x).upper() != str(role).upper()]))
def add_relationship_obligation(source, target, obligation): return _mutate(source, target, lambda row: row.__setitem__("obligations", _list(row.get("obligations")) + [_dict(obligation)]))
def append_relationship_history(source, target, entry):
    item = _dict(entry); item.setdefault("timestamp", _now())
    return _mutate(source, target, lambda row: row.__setitem__("history", _list(row.get("history")) + [item]))


# Compatibility aliases; unlike social_entity_id, these are safe in DM paths.
get_relationship = read_relationship
related_entities = read_related_entities
social_path = read_social_path
