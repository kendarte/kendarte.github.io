from evennia import search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v21_relationship_identity"
UPGRADE_CATEGORY = "siza_upgrade"
MARA_ID = "NPC-KAL-DAR-MARA-001"


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
        return {}


def _find_npc(npc_id):
    wanted = str(npc_id or "")
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == wanted:
            return obj
    return None


def _target_by_dbref(raw):
    text = str(raw or "").strip().lstrip("#")
    if not text.isdigit():
        return None
    matches = list(search_object(f"#{text}"))
    return matches[0] if len(matches) == 1 else None


def _identity_for(target):
    npc_id = str(getattr(target.db, "npc_id", "") or "").strip()
    if npc_id:
        return npc_id, {
            "target_type": "NPC",
            "target_npc_id": npc_id,
            "target_dbref": int(target.id),
            "target_name": target.key,
        }
    return f"DBREF:{int(target.id)}", {
        "target_type": "CHARACTER",
        "target_dbref": int(target.id),
        "target_name": target.key,
    }


def _merge_obligations(left, right):
    merged = []
    by_id = {}
    anonymous = []
    for raw in _plain_list(left) + _plain_list(right):
        item = _record(raw)
        obligation_id = str(item.get("id") or "").strip()
        if not obligation_id:
            anonymous.append(item)
            continue
        if obligation_id not in by_id:
            by_id[obligation_id] = item
        else:
            previous = by_id[obligation_id]
            previous.update(item)
            by_id[obligation_id] = previous
    merged.extend(by_id.values())
    merged.extend(anonymous)
    return merged


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _merge_relation(existing, incoming):
    old = _record(incoming)
    current = _record(existing)
    merged = dict(old)
    merged.update(current)
    merged["familiarity"] = max(
        _safe_int(old.get("familiarity")),
        _safe_int(current.get("familiarity")),
    )
    timestamps = [
        str(value)
        for value in (old.get("last_interaction"), current.get("last_interaction"))
        if value
    ]
    if timestamps:
        merged["last_interaction"] = max(timestamps)
    obligations = _merge_obligations(old.get("obligations"), current.get("obligations"))
    if obligations:
        merged["obligations"] = obligations
    return merged


def _normalize_holder(holder):
    relationships = _plain_dict(getattr(holder.db, "relationships", {}))
    if not relationships:
        return {"holder": holder.key, "changed": False, "moved": [], "unresolved": []}

    output = dict(relationships)
    moved = []
    unresolved = []

    for identity, raw_relation in list(relationships.items()):
        key = str(identity).strip()
        relation = _record(raw_relation)

        if key.startswith("DBREF:"):
            target = _target_by_dbref(key.split(":", 1)[1])
            if target:
                _new_key, metadata = _identity_for(target)
                relation.update(metadata)
                output[key] = relation
            continue

        if not key.isdigit():
            target = _find_npc(key)
            if target:
                _new_key, metadata = _identity_for(target)
                relation.update(metadata)
                output[key] = relation
            continue

        target = _target_by_dbref(key)
        if not target:
            unresolved.append(key)
            continue

        new_key, metadata = _identity_for(target)
        relation.update(metadata)
        existing = output.get(new_key)
        output[new_key] = _merge_relation(existing, relation) if existing is not None else relation
        if new_key != key:
            output.pop(key, None)
            moved.append({"old": key, "new": new_key, "target": target.key})

    changed = output != relationships
    if changed:
        holder.db.relationships = output
    return {
        "holder": holder.key,
        "changed": changed,
        "moved": moved,
        "unresolved": unresolved,
    }


def build():
    mara = _find_npc(MARA_ID)
    if not mara:
        caller.msg("No puedo aplicar v0.21: falta Mara Vensal.")
        return

    if mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.21 ya estaba aplicado; no se reescribieron relationships.")
        return

    holders = []
    seen = set()
    for obj in [caller] + list(search_tag(ENTITY_TAG, category=ENTITY_CATEGORY)):
        if not obj or obj.id in seen:
            continue
        seen.add(obj.id)
        holders.append(obj)

    results = [_normalize_holder(holder) for holder in holders]
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.21 aplicado: identidad estable para relationships.")
    caller.msg("NPC targets usan npc_id; targets sin npc_id usan DBREF:<id> explícito.")
    caller.msg("No se borró familiarity, last_interaction, memories ni obligations.")
    for row in results:
        if not row.get("changed") and not row.get("unresolved"):
            continue
        caller.msg(f"{row.get('holder')}: changed={row.get('changed')}")
        for move in row.get("moved") or []:
            caller.msg(
                f"  {move.get('old')} -> {move.get('new')} | target={move.get('target')}"
            )
        for key in row.get("unresolved") or []:
            caller.msg(f"  unresolved legacy identity preserved: {key}")
    caller.msg("Prueba: siza-relationships Mara")


build()
