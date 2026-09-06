"""Small explicit registry for authored DM campaigns."""

from services.dm_campaign_director import get_campaign_state, project_campaign_evidence, start_campaign, validate_campaign_definition


_CAMPAIGNS = {}


def register_campaign(definition):
    checked = validate_campaign_definition(definition)
    if not checked.get("valid"):
        return {"status": "INVALID_CAMPAIGN", "registered": False, "validation": checked}
    campaign_id = checked["campaign_id"]
    _CAMPAIGNS[campaign_id] = definition
    return {"status": "REGISTERED", "registered": True, "campaign_id": campaign_id}


def resolve_campaign(campaign_id):
    return _CAMPAIGNS.get(str(campaign_id or "").strip())


def start_registered_campaign(actor, campaign_id, force=False):
    definition = resolve_campaign(campaign_id)
    if not definition:
        return {"status": "CAMPAIGN_NOT_REGISTERED", "started": False, "campaign_id": str(campaign_id or "")}
    return start_campaign(actor, definition, force=force)


def get_active_campaign_definition(actor):
    state = get_campaign_state(actor)
    campaign_id = str(state.get("campaign_id") or "")
    definition = resolve_campaign(campaign_id)
    return {"state": state, "campaign_id": campaign_id, "definition": definition}


def observe_active_campaign_evidence(actor, evidence):
    """Forward only a World Engine packet to the active campaign's authored observer."""
    active = get_active_campaign_definition(actor)
    if not active.get("definition"):
        return {"status": "NO_REGISTERED_ACTIVE_CAMPAIGN", "advanced": False, "projected": []}
    return project_campaign_evidence(actor, active["definition"], evidence)
