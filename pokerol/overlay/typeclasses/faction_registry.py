from evennia import DefaultScript


FACTION_REGISTRY_KEY = "SIZA_FACTION_REGISTRY"
FACTION_REGISTRY_BUILD = "0.24.0-faction-membership-loyalty"


class SizaFactionRegistry(DefaultScript):
    """Persistent registry for faction definitions; memberships remain on actors."""

    def at_script_creation(self):
        self.key = FACTION_REGISTRY_KEY
        self.desc = "Persistent Siza faction registry."
        self.persistent = True
        self.db.factions = {}
        self.db.build = FACTION_REGISTRY_BUILD
