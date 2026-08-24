from evennia import DefaultScript


class SizaConsequenceRegistry(DefaultScript):
    """Persistent registry for action -> consequence rules and processed action ids."""

    def at_script_creation(self):
        self.key = "SIZA_CONSEQUENCE_REGISTRY"
        self.desc = "Persistent Siza Action/Consequence rule registry."
        self.persistent = True
        self.interval = 0
        self.db.rules = []
        self.db.processed_action_ids = []
        self.db.action_log = []
        self.db.build = "0.27.0-action-consequence-memory"
