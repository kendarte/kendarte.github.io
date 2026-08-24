from evennia import create_object, search_object, search_tag

from services.consequence_engine import get_consequence_registry, upsert_consequence_rule


PILOT_BUILD = "0.51.0-persistent-pescaderia-gameplay"
PESCADERIA_ID = "CAR-KAL-DAR-007"
PILOT_TAG = "kalnaj_pilot_v51_playable_content"
PILOT_CATEGORY = "siza_pilot_v51"

CONTAINER_ID = "OBJ-TEST-PESCADERIA-REPARTO-001"
CONTAINER_NAME = "Cajon de reparto de prueba"
MANIFEST_ID = "OBJ-TEST-PESCADERIA-MANIFIESTO-001"
MANIFEST_NAME = "Manifiesto de carga de prueba"

OPEN_ACTION_ID = "ACT-TEST-PESCADERIA-ABRIR-CAJON-001"
INSPECT_ACTION_ID = "ACT-TEST-PESCADERIA-REGISTRAR-CAJON-001"
OPEN_RULE_ID = "RULE-TEST-PESCADERIA-ABRIR-CAJON-001"
INSPECT_RULE_ID = "RULE-TEST-PESCADERIA-REGISTRAR-CAJON-001"
MANIFEST_VISIBLE_FIELD = "v051_manifest_visible"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _find_site():
    for obj in search_object("Pescaderia de Darsena"):
        if str(getattr(obj.db, "room_id", "") or "") == PESCADERIA_ID:
            return obj
    return None


def _find_content_object(site, object_id):
    for obj in search_tag(PILOT_TAG, category=PILOT_CATEGORY):
        if str(getattr(obj.db, "object_id", "") or "") == object_id:
            return obj
    if site:
        for obj in list(getattr(site, "contents", []) or []):
            if str(getattr(obj.db, "object_id", "") or "") == object_id:
                return obj
    return None


def _ensure_container(site):
    obj = _find_content_object(site, CONTAINER_ID)
    created = False
    if obj is None:
        obj = create_object(
            "typeclasses.siza_objects.WorldObject",
            key=CONTAINER_NAME,
            location=site,
            aliases=["cajon de reparto", "cajon", "contenedor de reparto"],
            tags=[(PILOT_TAG, PILOT_CATEGORY)],
        )
        obj.db.object_id = CONTAINER_ID
        obj.db.state = {
            "sealed": True,
            "opened_count": 0,
            "inspected": False,
        }
        created = True
    elif obj.location != site:
        return None, created, "CONTAINER_WRONG_LOCATION"

    state = _plain_dict(getattr(obj.db, "state", {}))
    state.setdefault("sealed", True)
    state.setdefault("opened_count", 0)
    state.setdefault("inspected", False)
    obj.db.state = state
    obj.db.portable = False
    obj.db.hidden = False
    obj.db.canon_status = "prototype"
    obj.db.desc = (
        "Contenedor prototype persistente usado para probar interacciones, estado y consecuencias "
        "dentro de la Pescaderia de Darsena."
    )
    obj.db.state_visibility_requirements = []
    obj.db.object_actions = [
        {
            "id": OPEN_ACTION_ID,
            "name": "Abrir cajon de reparto",
            "input_phrases": ["abrir", "desellar"],
            "enabled": True,
            "object_state_requirements": [
                {
                    "field": "sealed",
                    "op": "EQ",
                    "value": True,
                    "name": "Cajon sellado",
                }
            ],
            "canon_status": "prototype",
        },
        {
            "id": INSPECT_ACTION_ID,
            "name": "Registrar cajon de reparto",
            "input_phrases": ["registrar", "revisar", "inspeccionar"],
            "enabled": True,
            "object_state_requirements": [
                {
                    "field": "sealed",
                    "op": "EQ",
                    "value": False,
                    "name": "Cajon abierto",
                },
                {
                    "field": "inspected",
                    "op": "EQ",
                    "value": False,
                    "name": "Cajon sin registrar",
                },
            ],
            "canon_status": "prototype",
        },
    ]
    obj.tags.add(PILOT_TAG, category=PILOT_CATEGORY)
    return obj, created, None


def _ensure_manifest(site):
    obj = _find_content_object(site, MANIFEST_ID)
    created = False
    if obj is None:
        obj = create_object(
            "typeclasses.siza_objects.WorldObject",
            key=MANIFEST_NAME,
            location=site,
            aliases=["manifiesto", "manifiesto de carga"],
            tags=[(PILOT_TAG, PILOT_CATEGORY)],
        )
        obj.db.object_id = MANIFEST_ID
        obj.db.state = {}
        created = True
    elif obj.location != site:
        return None, created, "MANIFEST_WRONG_LOCATION"

    obj.db.portable = False
    obj.db.hidden = False
    obj.db.canon_status = "prototype"
    obj.db.desc = (
        "Documento prototype persistente revelado por una consecuencia del cajon de reparto."
    )
    obj.db.state_visibility_requirements = [
        {
            "field": MANIFEST_VISIBLE_FIELD,
            "op": "EQ",
            "value": 1,
            "name": "Manifiesto descubierto",
        }
    ]
    obj.tags.add(PILOT_TAG, category=PILOT_CATEGORY)
    return obj, created, None


def _ensure_rules():
    open_rule = upsert_consequence_rule(
        {
            "id": OPEN_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": OPEN_ACTION_ID,
                "object_id": CONTAINER_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": "sealed",
                    "op": "SET",
                    "value": False,
                },
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": "opened_count",
                    "op": "ADD",
                    "value": 1,
                },
            ],
        }
    )
    inspect_rule = upsert_consequence_rule(
        {
            "id": INSPECT_RULE_ID,
            "enabled": True,
            "canon_status": "prototype",
            "recipient_mode": "ACTION_RECIPIENTS",
            "when": {
                "action_type": "OBJECT_ACTION_COMPLETED",
                "object_action_id": INSPECT_ACTION_ID,
                "object_id": CONTAINER_ID,
                "outcome": "COMPLETED",
            },
            "state_effects": [
                {
                    "scope": "ACTION_OBJECT",
                    "namespace": "state",
                    "field": "inspected",
                    "op": "SET",
                    "value": True,
                },
                {
                    "scope": "ACTION_SITE",
                    "namespace": "world_state",
                    "field": MANIFEST_VISIBLE_FIELD,
                    "op": "SET",
                    "value": 1,
                },
            ],
        }
    )
    get_consequence_registry(create=True)
    return open_rule, inspect_rule


def ensure_v51_pilot_content():
    """Idempotently install the first persistent playable object-action loop in the real pilot Pescaderia."""
    site = _find_site()
    if not site:
        return {
            "success": False,
            "reason": "PESCADERIA_NOT_FOUND",
            "build": PILOT_BUILD,
        }

    container, container_created, error = _ensure_container(site)
    if error:
        return {
            "success": False,
            "reason": error,
            "build": PILOT_BUILD,
            "site": site,
        }

    manifest, manifest_created, error = _ensure_manifest(site)
    if error:
        return {
            "success": False,
            "reason": error,
            "build": PILOT_BUILD,
            "site": site,
            "container": container,
        }

    open_rule, inspect_rule = _ensure_rules()
    site.tags.add(PILOT_TAG, category=PILOT_CATEGORY)

    return {
        "success": True,
        "reason": "INSTALLED_OR_PRESENT",
        "build": PILOT_BUILD,
        "site": site,
        "container": container,
        "manifest": manifest,
        "container_created": container_created,
        "manifest_created": manifest_created,
        "open_rule": open_rule,
        "inspect_rule": inspect_rule,
    }
